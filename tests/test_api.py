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
