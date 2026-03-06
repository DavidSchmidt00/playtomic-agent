import datetime

import pytest

from playtomic_agent.web.vote_store import VoteSlot, VoteStore

_SLOT_A = VoteSlot(
    slot_id="s1",
    date="2026-03-10",
    local_time="19:00",
    court="Court A",
    court_type="DOUBLE",
    duration=90,
    price="€20.00",
    booking_link="https://x/1",
)
_SLOT_B = VoteSlot(
    slot_id="s2",
    date="2026-03-10",
    local_time="20:00",
    court="Court B",
    court_type="SINGLE",
    duration=60,
    price="€15.00",
    booking_link="https://x/2",
)


@pytest.fixture
def store(tmp_path):
    return VoteStore(db_path=tmp_path / "votes.db")


def test_create_returns_8_char_id(store):
    vote_id = store.create([_SLOT_A, _SLOT_B])
    assert len(vote_id) == 8
    assert vote_id.isalnum()


def test_get_returns_session_with_slots(store):
    vote_id = store.create([_SLOT_A, _SLOT_B])
    session = store.get(vote_id)
    assert session is not None
    assert len(session["slots"]) == 2
    assert session["slots"][0]["slot_id"] == "s1"
    assert session["slots"][0]["court_type"] == "DOUBLE"


def test_get_missing_returns_none(store):
    assert store.get("notexist") is None


def test_tally_starts_empty(store):
    vote_id = store.create([_SLOT_A])
    session = store.get(vote_id)
    assert session["tally"]["s1"] == 0


def test_record_vote_counts_can_attend(store):
    vote_id = store.create([_SLOT_A, _SLOT_B])
    store.record_vote(vote_id, "Alice", {"s1": True, "s2": False})
    store.record_vote(vote_id, "Bob", {"s1": True, "s2": True})
    store.record_vote(vote_id, "Carol", {"s1": False, "s2": True})
    session = store.get(vote_id)
    assert session["tally"]["s1"] == 2  # Alice + Bob
    assert session["tally"]["s2"] == 2  # Bob + Carol
    assert session["voter_count"] == 3


def test_record_vote_replaces_previous(store):
    vote_id = store.create([_SLOT_A, _SLOT_B])
    store.record_vote(vote_id, "Alice", {"s1": True, "s2": False})
    store.record_vote(vote_id, "Alice", {"s1": False, "s2": True})  # change mind
    session = store.get(vote_id)
    assert session["tally"]["s1"] == 0
    assert session["tally"]["s2"] == 1
    assert session["voter_count"] == 1


def test_record_vote_invalid_slot_raises(store):
    vote_id = store.create([_SLOT_A])
    with pytest.raises(ValueError, match="Invalid slot_id"):
        store.record_vote(vote_id, "Alice", {"bad-slot": True})


def test_record_vote_session_not_found_raises(store):
    with pytest.raises(ValueError, match="not found or expired"):
        store.record_vote("nobody", "Alice", {"s1": True})


def test_session_expires(store):
    past_date = (datetime.date.today() - datetime.timedelta(days=2)).isoformat()
    past_slot = VoteSlot(
        slot_id="s9",
        date=past_date,
        local_time="19:00",
        court="Court X",
        court_type="DOUBLE",
        duration=90,
        price="€20",
        booking_link="u",
    )
    vote_id = store.create([past_slot])
    assert store.get(vote_id) is None


def test_persists_across_store_instances(tmp_path):
    path = tmp_path / "votes.db"
    vote_id = VoteStore(db_path=path).create([_SLOT_A])
    VoteStore(db_path=path).record_vote(vote_id, "Alice", {"s1": True})
    session = VoteStore(db_path=path).get(vote_id)
    assert session["tally"]["s1"] == 1
