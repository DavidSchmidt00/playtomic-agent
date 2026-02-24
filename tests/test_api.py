from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from playtomic_agent.web.api import app

client = TestClient(app, raise_server_exceptions=False)


def test_chat_agent_unavailable():
    # If create_playtomic_agent raises an error (e.g. missing config), API should return 500
    with patch(
        "playtomic_agent.web.api.create_playtomic_agent", side_effect=ValueError("Config missing")
    ):
        res = client.post("/api/chat", json={"prompt": "Test prompt"})
        assert res.status_code == 500


def test_accepts_assistant_messages_without_role():
    # Simulate an assistant message that does NOT include a `role` attribute but
    # exposes `content` as a list of dicts (like some model outputs).
    class DummyMsg:
        def __init__(self, text):
            self.content = [{"type": "text", "text": text}]
            self.tool_calls = []  # Agent adds this check
            self.tool_call_id = None
            self.type = "ai"

    sample_text = "Hello from the assistant without a role"
    chunks = [{"model": {"messages": [DummyMsg(sample_text)]}}]

    async def fake_astream(*args, **kwargs):
        for chunk in chunks:
            yield chunk

    mock_agent = MagicMock()
    mock_agent.astream = fake_astream

    with patch("playtomic_agent.web.api.create_playtomic_agent", return_value=mock_agent):
        res = client.post("/api/chat", json={"prompt": "Test prompt"})
        assert res.status_code == 200
        # The API streams events. We need to parse the SSE or check the raw text.
        # client.post reads the response. res.text will contain "data: ...".
        assert sample_text in res.text


def test_chat_with_message_history():
    """The agent should receive the full conversation history (truncated) when messages are sent."""

    class DummyMsg:
        def __init__(self, text):
            self.content = [{"type": "text", "text": text}]
            self.tool_calls = []
            self.tool_call_id = None
            self.type = "ai"  # needed for is_ai check

    captured_args: list = []

    async def fake_astream(input_data, *args, **kwargs):
        captured_args.append(input_data)
        yield {"model": {"messages": [DummyMsg("Follow-up answer")]}}

    mock_agent = MagicMock()
    mock_agent.astream = fake_astream

    with patch("playtomic_agent.web.api.create_playtomic_agent", return_value=mock_agent):
        history = [{"role": "user", "content": f"msg {i}"} for i in range(25)]

        res = client.post("/api/chat", json={"messages": history})

        assert res.status_code == 200
        assert "Follow-up answer" in res.text

        # Verify truncation
        assert len(captured_args) == 1
        passed_messages = captured_args[0]["messages"]
        assert len(passed_messages) == 20
        assert passed_messages[-1]["content"] == "msg 24"


def test_chat_missing_prompt_and_messages():
    """Should return 400 when neither prompt nor messages is provided."""
    res = client.post("/api/chat", json={})
    assert res.status_code == 400
