import asyncio
import json
import logging
import os
from collections import defaultdict
from datetime import date as _date
from datetime import timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from playtomic_agent.client.api import PlaytomicClient
from playtomic_agent.client.exceptions import APIError, ClubNotFoundError
from playtomic_agent.context import get_timezone, set_request_region
from playtomic_agent.web.agent import create_playtomic_agent

logger = logging.getLogger(__name__)

app = FastAPI(title="Playtomic Agent API")

# Setup Rate Limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

# Allow local frontend dev server access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files if the directory exists (Production mode)
# This assumes the frontend build is copied to /app/static in the Docker image
STATIC_DIR = os.environ.get("STATIC_DIR", "/app/static")
if os.path.isdir(STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=f"{STATIC_DIR}/assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # Serve index.html for unknown paths (SPA routing)
        # Check if file exists in static dir, if not return index.html
        possible_file = os.path.join(STATIC_DIR, full_path)
        if os.path.isfile(possible_file):
            return FileResponse(possible_file)
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/health")
async def health_check():
    """Health check endpoint for Railway."""
    return {"status": "ok"}


class ChatRequest(BaseModel):
    prompt: str | None = None
    messages: list[dict] | None = None
    user_profile: dict | None = None
    # Region settings (from frontend region selector)
    country: str | None = None
    language: str | None = None
    timezone: str | None = None


class ProfileSuggestion(BaseModel):
    key: str
    value: str


class ChatResponse(BaseModel):
    text: str
    profile_suggestions: list[ProfileSuggestion] | None = None


class TimeWindow(BaseModel):
    days: list[int]  # 0=Mon … 6=Sun
    start: str  # HH:MM
    end: str  # HH:MM


class SearchRequest(BaseModel):
    club_slug: str
    date_from: str
    date_to: str
    time_windows: list[TimeWindow]
    duration: int | None = None
    court_type: Literal["SINGLE", "DOUBLE"] | None = None
    timezone: str | None = None
    language: str | None = None
    country: str | None = None


class SlotResult(BaseModel):
    date: str  # YYYY-MM-DD
    local_time: str  # HH:MM
    court: str
    duration: int
    price: str
    booking_link: str


class SearchResponse(BaseModel):
    results: list[SlotResult]
    total_count: int
    dates_checked: int
    error: str | None = None


class ClubResult(BaseModel):
    name: str
    slug: str


def _extract_text(m) -> str | None:
    """Extract text content from various message formats."""
    # Try content_blocks first (LangChain AIMessage-like)
    try:
        cbs = getattr(m, "content_blocks", None)
        if cbs:
            for cb in cbs:
                t = getattr(cb, "text", None)
                if t:
                    return str(t)
    except Exception:
        pass

    # Try content (string or list of dicts)
    try:
        content = getattr(m, "content", None)
        if isinstance(content, str):
            return content
        elif isinstance(content, list | tuple):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                    return item.get("text")
    except Exception:
        pass

    return None


def _map_exception_to_error(exc: Exception) -> dict:
    """Map exceptions to standard error codes and friendly messages."""
    msg = str(exc)

    # 1. Network / Connection Errors
    if "ConnectError" in msg or "Network is unreachable" in msg or "socket" in msg.lower():
        return {
            "code": "NETWORK_ERROR",
            "message": "Network connection lost. Please check your internet connection.",
            "detail": msg,
        }

    # 2. Rate Limits (Google GenAI)
    if "429" in msg or "ResourceExhausted" in msg:
        return {
            "code": "RATE_LIMIT_ERROR",
            "message": "I'm receiving too many requests right now. Please try again in a minute.",
            "detail": msg,
        }

    # 3. Recursion Limit (Agent getting stuck)
    if "recursion limit" in msg.lower():
        return {
            "code": "RECURSION_LIMIT_ERROR",
            "message": "I thought about this for too long and got stuck. Please try rephrasing your request.",
            "detail": msg,
        }

    # 4. Parsing / JSON Errors
    if "JSONDecodeError" in msg:
        return {
            "code": "PARSING_ERROR",
            "message": "I couldn't understand the server response. Please try again.",
            "detail": msg,
        }

    # Default: Internal Error
    return {
        "code": "INTERNAL_SERVER_ERROR",
        "message": "Something went wrong. Please try again later.",
        "detail": msg,
    }


@app.post("/api/chat")
@limiter.limit("100/day")
async def chat(req: ChatRequest, request: Request):  # Added request param for limiter
    """Accept a prompt, run the agent, and stream events via SSE.

    Events:
    - tool_start: {"tool": "name", "input": "..."}
    - tool_end: {"tool": "name", "output": "..."}
    - message: {"text": "final response"}
    - profile_suggestion: {"key": "...", "value": "..."}
    - error: {"detail": "..."}
    """
    # Prepare input
    if req.messages:
        messages = [{"role": m["role"], "content": m["content"]} for m in req.messages]
    elif req.prompt:
        messages = [{"role": "user", "content": req.prompt}]
    else:
        raise HTTPException(
            status_code=400, detail="Either 'prompt' or 'messages' must be provided."
        )

    # Token Optimization: Truncate history to last 20 messages
    # This prevents the context window from growing indefinitely
    if len(messages) > 20:
        # always keep the last message (user prompt) and preceding context
        # but ensure we don't cut off half a tool exchange if possible (LangGraph handles it, but safer to be generous)
        messages = messages[-20:]

    # Set context
    set_request_region(
        country=req.country,
        language=req.language,
        timezone=req.timezone,
    )

    agent = create_playtomic_agent(req.user_profile, language=req.language)

    async def stream_agent_events():
        try:
            logging.debug(f"Starting agent stream with profile: {req.user_profile}")

            # Use "updates" mode to get each step of the graph
            async for chunk in agent.astream(
                {"messages": messages}, stream_mode="updates", config={"recursion_limit": 30}
            ):
                for step, data in chunk.items():
                    logging.debug(f"Agent Step: {step}")

                    for m in data.get("messages", []):
                        # 1. Check for Tool Calls (Tool Start)
                        if getattr(m, "tool_calls", None):
                            for tc in m.tool_calls:
                                event = {
                                    "type": "tool_start",
                                    "tool": tc.get("name"),
                                    # "input" turned out to cause JSON parsing issues on frontend if it contains quotes
                                }
                                yield f"data: {json.dumps(event)}\n\n"
                                await asyncio.sleep(0.01)  # Force flush
                                logging.debug(f"Stream yielded tool_start: {tc.get('name')}")

                                if tc.get("name") == "suggest_next_steps":
                                    try:
                                        args = tc.get("args", {})
                                        if "options" in args and isinstance(args["options"], list):
                                            chip_event = {
                                                "type": "suggestion_chips",
                                                "options": args["options"],
                                            }
                                            yield f"data: {json.dumps(chip_event)}\n\n"
                                            await asyncio.sleep(0.01)
                                            logging.info(
                                                f"Stream yielded suggestion_chips: {args['options']}"
                                            )
                                    except Exception as e:
                                        logging.error(f"Failed to parse suggestions: {e}")

                        # 2. Check for Tool Output (Tool End) & Profile Updates
                        if getattr(m, "tool_call_id", None) is not None:
                            tool_name = getattr(m, "name", "unknown")
                            content = getattr(m, "content", "")

                            # Check for profile update
                            if tool_name == "update_user_profile":
                                try:
                                    # Content might be stringified JSON
                                    parsed = (
                                        json.loads(content) if isinstance(content, str) else content
                                    )
                                    if isinstance(parsed, dict) and "profile_update" in parsed:
                                        update = parsed["profile_update"]
                                        event = {
                                            "type": "profile_suggestion",
                                            "key": update["key"],
                                            "value": update["value"],
                                        }
                                        yield f"data: {json.dumps(event)}\n\n"
                                        await asyncio.sleep(0.01)  # Force flush
                                        logging.info(f"Stream yielded profile_suggestion: {update}")
                                except Exception:
                                    pass

                            # Emit generic tool end
                            event = {
                                "type": "tool_end",
                                "tool": tool_name,
                                "output": str(content)[:200],  # truncate for log/stream
                            }
                            yield f"data: {json.dumps(event)}\n\n"
                            await asyncio.sleep(0.01)  # Force flush
                            logging.debug(f"Stream yielded tool_end: {tool_name}")

                            # Check for suggestion chips
                            if tool_name == "suggest_next_steps":
                                try:
                                    # Content might be stringified JSON or the return string
                                    # Since tool returns a string, we need to grab the input args to see what options were passed
                                    # But wait, we are in tool_end (output). We need the inputs?
                                    # Actually, langchain graph state stores messages.
                                    # The tool CALL has the args. The tool OUTPUT is just "Suggestions sent".
                                    # We can capture the tool call arguments from the ToolMessage? No, ToolMessage only has artifact/content.
                                    # We need to look at the corresponding AIMessage that called the tool.
                                    # BUT, simpler: in `tool_start` we have the input! Can we emit it then?
                                    # No, let's keep it simple. We can parse the input in `tool_start` or just rely on the fact that
                                    # we are processing the tool execution.
                                    # Let's look at `tool_start` above. It has `tc.get("args")`.
                                    pass
                                except Exception:
                                    pass

                        # 3. Check for Final Answer (Text)
                        # We only want the *final* assistant message, not intermediate tool calls
                        is_ai = (
                            m.__class__.__name__ == "AIMessage" or getattr(m, "type", "") == "ai"
                        )
                        if is_ai and not getattr(m, "tool_calls", None):
                            text = _extract_text(m)
                            if text:
                                event = {"type": "message", "text": text}
                                yield f"data: {json.dumps(event)}\n\n"
                                await asyncio.sleep(0.01)  # Force flush
                                logging.debug("Stream yielded final message")

        except Exception as exc:
            logging.exception("Agent stream failed")

            error_info = _map_exception_to_error(exc)

            error_event = {
                "type": "error",
                "code": error_info["code"],
                "message": error_info["message"],  # Fallback
                "detail": error_info["detail"],
            }

            yield f"data: {json.dumps(error_event)}\n\n"
            await asyncio.sleep(0.01)  # Force flush

    return StreamingResponse(stream_agent_events(), media_type="text/event-stream")


@app.get("/api/clubs")
async def search_clubs_endpoint(q: str = "") -> list[ClubResult]:
    """Search for clubs by name. Returns matching clubs with name and slug."""
    if len(q) < 2:
        return []
    try:
        with PlaytomicClient() as client:
            clubs = client.search_clubs(query=q)
        return [ClubResult(name=c.name, slug=c.slug) for c in clubs]
    except APIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/search", response_model=SearchResponse)
async def search_slots(req: SearchRequest):
    """Scan for available slots across a date range and time windows, bypassing the LLM."""
    # 1. Validate date range
    try:
        d_from = _date.fromisoformat(req.date_from)
        d_to = _date.fromisoformat(req.date_to)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid date format. Use YYYY-MM-DD.") from exc
    if d_to < d_from:
        raise HTTPException(status_code=422, detail="date_to must be >= date_from.")
    if (d_to - d_from).days > 13:
        raise HTTPException(status_code=422, detail="Date range must not exceed 14 days.")
    if not req.time_windows:
        raise HTTPException(status_code=422, detail="At least one time_window is required.")

    # 2. Set request context
    set_request_region(country=req.country, language=req.language, timezone=req.timezone)
    tz_str = get_timezone()

    # 3. Expand dates and build weekday → windows map
    all_dates = [d_from + timedelta(days=i) for i in range((d_to - d_from).days + 1)]
    window_by_day: dict[int, list[TimeWindow]] = defaultdict(list)
    for w in req.time_windows:
        for day in w.days:
            window_by_day[day].append(w)

    # 4. Scan each (date, window) combination
    results: list[SlotResult] = []
    dates_with_windows: set[str] = set()
    tz_zone = ZoneInfo(tz_str)

    try:
        with PlaytomicClient() as client:
            for d in all_dates:
                windows = window_by_day.get(d.weekday(), [])
                if not windows:
                    continue
                date_str = d.isoformat()
                dates_with_windows.add(date_str)
                for window in windows:
                    slots = client.find_slots(
                        club_slug=req.club_slug,
                        date=date_str,
                        court_type=req.court_type,
                        start_time=window.start,
                        end_time=window.end,
                        timezone=tz_str,
                        duration=req.duration,
                    )
                    for slot in slots:
                        local_dt = slot.time.astimezone(tz_zone)
                        results.append(
                            SlotResult(
                                date=date_str,
                                local_time=local_dt.strftime("%H:%M"),
                                court=slot.court_name,
                                duration=slot.duration,
                                price=slot.price,
                                booking_link=slot.get_link(),
                            )
                        )
    except ClubNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except APIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    results.sort(key=lambda r: (r.date, r.local_time))
    return SearchResponse(
        results=results,
        total_count=len(results),
        dates_checked=len(dates_with_windows),
    )
