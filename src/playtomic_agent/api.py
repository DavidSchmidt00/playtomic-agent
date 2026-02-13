from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from playtomic_agent.agent import playtomic_agent

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
    # optional settings for future use
    timezone: str | None = None


class ChatResponse(BaseModel):
    text: str


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Accept a prompt, run the agent, and return the final assistant message only.

    This function intentionally keeps the output minimal and does not expose any
    tool calls or internal reasoning.
    """
    # Prepare input for the agent – use full history when available
    if req.messages:
        messages = [{"role": m["role"], "content": m["content"]} for m in req.messages]
    elif req.prompt:
        messages = [{"role": "user", "content": req.prompt}]
    else:
        raise HTTPException(status_code=400, detail="Either 'prompt' or 'messages' must be provided.")

    # Try streaming to capture the final assistant text
    final_text = None
    try:
        for chunk in playtomic_agent.stream({"messages": messages}, stream_mode="updates"):
            # chunk is a dict mapping step -> data
            for _, data in chunk.items():
                # Each data contains a list of messages; be permissive because
                # message objects from the model may not always include a `role`.
                for m in data.get("messages", []):
                    # Skip tool messages. ToolMessage instances often set a `tool_call_id`.
                    if getattr(m, "tool_call_id", None) is not None:
                        continue

                    role = getattr(m, "role", None)
                    # If role is present and not assistant, skip
                    if role is not None and role != "assistant":
                        continue

                    text = None
                    # Try content_blocks (LangChain AIMessage-like)
                    try:
                        cbs = getattr(m, "content_blocks", None)
                        if cbs:
                            for cb in cbs:
                                t = getattr(cb, "text", None)
                                if t:
                                    text = t
                                    break
                    except Exception:
                        pass

                    # Fallback: some messages expose `content` as a list of dicts
                    if not text:
                        try:
                            content = getattr(m, "content", None)
                            if isinstance(content, list | tuple):
                                for item in content:
                                    if (
                                        isinstance(item, dict)
                                        and item.get("type") == "text"
                                        and item.get("text")
                                    ):
                                        text = item.get("text")
                                        break
                        except Exception:
                            pass

                    if text:
                        final_text = text

        # If streaming finished and we have no assistant text, try run() fallback
        if not final_text:
            try:
                resp = playtomic_agent.run({"messages": messages})
                # resp may be a dict with 'messages', a list of messages, or an object
                msgs = None
                if isinstance(resp, dict):
                    msgs = resp.get("messages", [])
                elif isinstance(resp, list | tuple):
                    msgs = resp
                elif hasattr(resp, "messages"):
                    msgs = resp.messages

                if msgs:
                    for m in reversed(msgs):
                        # Skip tool messages in the fallback too
                        if getattr(m, "tool_call_id", None) is not None:
                            continue

                        text = None
                        try:
                            cbs = getattr(m, "content_blocks", None)
                            if cbs:
                                for cb in cbs:
                                    t = getattr(cb, "text", None)
                                    if t:
                                        text = t
                                        break
                        except Exception:
                            pass

                        if not text:
                            try:
                                content = getattr(m, "content", None)
                                if isinstance(content, list | tuple):
                                    for item in content:
                                        if (
                                            isinstance(item, dict)
                                            and item.get("type") == "text"
                                            and item.get("text")
                                        ):
                                            text = item.get("text")
                                            break
                            except Exception:
                                pass

                        if text:
                            final_text = text
                            break
            except Exception:
                # ignore fallback errors
                pass

    except Exception as exc:  # pragma: no cover - runtime dependent
        raise HTTPException(status_code=500, detail=f"Agent execution error: {exc}") from exc

    if not final_text:
        raise HTTPException(status_code=500, detail="Agent did not return an assistant response.")

    return ChatResponse(text=final_text)
