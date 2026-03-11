import os
import sqlite3

import pytest

from playtomic_agent.whatsapp.storage import UserState, UserStorage


@pytest.fixture
def storage(tmp_path):
    return UserStorage(str(tmp_path / "users.db"))


def test_load_unknown_sender_returns_empty_state(storage):
    state = storage.load("+4912345678")
    assert state.profile == {}
    assert state.history == []
    assert state.language == ""


def test_save_and_load_roundtrip(storage):
    state = UserState(
        profile={"preferred_club_slug": "lemon-padel-club"},
        history=[{"role": "user", "content": "hello"}],
        language="de",
    )
    storage.save("+4912345678", state)

    loaded = storage.load("+4912345678")
    assert loaded.profile == {"preferred_club_slug": "lemon-padel-club"}
    assert loaded.history == [{"role": "user", "content": "hello"}]
    assert loaded.language == "de"


def test_multiple_senders_isolated(storage):
    storage.save("+1111", UserState(profile={"city": "Berlin"}))
    storage.save("+2222", UserState(profile={"city": "Munich"}))

    assert storage.load("+1111").profile["city"] == "Berlin"
    assert storage.load("+2222").profile["city"] == "Munich"


def test_overwrite_existing_sender(storage):
    storage.save("+4912345678", UserState(profile={"city": "Berlin"}))
    storage.save("+4912345678", UserState(profile={"city": "Hamburg"}))

    assert storage.load("+4912345678").profile["city"] == "Hamburg"


def test_load_from_new_db_returns_empty(tmp_path):
    """A freshly created DB always returns empty state for any sender."""
    storage = UserStorage(str(tmp_path / "fresh.db"))
    assert storage.load("+4912345678").profile == {}


def test_creates_parent_directory(tmp_path):
    nested_path = str(tmp_path / "subdir" / "nested" / "users.db")
    storage = UserStorage(nested_path)
    storage.save("+111", UserState())
    assert os.path.exists(nested_path)


def test_wal_mode_enabled(tmp_path):
    db_path = str(tmp_path / "users.db")
    UserStorage(db_path)
    conn = sqlite3.connect(db_path)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    conn.close()
    assert mode == "wal"


def test_active_poll_roundtrip(storage):
    state = UserState(
        active_poll={"message_id": "abc123", "question": "Slot?", "options": []},
        poll_count=1,
    )
    storage.save("+123", state)
    loaded = storage.load("+123")
    assert loaded.active_poll == {"message_id": "abc123", "question": "Slot?", "options": []}
    assert loaded.poll_count == 1


def test_null_active_poll_roundtrip(storage):
    state = UserState(active_poll=None)
    storage.save("+123", state)
    loaded = storage.load("+123")
    assert loaded.active_poll is None
