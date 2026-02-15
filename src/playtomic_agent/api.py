import asyncio
import logging
import os
import sys
import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from playtomic_agent.agent import create_playtomic_agent
from playtomic_agent.context import set_request_region

# Configure logging (use LOG_LEVEL env var, default to INFO)
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

app = FastAPI(title="Playtomic Agent API")

# Allow local frontend dev server access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


def _extract_text(m) -> str | None:
    """Extract text content from various message formats."""
    # Try content_blocks first (LangChain AIMessage-like)
    try:
        cbs = getattr(m, "content_blocks", None)
        if cbs:
            for cb in cbs:
                t = getattr(cb, "text", None)
                if t:
                    return t
    except Exception:
        pass

    # Try content (string or list of dicts)
    try:
        content = getattr(m, "content", None)
        if isinstance(content, str):
            return content
        elif isinstance(content, list | tuple):
            for item in content:
                if (
                    isinstance(item, dict)
                    and item.get("type") == "text"
                    and item.get("text")
                ):
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
            "detail": msg
        }
    
    # 2. Rate Limits (Google GenAI)
    if "429" in msg or "ResourceExhausted" in msg:
        return {
            "code": "RATE_LIMIT_ERROR",
            "message": "I'm receiving too many requests right now. Please try again in a minute.",
            "detail": msg
        }

    # 3. Recursion Limit (Agent getting stuck)
    if "recursion limit" in msg.lower():
        return {
            "code": "RECURSION_LIMIT_ERROR",
            "message": "I thought about this for too long and got stuck. Please try rephrasing your request.",
            "detail": msg
        }
        
    # 4. Parsing / JSON Errors
    if "JSONDecodeError" in msg:
        return {
            "code": "PARSING_ERROR",
            "message": "I couldn't understand the server response. Please try again.",
            "detail": msg
        }

    # Default: Internal Error
    return {
        "code": "INTERNAL_SERVER_ERROR",
        "message": "Something went wrong. Please try again later.",
        "detail": msg
    }

@app.post("/api/chat")
async def chat(req: ChatRequest):
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
        raise HTTPException(status_code=400, detail="Either 'prompt' or 'messages' must be provided.")

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
            for chunk in agent.stream({"messages": messages}, stream_mode="updates", config={"recursion_limit": 30}):
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
                                await asyncio.sleep(0.01) # Force flush
                                logging.debug(f"Stream yielded tool_start: {tc.get('name')}")

                                if tc.get("name") == "suggest_next_steps":
                                    try:
                                        args = tc.get("args", {})
                                        if "options" in args and isinstance(args["options"], list):
                                            chip_event = {
                                                "type": "suggestion_chips",
                                                "options": args["options"]
                                            }
                                            yield f"data: {json.dumps(chip_event)}\n\n"
                                            await asyncio.sleep(0.01)
                                            logging.info(f"Stream yielded suggestion_chips: {args['options']}")
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
                                    parsed = json.loads(content) if isinstance(content, str) else content
                                    if isinstance(parsed, dict) and "profile_update" in parsed:
                                        update = parsed["profile_update"]
                                        event = {
                                            "type": "profile_suggestion",
                                            "key": update["key"],
                                            "value": update["value"]
                                        }
                                        yield f"data: {json.dumps(event)}\n\n"
                                        await asyncio.sleep(0.01) # Force flush
                                        logging.info(f"Stream yielded profile_suggestion: {update}")
                                except Exception:
                                    pass

                            # Emit generic tool end
                            event = {
                                "type": "tool_end",
                                "tool": tool_name,
                                "output": str(content)[:200]  # truncate for log/stream
                            }
                            yield f"data: {json.dumps(event)}\n\n"
                            await asyncio.sleep(0.01) # Force flush
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
                        is_ai = m.__class__.__name__ == "AIMessage" or getattr(m, "type", "") == "ai"
                        if is_ai and not getattr(m, "tool_calls", None):
                            text = _extract_text(m)
                            if text:
                                event = {
                                    "type": "message",
                                    "text": text
                                }
                                yield f"data: {json.dumps(event)}\n\n"
                                await asyncio.sleep(0.01) # Force flush
                                logging.debug("Stream yielded final message")

        except Exception as exc:
            logging.exception("Agent stream failed")
            
            error_info = _map_exception_to_error(exc)
            
            error_event = {
                "type": "error",
                "code": error_info["code"],
                "message": error_info["message"], # Fallback
                "detail": error_info["detail"]
            }
            
            yield f"data: {json.dumps(error_event)}\n\n"
            await asyncio.sleep(0.01) # Force flush

    return StreamingResponse(stream_agent_events(), media_type="text/event-stream")
