from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from playtomic_agent.web.api import app
from playtomic_agent.web.vote_store import InvalidSlotError, SessionNotFoundError

client = TestClient(app)

_SAMPLE_SLOTS = [
    {
        "slot_id": "s1",
        "date": "2026-03-10",
        "local_time": "19:00",
        "court": "Court A",
        "court_type": "DOUBLE",
        "duration": 90,
        "price": "€20.00",
        "booking_link": "https://x/1",
    },
    {
        "slot_id": "s2",
        "date": "2026-03-10",
        "local_time": "20:00",
        "court": "Court B",
        "court_type": "SINGLE",
        "duration": 60,
        "price": "€15.00",
        "booking_link": "https://x/2",
    },
]

_MOCK_SESSION = {
    "vote_id": "testvote",
    "slots": _SAMPLE_SLOTS,
    "tally": {"s1": 0, "s2": 0},
    "voter_count": 0,
    "voters": [],
    "attendees": {"s1": [], "s2": []},
}


def _mock_store(vote_id="testvote", session=_MOCK_SESSION):
    m = MagicMock()
    m.create.return_value = vote_id
    m.get.return_value = session
    m.record_vote.return_value = {**session, "tally": {"s1": 1, "s2": 0}, "voter_count": 1}
    return m


def _patched(mock):
    """Patch both _vote_store and _get_vote_store so lazy init returns the mock."""
    return patch("playtomic_agent.web.api._vote_store", mock)


def test_create_vote_session_201():
    with _patched(_mock_store()):
        res = client.post("/api/votes", json={"slots": _SAMPLE_SLOTS})
    assert res.status_code == 201
    data = res.json()
    assert data["vote_id"] == "testvote"
    assert data["url"] == "/vote/testvote"


def test_create_vote_session_missing_slots():
    res = client.post("/api/votes", json={})
    assert res.status_code == 422


def test_get_vote_session_200():
    with _patched(_mock_store()):
        res = client.get("/api/votes/testvote")
    assert res.status_code == 200
    data = res.json()
    assert data["vote_id"] == "testvote"
    assert len(data["slots"]) == 2
    assert "tally" in data
    assert "voter_count" in data


def test_get_vote_session_404():
    m = MagicMock()
    m.get.return_value = None
    with _patched(m):
        res = client.get("/api/votes/nosuchid")
    assert res.status_code == 404


_VOTES_PAYLOAD = [{"slot_id": "s1", "can_attend": True}, {"slot_id": "s2", "can_attend": False}]


def test_cast_vote_200():
    with _patched(_mock_store()):
        res = client.post(
            "/api/votes/testvote/vote", json={"voter_name": "Alice", "votes": _VOTES_PAYLOAD}
        )
    assert res.status_code == 200
    data = res.json()
    assert data["tally"]["s1"] == 1
    assert data["voter_count"] == 1


def test_cast_vote_invalid_slot_422():
    m = MagicMock()
    m.record_vote.side_effect = InvalidSlotError("Invalid slot_id")
    with _patched(m):
        res = client.post(
            "/api/votes/testvote/vote",
            json={"voter_name": "Alice", "votes": [{"slot_id": "bad", "can_attend": True}]},
        )
    assert res.status_code == 422


def test_cast_vote_session_not_found_404():
    m = MagicMock()
    m.record_vote.side_effect = SessionNotFoundError("not found or expired")
    with _patched(m):
        res = client.post(
            "/api/votes/missing/vote", json={"voter_name": "Alice", "votes": _VOTES_PAYLOAD}
        )
    assert res.status_code == 404


def test_cast_vote_blank_name_422():
    with _patched(_mock_store()):
        res = client.post(
            "/api/votes/testvote/vote", json={"voter_name": "   ", "votes": _VOTES_PAYLOAD}
        )
    assert res.status_code == 422


# --- Per-slot threshold tests (WEB-6) ---

_SESSION_WITH_GROUP = {
    **_MOCK_SESSION,
    "metadata": {"group_jid": "123@g.us"},
    "notified_slots": [],
}


def _after_vote(tally: dict) -> dict:
    return {**_SESSION_WITH_GROUP, "tally": tally, "voter_count": sum(tally.values())}


def test_single_slot_fires_webhook_at_2_votes():
    """SINGLE court slot (s2) triggers consensus notification at exactly 2 votes."""
    m = _mock_store(session=_SESSION_WITH_GROUP)
    m.record_vote.return_value = _after_vote({"s1": 0, "s2": 2})
    with _patched(m), patch("playtomic_agent.web.api._fire_webhook") as mock_wh:
        res = client.post(
            "/api/votes/testvote/vote",
            json={"voter_name": "Bob", "votes": [{"slot_id": "s2", "can_attend": True}]},
        )
    assert res.status_code == 200
    mock_wh.assert_called_once()
    _, payload = mock_wh.call_args[0]
    assert payload["vote_id"] == "testvote"


def test_double_slot_no_webhook_at_2_votes():
    """DOUBLE court slot (s1) does NOT trigger at 2 votes — threshold is 4."""
    m = _mock_store(session=_SESSION_WITH_GROUP)
    m.record_vote.return_value = _after_vote({"s1": 2, "s2": 0})
    with _patched(m), patch("playtomic_agent.web.api._fire_webhook") as mock_wh:
        res = client.post(
            "/api/votes/testvote/vote",
            json={"voter_name": "Bob", "votes": [{"slot_id": "s1", "can_attend": True}]},
        )
    assert res.status_code == 200
    mock_wh.assert_not_called()


def test_mixed_session_single_fires_double_does_not():
    """Mixed session at 2 votes each: SINGLE fires, DOUBLE does not."""
    m = _mock_store(session=_SESSION_WITH_GROUP)
    m.record_vote.return_value = _after_vote({"s1": 2, "s2": 2})
    with _patched(m), patch("playtomic_agent.web.api._fire_webhook") as mock_wh:
        res = client.post(
            "/api/votes/testvote/vote",
            json={
                "voter_name": "Bob",
                "votes": [
                    {"slot_id": "s1", "can_attend": True},
                    {"slot_id": "s2", "can_attend": True},
                ],
            },
        )
    assert res.status_code == 200
    # Only s2 (SINGLE) should fire; s1 (DOUBLE) needs 4 votes
    assert mock_wh.call_count == 1
    _, payload = mock_wh.call_args[0]
    assert payload["booking_link"] == "https://x/2"  # s2's booking link
