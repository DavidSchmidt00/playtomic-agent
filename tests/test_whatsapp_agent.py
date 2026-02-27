"""Tests for WhatsApp agent helper functions and send_poll tool."""

import json
from unittest.mock import MagicMock

from playtomic_agent.whatsapp.agent import (
    extract_final_text,
    extract_poll_data,
    extract_preference_updates,
    send_poll,
)

# ---------------------------------------------------------------------------
# send_poll tool
# ---------------------------------------------------------------------------

_SLOT_A = {"display": "Mo | 01.03 | 18:00 | 90", "booking_link": "https://x"}
_SLOT_B = {"display": "Mo | 01.03 | 19:30 | 60", "booking_link": "https://y"}


def test_send_poll_returns_wa_poll():
    slots = [_SLOT_A, _SLOT_B]
    result = send_poll.invoke({"question": "Welcher Slot?", "slots": slots})
    assert "wa_poll" in result
    assert result["wa_poll"]["question"] == "Welcher Slot?"
    assert result["wa_poll"]["slots"] == slots


def test_send_poll_default_court_type_is_double():
    result = send_poll.invoke({"question": "Slot?", "slots": [_SLOT_A]})
    assert result["wa_poll"]["court_type"] == "DOUBLE"


def test_send_poll_single_court_type():
    result = send_poll.invoke({"question": "Slot?", "slots": [_SLOT_A], "court_type": "SINGLE"})
    assert result["wa_poll"]["court_type"] == "SINGLE"


def test_send_poll_limits_to_12():
    slots = [{"display": f"Mo | 01.03 | {i:02d}:00 | 60", "booking_link": ""} for i in range(15)]
    result = send_poll.invoke({"question": "Pick?", "slots": slots})
    assert len(result["wa_poll"]["slots"]) == 12


# ---------------------------------------------------------------------------
# extract_final_text
# ---------------------------------------------------------------------------


def _make_ai_msg(text: str, tool_calls=None):
    m = MagicMock()
    m.__class__.__name__ = "AIMessage"
    m.type = "ai"
    m.content = text
    m.tool_calls = tool_calls or []
    m.tool_call_id = None
    return m


def test_extract_final_text_returns_last_ai_message():
    result = {
        "messages": [
            _make_ai_msg("First response"),
            _make_ai_msg("Second response"),
        ]
    }
    assert extract_final_text(result) == "Second response"


def test_extract_final_text_skips_tool_call_messages():
    tool_call_msg = _make_ai_msg("", tool_calls=[{"name": "find_slots"}])
    final_msg = _make_ai_msg("Here are your slots!")
    result = {"messages": [tool_call_msg, final_msg]}
    assert extract_final_text(result) == "Here are your slots!"


def test_extract_final_text_handles_list_content():
    m = MagicMock()
    m.__class__.__name__ = "AIMessage"
    m.type = "ai"
    m.content = [{"type": "text", "text": "Hello from list content"}]
    m.tool_calls = []
    m.tool_call_id = None
    result = {"messages": [m]}
    assert extract_final_text(result) == "Hello from list content"


def test_extract_final_text_empty_result():
    assert extract_final_text({"messages": []}) == ""


# ---------------------------------------------------------------------------
# extract_poll_data
# ---------------------------------------------------------------------------


def _make_tool_msg(name: str, content):
    m = MagicMock()
    m.name = name
    m.tool_call_id = "tc_123"
    m.content = json.dumps(content) if not isinstance(content, str) else content
    return m


def test_extract_poll_data_finds_wa_poll():
    poll_payload = {
        "wa_poll": {"question": "Welcher Slot?", "slots": [_SLOT_A], "court_type": "DOUBLE"}
    }
    result = {"messages": [_make_tool_msg("send_poll", poll_payload)]}
    poll = extract_poll_data(result)
    assert poll is not None
    assert poll["question"] == "Welcher Slot?"
    assert poll["slots"] == [_SLOT_A]
    assert poll["court_type"] == "DOUBLE"


def test_extract_poll_data_returns_none_when_absent():
    result = {"messages": [_make_tool_msg("find_slots", {"count": 0, "slots": []})]}
    assert extract_poll_data(result) is None


# ---------------------------------------------------------------------------
# extract_preference_updates
# ---------------------------------------------------------------------------


def test_extract_preference_updates_finds_profile_update():
    payload = {"profile_update": {"key": "preferred_city", "value": "Berlin"}}
    result = {"messages": [_make_tool_msg("update_user_profile", payload)]}
    updates = extract_preference_updates(result)
    assert updates == {"preferred_city": "Berlin"}


def test_extract_preference_updates_merges_multiple():
    result = {
        "messages": [
            _make_tool_msg(
                "update_user_profile",
                {"profile_update": {"key": "preferred_club_slug", "value": "lemon"}},
            ),
            _make_tool_msg(
                "update_user_profile",
                {"profile_update": {"key": "preferred_club_name", "value": "Lemon Padel"}},
            ),
        ]
    }
    updates = extract_preference_updates(result)
    assert updates == {"preferred_club_slug": "lemon", "preferred_club_name": "Lemon Padel"}


def test_extract_preference_updates_ignores_other_tools():
    result = {"messages": [_make_tool_msg("find_slots", {"count": 0})]}
    assert extract_preference_updates(result) == {}
