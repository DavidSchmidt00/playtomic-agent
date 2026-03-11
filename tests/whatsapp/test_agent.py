"""Tests for the WhatsApp agent: respond tool, extract_response, update_user_profile."""

import json
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from playtomic_agent.whatsapp.agent import (
    WAPoll,
    WAResponse,
    WAVoteLink,
    _wa_state_ctx,
    extract_final_text,
    extract_response,
    respond,
    set_wa_invocation_state,
    update_user_profile,
)
from playtomic_agent.whatsapp.storage import UserState

_SLOT_A = {
    "display": "Mo | 01.03 | 18:00 | 90 min",
    "date": "2026-03-01",
    "local_time": "18:00",
    "court": "Court 1",
    "court_type": "DOUBLE",
    "duration": 90,
    "price": "20.00 EUR",
    "booking_link": "https://x",
}
_SLOT_B = {
    "display": "Mo | 01.03 | 19:30 | 60 min",
    "date": "2026-03-01",
    "local_time": "19:30",
    "court": "Court 2",
    "court_type": "DOUBLE",
    "duration": 60,
    "price": "15.00 EUR",
    "booking_link": "https://y",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ai_msg(text: str, tool_calls=None):
    m = MagicMock()
    m.__class__.__name__ = "AIMessage"
    m.type = "ai"
    m.content = text
    m.tool_calls = tool_calls or []
    m.tool_call_id = None
    return m


def _make_tool_msg(name: str, content: object) -> MagicMock:
    m = MagicMock()
    m.name = name
    m.tool_call_id = "tc_123"
    m.content = json.dumps(content) if not isinstance(content, str) else content
    return m


# ---------------------------------------------------------------------------
# respond tool
# ---------------------------------------------------------------------------


def test_respond_text_only():
    result = respond.invoke({"response": WAResponse(text_parts=["Hello", "World"])})
    assert result["text_parts"] == ["Hello", "World"]
    assert result["poll"] is None
    assert result["vote_link"] is None


def test_respond_with_poll():
    poll = WAPoll(question="Welcher Slot?", slots=[_SLOT_A, _SLOT_B])
    result = respond.invoke({"response": WAResponse(text_parts=["Hier die Auswahl:"], poll=poll)})
    assert result["poll"]["question"] == "Welcher Slot?"
    assert result["poll"]["court_type"] == "DOUBLE"
    assert result["vote_link"] is None


def test_respond_with_vote_link():
    vl = WAVoteLink(question="Vote!", slots=[_SLOT_A, _SLOT_B], court_type="SINGLE")
    result = respond.invoke({"response": WAResponse(vote_link=vl)})
    assert result["vote_link"]["court_type"] == "SINGLE"
    assert result["poll"] is None


def test_respond_default_court_type_is_double():
    poll = WAPoll(question="?", slots=[_SLOT_A, _SLOT_B])
    result = respond.invoke({"response": WAResponse(poll=poll)})
    assert result["poll"]["court_type"] == "DOUBLE"


def test_respond_raises_if_poll_and_vote_link_both_set():
    with pytest.raises(ValidationError):
        WAResponse(
            poll=WAPoll(question="?", slots=[_SLOT_A]),
            vote_link=WAVoteLink(question="?", slots=[_SLOT_A]),
        )


# ---------------------------------------------------------------------------
# extract_response
# ---------------------------------------------------------------------------


def test_extract_response_finds_respond_tool():
    payload = {
        "text_parts": ["Here are your slots:"],
        "poll": {"question": "Slot?", "slots": [_SLOT_A, _SLOT_B], "court_type": "DOUBLE"},
        "vote_link": None,
    }
    result = {"messages": [_make_tool_msg("respond", payload)]}
    wa_response = extract_response(result)
    assert wa_response is not None
    assert wa_response.text_parts == ["Here are your slots:"]
    assert wa_response.poll is not None
    assert wa_response.poll.question == "Slot?"


def test_extract_response_returns_none_when_absent():
    result = {"messages": [_make_tool_msg("find_slots", {"count": 0, "slots": []})]}
    assert extract_response(result) is None


def test_extract_response_returns_none_on_invalid_payload():
    """Mutually exclusive constraint triggers a warning + None, not a crash."""
    payload = {
        "text_parts": [],
        "poll": {"question": "?", "slots": [_SLOT_A], "court_type": "DOUBLE"},
        "vote_link": {"question": "?", "slots": [_SLOT_A], "court_type": "DOUBLE"},
    }
    result = {"messages": [_make_tool_msg("respond", payload)]}
    assert extract_response(result) is None


def test_extract_response_empty_payload_gives_defaults():
    """An empty dict is a valid WAResponse with all-default fields."""
    result = {"messages": [_make_tool_msg("respond", {})]}
    wa_response = extract_response(result)
    assert wa_response is not None
    assert wa_response.text_parts == []
    assert wa_response.poll is None


# ---------------------------------------------------------------------------
# extract_final_text (fallback — unchanged behaviour)
# ---------------------------------------------------------------------------


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
# WA-specific update_user_profile (ContextVar side-effect)
# ---------------------------------------------------------------------------


def test_update_user_profile_mutates_profile():
    state = UserState(profile={}, language="")
    set_wa_invocation_state(state)
    result = update_user_profile.invoke({"key": "preferred_city", "value": "Berlin"})
    assert result == {"status": "saved", "key": "preferred_city", "value": "Berlin"}
    assert state.profile["preferred_city"] == "Berlin"


def test_update_user_profile_sets_language_not_profile():
    state = UserState(profile={}, language="")
    set_wa_invocation_state(state)
    update_user_profile.invoke({"key": "language", "value": "de"})
    assert state.language == "de"
    assert "language" not in state.profile


def test_update_user_profile_noop_when_no_context():
    """Returns success even when no UserState is injected — does not crash."""
    _wa_state_ctx.set(None)
    result = update_user_profile.invoke({"key": "preferred_city", "value": "Munich"})
    assert result["status"] == "saved"
