from fastapi.testclient import TestClient
from playtomic_agent.api import app

client = TestClient(app)


def test_chat_agent_unavailable():
    # In the CI/dev environment where model libs are not installed the API should return 503
    res = client.post("/api/chat", json={"prompt": "Test prompt"})
    assert res.status_code in (503, 500)


def test_accepts_assistant_messages_without_role(monkeypatch):
    # Simulate an assistant message that does NOT include a `role` attribute but
    # exposes `content` as a list of dicts (like some model outputs).
    class DummyMsg:
        def __init__(self, text):
            self.content = [{"type": "text", "text": text}]

    sample_text = "Hello from the assistant without a role"

    def fake_stream(*args, **kwargs):
        yield {"model": {"messages": [DummyMsg(sample_text)]}}

    monkeypatch.setattr("playtomic_agent.api.playtomic_agent.stream", fake_stream)

    res = client.post("/api/chat", json={"prompt": "Test prompt"})
    assert res.status_code == 200
    assert sample_text in res.json()["text"]


def test_chat_with_message_history(monkeypatch):
    """The agent should receive the full conversation history when messages are sent."""

    class DummyMsg:
        def __init__(self, text):
            self.content = [{"type": "text", "text": text}]

    captured_input = {}

    def fake_stream(input_data, **kwargs):
        captured_input["messages"] = input_data["messages"]
        yield {"model": {"messages": [DummyMsg("Follow-up answer")]}}

    monkeypatch.setattr("playtomic_agent.api.playtomic_agent.stream", fake_stream)

    history = [
        {"role": "user", "content": "Find a court at lemon-padel-club"},
        {"role": "assistant", "content": "Found a court at 20:00."},
        {"role": "user", "content": "Find the next slot"},
    ]
    res = client.post("/api/chat", json={"messages": history})

    assert res.status_code == 200
    assert res.json()["text"] == "Follow-up answer"
    # Verify all 3 messages were forwarded to the agent
    assert len(captured_input["messages"]) == 3
    assert captured_input["messages"][0]["content"] == "Find a court at lemon-padel-club"
    assert captured_input["messages"][2]["content"] == "Find the next slot"


def test_chat_missing_prompt_and_messages():
    """Should return 400 when neither prompt nor messages is provided."""
    res = client.post("/api/chat", json={})
    assert res.status_code == 400

