"""Tests for message handling helper functions in server.py."""

from unittest.mock import MagicMock

from playtomic_agent.whatsapp.server import (
    _detect_media_type,
    _prepend_quoted_context,
    _split_message,
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
# WA-1: _split_message
# ---------------------------------------------------------------------------

BOOKING = "https://app.playtomic.com/"


def test_short_text_returns_single_chunk():
    assert _split_message("short text") == ["short text"]


def test_exactly_at_boundary_single_chunk():
    text = "a" * 1200
    assert _split_message(text) == [text]


def test_isolates_booking_link_as_final_chunk():
    body = "Slot A ist verfügbar\n\nSlot B ist verfügbar"
    link = f"Jetzt buchen: {BOOKING}payments?foo=bar"
    text = body + "\n\n" + link
    # max_chunk_chars=50 forces a split (total text ~100 chars > 50)
    chunks = _split_message(text, max_chunk_chars=50, booking_url_prefix=BOOKING)
    assert chunks[-1] == link
    assert link not in "\n\n".join(chunks[:-1])


def test_split_by_length_no_booking_url():
    para = "x" * 700
    text = para + "\n\n" + para
    chunks = _split_message(text, max_chunk_chars=800, booking_url_prefix=BOOKING)
    assert len(chunks) == 2
    assert chunks[0] == para
    assert chunks[1] == para


def test_single_chunk_when_fits():
    para1 = "Hello there"
    para2 = "How can I help?"
    text = para1 + "\n\n" + para2
    chunks = _split_message(text, max_chunk_chars=1200, booking_url_prefix=BOOKING)
    assert chunks == [text]


def test_multiple_paragraphs_merged_greedily():
    # Each paragraph is 100 chars; 10 paragraphs = 1000 + 9*2 separators = 1018 chars
    # With max_chunk_chars=550, we expect 2 chunks (first 5 paras, then 5 paras)
    para = "a" * 100
    text = "\n\n".join([para] * 10)
    chunks = _split_message(text, max_chunk_chars=550, booking_url_prefix=BOOKING)
    assert len(chunks) == 2
    # Verify all content is preserved
    assert "\n\n".join(chunks) == text


def test_no_split_for_single_element_with_link():
    link_only = f"Book: {BOOKING}foo"
    assert _split_message(link_only, max_chunk_chars=200, booking_url_prefix=BOOKING) == [link_only]


def test_oversized_paragraph_sent_as_own_chunk():
    big_para = "z" * 2000
    small_para = "small"
    text = big_para + "\n\n" + small_para
    chunks = _split_message(text, max_chunk_chars=1200, booking_url_prefix=BOOKING)
    assert big_para in chunks
    assert small_para in chunks
