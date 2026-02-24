import os

import pytest
from playtomic_agent.whatsapp.storage import UserState, UserStorage


@pytest.fixture
def storage(tmp_path):
    return UserStorage(str(tmp_path / "users.json"))


def test_load_unknown_sender_returns_empty_state(storage):
    state = storage.load("+4912345678")
    assert state.profile == {}
    assert state.history == []
    assert state.language == "en"


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


def test_corrupted_file_returns_empty(tmp_path):
    path = str(tmp_path / "users.json")
    with open(path, "w") as f:
        f.write("not valid json{{{")

    storage = UserStorage(path)
    state = storage.load("+4912345678")
    assert state.profile == {}


def test_creates_parent_directory(tmp_path):
    nested_path = str(tmp_path / "subdir" / "nested" / "users.json")
    storage = UserStorage(nested_path)
    storage.save("+111", UserState())
    assert os.path.exists(nested_path)
