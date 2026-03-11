from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from playtomic_agent.client.exceptions import APIError, ClubNotFoundError
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


# ─── /api/search tests ────────────────────────────────────────────────────────

_BASE_SEARCH_BODY = {
    "club_slug": "test-club",
    "date_from": "2026-03-09",  # Monday
    "date_to": "2026-03-09",
    "time_windows": [{"days": [0], "start": "18:00", "end": "22:00"}],
    "timezone": "Europe/Berlin",
}


def _make_mock_client(slots):
    """Return a patched PlaytomicClient context manager that returns *slots* from find_slots."""
    MockClient = MagicMock()
    mock_instance = MagicMock()
    mock_instance.find_slots.return_value = slots
    MockClient.return_value.__enter__.return_value = mock_instance
    MockClient.return_value.__exit__.return_value = False
    return MockClient


def test_search_happy_path(sample_slots):
    """Monday date + Monday window → returns slots with booking links."""
    MockClient = _make_mock_client(sample_slots)

    with patch("playtomic_agent.web.api.PlaytomicClient", MockClient):
        res = client.post("/api/search", json=_BASE_SEARCH_BODY)

    assert res.status_code == 200
    data = res.json()
    assert data["total_count"] == len(sample_slots)
    assert data["dates_checked"] == 1
    for slot in data["results"]:
        assert "booking_link" in slot
        assert slot["booking_link"].startswith("http")
        assert "day_label" not in slot


def test_search_no_matching_weekday(sample_slots):
    """Monday date + Saturday-only window → no results, dates_checked == 0."""
    body = {**_BASE_SEARCH_BODY, "time_windows": [{"days": [5], "start": "14:00", "end": "20:00"}]}
    MockClient = _make_mock_client(sample_slots)

    with patch("playtomic_agent.web.api.PlaytomicClient", MockClient):
        res = client.post("/api/search", json=body)

    assert res.status_code == 200
    data = res.json()
    assert data["total_count"] == 0
    assert data["dates_checked"] == 0


def test_search_club_not_found():
    """find_slots raising ClubNotFoundError → 404."""
    MockClient = MagicMock()
    mock_instance = MagicMock()
    mock_instance.find_slots.side_effect = ClubNotFoundError("test-club", "slug")
    MockClient.return_value.__enter__.return_value = mock_instance
    MockClient.return_value.__exit__.return_value = False

    with patch("playtomic_agent.web.api.PlaytomicClient", MockClient):
        res = client.post("/api/search", json=_BASE_SEARCH_BODY)

    assert res.status_code == 404


def test_search_api_error():
    """find_slots raising APIError → 502."""
    MockClient = MagicMock()
    mock_instance = MagicMock()
    mock_instance.find_slots.side_effect = APIError("Upstream failure")
    MockClient.return_value.__enter__.return_value = mock_instance
    MockClient.return_value.__exit__.return_value = False

    with patch("playtomic_agent.web.api.PlaytomicClient", MockClient):
        res = client.post("/api/search", json=_BASE_SEARCH_BODY)

    assert res.status_code == 502


def test_search_date_range_too_large():
    """Date range > 14 days → 422, no mock needed."""
    body = {**_BASE_SEARCH_BODY, "date_from": "2026-03-01", "date_to": "2026-03-20"}
    res = client.post("/api/search", json=body)
    assert res.status_code == 422
    assert "14 days" in res.json()["detail"]


def test_search_date_to_before_date_from():
    """date_to < date_from → 422."""
    body = {**_BASE_SEARCH_BODY, "date_from": "2026-03-10", "date_to": "2026-03-09"}
    res = client.post("/api/search", json=body)
    assert res.status_code == 422
    assert "date_to" in res.json()["detail"]


def test_search_empty_time_windows():
    """Empty time_windows list → 422."""
    body = {**_BASE_SEARCH_BODY, "time_windows": []}
    res = client.post("/api/search", json=body)
    assert res.status_code == 422
    assert "time_window" in res.json()["detail"]


def test_search_results_sorted(sample_slots):
    """Results from multiple dates are sorted ascending by (date, local_time)."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from playtomic_agent.models import Slot

    # Two slots on different dates: slot B comes before slot A in API order
    slot_a = Slot(
        club_id="c1",
        court_id="court-1",
        court_name="Court 1",
        time=datetime(2026, 3, 10, 17, 0, 0, tzinfo=ZoneInfo("UTC")),  # Tuesday 18:00 Berlin
        duration=90,
        price="20.00 EUR",
    )
    slot_b = Slot(
        club_id="c1",
        court_id="court-1",
        court_name="Court 1",
        time=datetime(2026, 3, 9, 18, 0, 0, tzinfo=ZoneInfo("UTC")),  # Monday 19:00 Berlin
        duration=90,
        price="20.00 EUR",
    )

    call_count = 0

    def find_slots_side_effect(**kwargs):
        nonlocal call_count
        call_count += 1
        # First call = Monday, second call = Tuesday
        return [slot_b] if call_count == 1 else [slot_a]

    MockClient = MagicMock()
    mock_instance = MagicMock()
    mock_instance.find_slots.side_effect = find_slots_side_effect
    MockClient.return_value.__enter__.return_value = mock_instance
    MockClient.return_value.__exit__.return_value = False

    body = {
        **_BASE_SEARCH_BODY,
        "date_from": "2026-03-09",  # Monday
        "date_to": "2026-03-10",  # Tuesday
        "time_windows": [{"days": [0, 1], "start": "18:00", "end": "22:00"}],
    }

    with patch("playtomic_agent.web.api.PlaytomicClient", MockClient):
        res = client.post("/api/search", json=body)

    assert res.status_code == 200
    data = res.json()
    assert data["total_count"] == 2
    dates = [r["date"] for r in data["results"]]
    assert dates == sorted(dates), "Results should be sorted by date ascending"


# ─── /api/clubs tests ─────────────────────────────────────────────────────────


def _make_mock_clubs_client(clubs):
    """Return a patched PlaytomicClient that returns *clubs* from search_clubs."""
    MockClient = MagicMock()
    mock_instance = MagicMock()
    mock_instance.search_clubs.return_value = clubs
    MockClient.return_value.__enter__.return_value = mock_instance
    MockClient.return_value.__exit__.return_value = False
    return MockClient


def test_clubs_happy_path():
    """Query with 2+ chars returns matching clubs as name/slug pairs."""
    c1 = MagicMock()
    c1.name = "Lemon Padel Club"
    c1.slug = "lemon-padel-club"
    c2 = MagicMock()
    c2.name = "Lemon Indoor"
    c2.slug = "lemon-indoor"
    MockClient = _make_mock_clubs_client([c1, c2])

    with patch("playtomic_agent.web.api.PlaytomicClient", MockClient):
        res = client.get("/api/clubs?q=lemon")

    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2
    assert data[0] == {"name": "Lemon Padel Club", "slug": "lemon-padel-club"}


def test_clubs_short_query_returns_empty():
    """Query shorter than 2 chars returns [] without calling Playtomic."""
    res = client.get("/api/clubs?q=l")
    assert res.status_code == 200
    assert res.json() == []


def test_clubs_api_error_returns_502():
    """Upstream APIError is mapped to 502."""
    MockClient = MagicMock()
    mock_instance = MagicMock()
    mock_instance.search_clubs.side_effect = APIError("Upstream down")
    MockClient.return_value.__enter__.return_value = mock_instance
    MockClient.return_value.__exit__.return_value = False

    with patch("playtomic_agent.web.api.PlaytomicClient", MockClient):
        res = client.get("/api/clubs?q=lemon")

    assert res.status_code == 502


def test_metrics_endpoint_returns_200():
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "playtomic_api_requests_total" in resp.text
