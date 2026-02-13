import logging
import os
import sys

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from playtomic_agent.agent import create_playtomic_agent

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
    # optional settings for future use
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


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Accept a prompt, run the agent, and return the final assistant message.

    Optionally accepts a user_profile dict that is injected into the agent's
    system prompt for personalized responses.
    """
    # Prepare input for the agent – use full history when available
    if req.messages:
        messages = [{"role": m["role"], "content": m["content"]} for m in req.messages]
    elif req.prompt:
        messages = [{"role": "user", "content": req.prompt}]
    else:
        raise HTTPException(status_code=400, detail="Either 'prompt' or 'messages' must be provided.")

    # Create agent with user profile context
    agent = create_playtomic_agent(req.user_profile)

    # Track profile suggestions from tool calls
    profile_suggestions: list[ProfileSuggestion] = []
    final_text = None

    try:
        logging.debug(f"Starting agent with profile: {req.user_profile}")
        for chunk in agent.stream({"messages": messages}, stream_mode="updates", config={"recursion_limit": 15}):
            for step, data in chunk.items():
                logging.debug(f"Agent Step: {step}")

                for m in data.get("messages", []):
                    msg_type = type(m).__name__
                    logging.debug(f"  Message type={msg_type}, role={getattr(m, 'role', None)}, "
                                  f"tool_call_id={getattr(m, 'tool_call_id', None)}, "
                                  f"has_tool_calls={bool(getattr(m, 'tool_calls', None))}")

                    # Check for update_user_profile tool calls -> collect as suggestions
                    if getattr(m, "tool_call_id", None) is not None:
                        # This is a ToolMessage — log its content
                        tm_content = getattr(m, "content", None)
                        tm_name = getattr(m, "name", None)
                        logging.debug(f"  ToolMessage name={tm_name}, content (first 500 chars): {str(tm_content)[:500]}")
                        # check if it's a profile update
                        try:
                            content = getattr(m, "content", None)
                            if content and "profile_update" in str(content):
                                import json
                                parsed = json.loads(content) if isinstance(content, str) else content
                                if isinstance(parsed, dict) and "profile_update" in parsed:
                                    update = parsed["profile_update"]
                                    profile_suggestions.append(
                                        ProfileSuggestion(key=update["key"], value=update["value"])
                                    )
                                    logging.info(f"Profile suggestion: {update['key']}={update['value']}")
                        except Exception:
                            pass
                        continue

                    # Skip non-assistant messages
                    role = getattr(m, "role", None)
                    if role is not None and role != "assistant":
                        continue

                    # Skip AIMessages that contain tool_calls (intermediate steps)
                    if getattr(m, "tool_calls", None):
                        logging.debug(f"  Skipping AIMessage with tool_calls: {[tc.get('name') for tc in m.tool_calls]}")
                        continue

                    text = _extract_text(m)
                    logging.debug(f"  Extracted text (len={len(text) if text else 0}): {text[:200] if text else None}")
                    if text:
                        final_text = text

    except Exception as exc:
        logging.exception("Agent execution failed")
        raise HTTPException(status_code=500, detail=f"Agent execution error: {exc}") from exc

    if not final_text:
        raise HTTPException(status_code=500, detail="Agent did not return an assistant response.")

    return ChatResponse(
        text=final_text,
        profile_suggestions=profile_suggestions if profile_suggestions else None,
    )
