from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from playtomic_agent.api import app

client = TestClient(app, raise_server_exceptions=False)


def test_chat_agent_unavailable():
    # If create_playtomic_agent raises an error (e.g. missing config), API should return 500
    with patch("playtomic_agent.api.create_playtomic_agent", side_effect=ValueError("Config missing")):
        res = client.post("/api/chat", json={"prompt": "Test prompt"})
        assert res.status_code == 500


def test_accepts_assistant_messages_without_role():
    # Simulate an assistant message that does NOT include a `role` attribute but
    # exposes `content` as a list of dicts (like some model outputs).
    class DummyMsg:
        def __init__(self, text):
            self.content = [{"type": "text", "text": text}]
            self.tool_calls = [] # Agent adds this check
            self.tool_call_id = None
            self.type = "ai"

    sample_text = "Hello from the assistant without a role"

    # Mock the agent and its stream method
    mock_agent = MagicMock()
    # The stream yields chunks. Each chunk is a dict {node: state}.
    # The state has "messages".
    mock_agent.stream.return_value = [
        {"model": {"messages": [DummyMsg(sample_text)]}}
    ]

    with patch("playtomic_agent.api.create_playtomic_agent", return_value=mock_agent):
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
            self.type = "ai" # needed for is_ai check

    # Mock agent
    mock_agent = MagicMock()
    mock_agent.stream.return_value = [
         {"model": {"messages": [DummyMsg("Follow-up answer")]}}
    ]

    with patch("playtomic_agent.api.create_playtomic_agent", return_value=mock_agent) as mock_create:
        history = [{"role": "user", "content": f"msg {i}"} for i in range(25)]
        
        res = client.post("/api/chat", json={"messages": history})

        assert res.status_code == 200
        assert "Follow-up answer" in res.text
        
        # Verify call args to agent.stream
        # mock_create returned mock_agent. 
        # api.py calls: agent.stream({"messages": messages}, ...)
        
        call_args = mock_agent.stream.call_args
        assert call_args is not None
        input_data = call_args[0][0] # first arg
        passed_messages = input_data["messages"]
        
        # Verify truncation (My new feature!)
        assert len(passed_messages) == 20
        assert passed_messages[-1]["content"] == "msg 24"


def test_chat_missing_prompt_and_messages():
    """Should return 400 when neither prompt nor messages is provided."""
    res = client.post("/api/chat", json={})
    assert res.status_code == 400

