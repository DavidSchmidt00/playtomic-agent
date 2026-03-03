"""Tests for message handling helper functions in server.py and agent.py."""

import json
from unittest.mock import MagicMock

from playtomic_agent.whatsapp.agent import extract_message_parts
from playtomic_agent.whatsapp.server import (
    _detect_media_type,
    _prepend_quoted_context,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_msg(**set_fields: bool) -> MagicMock:
    """Return a mock Message where named media fields have non-empty ListFields()."""
    all_fields = (
        "imageMessage",
        "audioMessage",
        "videoMessage",
        "documentMessage",
        "stickerMessage",
        "locationMessage",
    )
    msg = MagicMock()
    for field in all_fields:
        getattr(msg, field).ListFields.return_value = (
            [("url", "https://example.com")] if field in set_fields else []
        )
    return msg


# ---------------------------------------------------------------------------
# WA-3: _detect_media_type
# ---------------------------------------------------------------------------


def test_detect_image():
    assert _detect_media_type(_make_msg(imageMessage=True)) == "image"


def test_detect_audio():
    assert _detect_media_type(_make_msg(audioMessage=True)) == "voice note"


def test_detect_video():
    assert _detect_media_type(_make_msg(videoMessage=True)) == "video"


def test_detect_document():
    assert _detect_media_type(_make_msg(documentMessage=True)) == "document"


def test_detect_sticker():
    assert _detect_media_type(_make_msg(stickerMessage=True)) == "sticker"


def test_detect_location():
    assert _detect_media_type(_make_msg(locationMessage=True)) == "location"


def test_detect_none_for_plain_text():
    assert _detect_media_type(_make_msg()) is None


def test_detect_first_wins_when_multiple_set():
    # imageMessage comes first in _MEDIA_LABELS dict order — it should win
    msg = _make_msg(imageMessage=True, audioMessage=True)
    assert _detect_media_type(msg) == "image"


# ---------------------------------------------------------------------------
# WA-4: _prepend_quoted_context
# ---------------------------------------------------------------------------


def test_enriches_with_quoted_text():
    result = _prepend_quoted_context("Where can I play?", "Let's play tomorrow at 18:00")
    assert result == '[Replying to: "Let\'s play tomorrow at 18:00"]\nWhere can I play?'


def test_truncates_at_300_chars():
    long_text = "x" * 350
    result = _prepend_quoted_context("hi", long_text)
    # Extract the excerpt between the quotes
    excerpt = result.split('"')[1]
    assert excerpt == "x" * 300 + "…"


def test_exactly_300_chars_no_ellipsis():
    text = "y" * 300
    result = _prepend_quoted_context("hi", text)
    excerpt = result.split('"')[1]
    assert excerpt == "y" * 300
    assert "…" not in result


def test_empty_quoted_text_unchanged():
    assert _prepend_quoted_context("hi", "") == "hi"


# ---------------------------------------------------------------------------
# WA-1: extract_message_parts
# ---------------------------------------------------------------------------


def _tool_msg(name: str, content: object) -> MagicMock:
    m = MagicMock()
    m.name = name
    m.content = json.dumps(content)
    return m


def test_extract_message_parts_returns_parts():
    result = {"messages": [_tool_msg("send_messages", {"wa_messages": ["Hello", "World"]})]}
    assert extract_message_parts(result) == ["Hello", "World"]


def test_extract_message_parts_empty_when_no_tool_message():
    assert extract_message_parts({"messages": []}) == []


def test_extract_message_parts_filters_empty_strings():
    result = {"messages": [_tool_msg("send_messages", {"wa_messages": ["Hello", "", "World"]})]}
    assert extract_message_parts(result) == ["Hello", "World"]


def test_extract_message_parts_ignores_other_tools():
    result = {"messages": [_tool_msg("send_poll", {"wa_poll": {}})]}
    assert extract_message_parts(result) == []


def test_extract_message_parts_coerces_to_str():
    result = {"messages": [_tool_msg("send_messages", {"wa_messages": [42, 3.14]})]}
    assert extract_message_parts(result) == ["42", "3.14"]
