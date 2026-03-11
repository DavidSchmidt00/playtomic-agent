"""Tests for per-option court_type threshold in native WhatsApp polls."""

import asyncio
from collections import defaultdict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from playtomic_agent.whatsapp.agent import WAPoll, WAResponse
from playtomic_agent.whatsapp.server import _dispatch_wa_response
from playtomic_agent.whatsapp.storage import UserState


def _make_wa_client():
    client = MagicMock()
    send_resp = MagicMock()
    send_resp.ID = "msg-123"
    client.build_poll_vote_creation = AsyncMock(return_value=MagicMock())
    client.send_message = AsyncMock(return_value=send_resp)
    return client


_MIXED_SLOTS = [
    {"display": "SINGLE slot", "booking_link": "https://a", "court_type": "SINGLE"},
    {"display": "DOUBLE slot", "booking_link": "https://b", "court_type": "DOUBLE"},
]


@pytest.mark.asyncio
async def test_dispatch_poll_stores_court_type_per_option():
    """active_poll options must carry the court_type from their originating slot."""
    response = WAResponse(poll=WAPoll(question="Vote?", slots=_MIXED_SLOTS, court_type="DOUBLE"))
    user_state = UserState()
    storage = MagicMock()

    await _dispatch_wa_response(
        wa_client=_make_wa_client(),
        sender_jid=MagicMock(),
        sender_id="g1@g.us",
        response=response,
        user_state=user_state,
        storage=storage,
        is_group=True,
    )

    options = user_state.active_poll["options"]
    assert options[0]["court_type"] == "SINGLE"
    assert options[1]["court_type"] == "DOUBLE"


@pytest.mark.asyncio
async def test_handle_poll_vote_single_fires_at_2_double_silent():
    """SINGLE option fires at 2 votes; DOUBLE option at 2 votes does not."""
    from playtomic_agent.whatsapp.server import _handle_poll_vote

    # active_poll with mixed court types, SINGLE option already at 2 voters,
    # DOUBLE at 2 voters — only SINGLE should notify
    active_poll = {
        "message_id": "poll-abc",
        "question": "Who's in?",
        "court_type": "DOUBLE",  # session-level (should be ignored per-option)
        "options": [
            {
                "display": "SINGLE slot",
                "booking_link": "https://a",
                "court_type": "SINGLE",
                "voters": ["u1@s.whatsapp.net", "u2@s.whatsapp.net"],
            },
            {
                "display": "DOUBLE slot",
                "booking_link": "https://b",
                "court_type": "DOUBLE",
                "voters": ["u1@s.whatsapp.net", "u2@s.whatsapp.net"],
            },
        ],
    }

    from playtomic_agent.whatsapp.storage import UserState, UserStorage

    user_state = UserState()
    user_state.active_poll = active_poll

    storage = MagicMock(spec=UserStorage)
    storage.load.return_value = user_state

    wa_client = MagicMock()
    poll_vote = MagicMock()
    # No new votes — the voters are already stored, changed=False path would skip.
    # Add a third voter so changed=True triggers the threshold check.
    poll_vote.selectedOptions = []  # no new selections from this voter

    sender_jid = MagicMock()
    user_locks: defaultdict = defaultdict(asyncio.Lock)

    # Patch get_poll_update_message to return a non-None value (triggering processing)
    mock_poll_update = MagicMock()
    mock_poll_update.pollCreationMessageKey.ID = "poll-abc"

    message = MagicMock()
    message.Info.MessageSource.Sender.User = "u3"
    message.Info.MessageSource.Sender.Server = "s.whatsapp.net"

    wa_client.decrypt_poll_vote = AsyncMock(return_value=poll_vote)

    notified_options = []

    async def fake_notify(client, jid, option, threshold):
        notified_options.append((option["display"], threshold))

    with (
        patch(
            "playtomic_agent.whatsapp.server.get_poll_update_message",
            return_value=mock_poll_update,
        ),
        patch(
            "playtomic_agent.whatsapp.server._notify_booking_threshold",
            side_effect=fake_notify,
        ),
    ):
        # Force changed=True by having a voter not yet in any option
        # Simulate: u3 votes for the SINGLE option
        import hashlib

        single_hash = hashlib.sha256(b"SINGLE slot").digest()
        poll_vote.selectedOptions = [single_hash]

        await _handle_poll_vote(wa_client, message, sender_jid, "g1@g.us", storage, user_locks)

    # Only SINGLE option should have notified (2 votes == threshold 2)
    assert len(notified_options) == 1
    assert notified_options[0][0] == "SINGLE slot"
    assert notified_options[0][1] == 2  # threshold passed to _notify_booking_threshold


@pytest.mark.asyncio
async def test_handle_poll_vote_double_fires_at_4():
    """DOUBLE option fires when it reaches 4 voters."""
    from playtomic_agent.whatsapp.server import _handle_poll_vote

    active_poll = {
        "message_id": "poll-def",
        "question": "Who's in?",
        "court_type": "DOUBLE",
        "options": [
            {
                "display": "DOUBLE slot",
                "booking_link": "https://b",
                "court_type": "DOUBLE",
                "voters": ["u1@s", "u2@s", "u3@s"],  # 3 voters, will add u4
            },
        ],
    }

    from playtomic_agent.whatsapp.storage import UserState, UserStorage

    user_state = UserState()
    user_state.active_poll = active_poll

    storage = MagicMock(spec=UserStorage)
    storage.load.return_value = user_state

    wa_client = MagicMock()
    wa_client.decrypt_poll_vote = AsyncMock(return_value=MagicMock())

    user_locks: defaultdict = defaultdict(asyncio.Lock)
    message = MagicMock()
    message.Info.MessageSource.Sender.User = "u4"
    message.Info.MessageSource.Sender.Server = "s"

    mock_poll_update = MagicMock()
    mock_poll_update.pollCreationMessageKey.ID = "poll-def"

    notified_options = []

    async def fake_notify(client, jid, option, threshold):
        notified_options.append((option["display"], threshold))

    import hashlib

    double_hash = hashlib.sha256(b"DOUBLE slot").digest()
    wa_client.decrypt_poll_vote.return_value.selectedOptions = [double_hash]

    with (
        patch(
            "playtomic_agent.whatsapp.server.get_poll_update_message",
            return_value=mock_poll_update,
        ),
        patch(
            "playtomic_agent.whatsapp.server._notify_booking_threshold",
            side_effect=fake_notify,
        ),
    ):
        await _handle_poll_vote(wa_client, message, MagicMock(), "g1@g.us", storage, user_locks)

    assert len(notified_options) == 1
    assert notified_options[0][0] == "DOUBLE slot"
    assert notified_options[0][1] == 4
