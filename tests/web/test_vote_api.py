from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from playtomic_agent.web.api import app

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
}


def _mock_store(vote_id="testvote", session=_MOCK_SESSION):
    m = MagicMock()
    m.create.return_value = vote_id
    m.get.return_value = session
    m.record_vote.return_value = {**session, "tally": {"s1": 1, "s2": 0}, "voter_count": 1}
    return m


def test_create_vote_session_201():
    with patch("playtomic_agent.web.api._vote_store", _mock_store()):
        res = client.post("/api/votes", json={"slots": _SAMPLE_SLOTS})
    assert res.status_code == 201
    data = res.json()
    assert data["vote_id"] == "testvote"
    assert data["url"] == "/vote/testvote"


def test_create_vote_session_missing_slots():
    res = client.post("/api/votes", json={})
    assert res.status_code == 422


def test_get_vote_session_200():
    with patch("playtomic_agent.web.api._vote_store", _mock_store()):
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
    with patch("playtomic_agent.web.api._vote_store", m):
        res = client.get("/api/votes/nosuchid")
    assert res.status_code == 404


def test_cast_vote_200():
    with patch("playtomic_agent.web.api._vote_store", _mock_store()):
        res = client.post("/api/votes/testvote/vote", json={"voter_name": "Alice", "slot_id": "s1"})
    assert res.status_code == 200
    data = res.json()
    assert data["tally"]["s1"] == 1
    assert data["voter_count"] == 1


def test_cast_vote_invalid_slot_404():
    m = MagicMock()
    m.record_vote.side_effect = ValueError("Invalid slot_id")
    with patch("playtomic_agent.web.api._vote_store", m):
        res = client.post(
            "/api/votes/testvote/vote", json={"voter_name": "Alice", "slot_id": "bad"}
        )
    assert res.status_code == 404


def test_cast_vote_session_not_found_404():
    m = MagicMock()
    m.record_vote.side_effect = ValueError("not found or expired")
    with patch("playtomic_agent.web.api._vote_store", m):
        res = client.post("/api/votes/missing/vote", json={"voter_name": "Alice", "slot_id": "s1"})
    assert res.status_code == 404
