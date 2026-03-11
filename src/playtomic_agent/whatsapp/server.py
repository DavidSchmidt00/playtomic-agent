"""WhatsApp webhook server — standalone entry point for the WhatsApp agent."""

import asyncio
import logging
import os
import random
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

import httpx
import requests
import uvicorn
from fastapi import FastAPI, Request
from neonize.aioze.client import NewAClient
from neonize.aioze.events import (
    ConnectFailureEv,
    GroupInfoEv,
    JoinedGroupEv,
    LoggedOutEv,
    MessageEv,
    OfflineSyncCompletedEv,
)
from neonize.proto.Neonize_pb2 import JID, ConnectFailureReason
from neonize.proto.waCompanionReg.WAWebProtobufsCompanionReg_pb2 import DeviceProps
from neonize.utils.enum import ChatPresence, ChatPresenceMedia, ReceiptType, VoteType
from neonize.utils.message import extract_text, get_poll_update_message

from playtomic_agent.config import get_settings
from playtomic_agent.log_config import setup_logging
from playtomic_agent.metrics import metrics_app
from playtomic_agent.whatsapp.agent import (
    WAResponse,
    create_whatsapp_agent,
    extract_final_text,
    extract_response,
    set_wa_invocation_state,
)
from playtomic_agent.whatsapp.storage import UserState, UserStorage

logger = logging.getLogger(__name__)


def _group_intro() -> str:
    return (
        "Hallo! 👋 Ich bin der Padel-Agent und helfe dabei, freie Court-Slots auf "
        "Playtomic zu finden. 🎾\n\n"
        "So funktioniert's:\n"
        "Erwähnt mich mit @ und stellt eure Frage, z.B.:\n"
        "* Gibt es morgen Abend freie Courts bei Lemon Padel?\n"
        "* Suche Doppel-Courts in Berlin am Samstag\n"
        "Ihr könnt auch einfach auf meine Nachricht antworten (Swipe über meine Nachricht)\n\n"
        f"Übrigens: Mich gibts auch auf {get_settings().web_public_base_url} 🌐"
    )


async def _fire_alert(*, event: str, reason: str, message: str) -> None:
    """POST a JSON alert to WHATSAPP_ALERT_WEBHOOK_URL. Fire-and-forget; never raises."""
    url = get_settings().whatsapp_alert_webhook_url
    if not url:
        return
    payload = {
        "event": event,
        "reason": reason,
        "message": message,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(url, json=payload)
        logger.info("Alert fired: event=%s reason=%s", event, reason)
    except Exception as exc:
        logger.warning("Failed to fire alert (event=%s): %s", event, exc)


webhook_app = FastAPI(title="WhatsApp Webhook Receiver")
webhook_app.mount("/metrics", metrics_app)


@webhook_app.post("/api/webhook/consensus")
async def consensus_webhook(req: Request):
    """Receive threshold consensus from the Web API and notify the group."""
    data = await req.json()
    group_jid = data.get("group_jid")
    display = data.get("display")
    voter_count = data.get("voter_count")
    vote_id = data.get("vote_id")

    wa_client = getattr(webhook_app.state, "wa_client", None)
    neonize_loop = getattr(webhook_app.state, "neonize_loop", None)
    if wa_client and neonize_loop and group_jid and display:
        # Parse "user@server" string back into a neonize JID object, which
        # send_message / send_chat_presence require (plain strings are rejected).
        user, _, server = group_jid.partition("@")
        jid_obj = JID(User=user, Server=server, RawAgent=0, Device=0, Integrator=0)

        msg = (
            f"🎉 *Buchungs-Empfehlung erreicht!*\n\n"
            f"{voter_count} Leute haben für diesen Slot abgestimmt:\n*{display}*\n\n"
            "Zeit, den Court zu buchen! 🎾"
        )
        if data.get("booking_link"):
            msg += f"\n👉 {data.get('booking_link')}"

        # _send_text is a coroutine on the neonize event loop — dispatch safely
        # across the loop boundary from uvicorn's loop.
        fut = asyncio.run_coroutine_threadsafe(_send_text(wa_client, jid_obj, msg), neonize_loop)
        fut.add_done_callback(
            lambda f: (
                logger.error("consensus _send_text failed: %s", f.exception())
                if not f.cancelled() and f.exception()
                else None
            )
        )
        logger.info("Sent consensus webhook notification to %s for vote %s", group_jid, vote_id)

    return {"status": "ok"}


def _compute_send_delay(text: str, wpm: float) -> float:
    """Return a human-like send delay in seconds proportional to message length.

    Clamps to [0.3, 3.0] seconds with +/-20% jitter. Returns 0.0 if wpm <= 0.
    """
    if wpm <= 0:
        return 0.0
    words = max(1, len(text.split()))
    base = words / (wpm / 60.0)
    jitter = base * random.uniform(-0.2, 0.2)
    return max(0.3, min(3.0, base + jitter))


_MEDIA_LABELS: dict[str, str] = {
    "imageMessage": "image",
    "audioMessage": "voice note",
    "videoMessage": "video",
    "documentMessage": "document",
    "stickerMessage": "sticker",
    "locationMessage": "location",
}

_MEDIA_LABELS_DE: dict[str, str] = {
    "image": "ein Bild",
    "voice note": "eine Sprachnachricht",
    "video": "ein Video",
    "document": "ein Dokument",
    "sticker": "einen Sticker",
    "location": "einen Standort",
}


def _detect_media_type(msg: Any) -> str | None:
    """Return a human-readable media label if the message is non-text media, else None."""
    for field, label in _MEDIA_LABELS.items():
        if getattr(msg, field).ListFields():
            return label
    return None


def _prepend_quoted_context(user_input: str, quoted_text: str) -> str:
    """Prepend quoted message context to user_input when a user replies to a message."""
    if not quoted_text:
        return user_input
    excerpt = quoted_text[:300] + ("…" if len(quoted_text) > 300 else "")
    return f'[Replying to: "{excerpt}"]\n{user_input}'


async def _send_text(wa_client: NewAClient, jid: Any, text: str) -> None:
    """Send a text message preceded by a natural typing indicator and WPM delay."""
    delay = _compute_send_delay(text, get_settings().whatsapp_send_delay_wpm)
    if delay > 0:
        try:
            await wa_client.send_chat_presence(
                jid,
                ChatPresence.CHAT_PRESENCE_COMPOSING,
                ChatPresenceMedia.CHAT_PRESENCE_MEDIA_TEXT,
            )
        except Exception:
            logger.debug("Failed to send COMPOSING presence", exc_info=True)
        try:
            await asyncio.sleep(delay)
        finally:
            try:
                await wa_client.send_chat_presence(
                    jid,
                    ChatPresence.CHAT_PRESENCE_PAUSED,
                    ChatPresenceMedia.CHAT_PRESENCE_MEDIA_TEXT,
                )
            except Exception:
                logger.debug("Failed to send PAUSED presence", exc_info=True)
    await wa_client.send_message(jid, text)


def _get_bot_jids(client: NewAClient) -> set[str]:
    """Return the set of JID strings the bot is known by (phone JID + LID)."""
    if not client.me:
        return set()
    jids = {f"{client.me.JID.User}@{client.me.JID.Server}"}
    if not client.me.LID.IsEmpty:
        jids.add(f"{client.me.LID.User}@{client.me.LID.Server}")
    return jids


def _is_bot_mentioned(message: MessageEv, bot_jids: set[str]) -> bool:
    """Return True if the bot is @mentioned or the message is a reply to the bot."""
    ctx = message.Message.extendedTextMessage.contextInfo
    if bot_jids & set(ctx.mentionedJID):
        return True
    # Also trigger when the user replies to one of the bot's messages.
    # In that case ctx.participant holds the JID of the quoted message's sender.
    if ctx.participant and ctx.participant in bot_jids:
        return True
    return False


async def _handle_poll_vote(
    wa_client: NewAClient,
    message: MessageEv,
    sender_jid: Any,
    sender_id: str,
    storage: UserStorage,
    user_locks: defaultdict,
) -> None:
    """Decrypt a poll vote, update the active poll tally, and notify if threshold is reached."""
    import hashlib

    poll_update = get_poll_update_message(message)
    if poll_update is None:
        return

    try:
        poll_vote = await wa_client.decrypt_poll_vote(message)
    except Exception:
        logger.debug("decrypt_poll_vote failed for %s — skipping", sender_id)
        return

    async with user_locks[sender_id]:
        user_state = storage.load(sender_id)
        if not user_state.active_poll:
            logger.info("Poll vote received for %s but no active_poll stored — ignoring", sender_id)
            return

        # Only handle votes for native WhatsApp polls (vote-link polls store "vote_id",
        # not "message_id" — skip them to avoid KeyError).
        stored_id = user_state.active_poll.get("message_id")
        if stored_id is None:
            logger.info(
                "Poll vote received for %s but active_poll has no message_id "
                "(vote-link poll active) — ignoring",
                sender_id,
            )
            return

        received_id = poll_update.pollCreationMessageKey.ID
        if received_id != stored_id:
            logger.info(
                "Poll vote ID mismatch in %s: received=%r stored=%r — ignoring",
                sender_id,
                received_id,
                stored_id,
            )
            return

        voter_jid = (
            f"{message.Info.MessageSource.Sender.User}@{message.Info.MessageSource.Sender.Server}"
        )
        n_selected = len(poll_vote.selectedOptions)
        logger.info(
            "Poll vote from %s in %s: %d option(s) selected",
            voter_jid,
            sender_id,
            n_selected,
        )

        opt_hash_map = {
            hashlib.sha256(o["display"].encode()).digest(): o
            for o in user_state.active_poll["options"]
        }
        changed = False
        unmatched: list[str] = []
        for selected_bytes in poll_vote.selectedOptions:
            matched = opt_hash_map.get(selected_bytes)
            if matched is None:
                unmatched.append(
                    selected_bytes.hex()
                    if isinstance(selected_bytes, bytes)
                    else repr(selected_bytes)
                )
            elif voter_jid not in matched["voters"]:
                matched["voters"].append(voter_jid)
                changed = True

        if unmatched:
            logger.info(
                "Poll vote from %s: %d unrecognized hash(es) — %s",
                voter_jid,
                len(unmatched),
                unmatched,
            )
        if not changed:
            logger.info(
                "Poll vote from %s changed nothing (already counted or no match)", voter_jid
            )
            return
        storage.save(sender_id, user_state)

        # Find options that just hit their per-court-type threshold and haven't been notified.
        # SINGLE courts need 2 votes; DOUBLE courts need 4.
        # We keep the poll alive (don't clear active_poll) so other options can
        # still accumulate votes and trigger their own notifications later.
        ready = [
            o
            for o in user_state.active_poll["options"]
            if len(o["voters"]) >= (2 if o.get("court_type") == "SINGLE" else 4)
            and not o.get("notified")
        ]
        if ready:
            for option in ready:
                option["notified"] = True
            storage.save(sender_id, user_state)
            for option in ready:
                option_threshold = 2 if option.get("court_type") == "SINGLE" else 4
                logger.info(
                    "Poll threshold reached in %s for '%s' (%d voters)",
                    sender_id,
                    option["display"],
                    len(option["voters"]),
                )
                await _notify_booking_threshold(wa_client, sender_jid, option, option_threshold)


async def _notify_booking_threshold(
    wa_client: NewAClient,
    group_jid: Any,
    option: dict,
    threshold: int,
) -> None:
    """Check slot availability and send a booking reminder to the group."""
    from urllib.parse import parse_qs, urlparse

    from playtomic_agent.client.api import PlaytomicClient
    from playtomic_agent.models import Club

    display = option["display"]
    booking_link = option.get("booking_link", "")
    still_available = True

    if booking_link:
        try:
            qs = parse_qs(urlparse(booking_link).query)
            club_id = qs["tenant_id"][0]
            court_id = qs["resource_id"][0]
            # Booking links URL-encode colons as %3A — decode before parsing
            raw_start = qs["start"][0].replace("%3A", ":")
            duration = int(qs["duration"][0])
            date_str = raw_start[:10]  # "2026-02-27"
            start_hhmm = raw_start[11:16]  # "17:00"

            minimal_club = Club(club_id=club_id, name="", slug="", timezone="UTC", courts=[])
            with PlaytomicClient() as client:
                slots = client.get_available_slots(minimal_club, date_str, start_time=start_hhmm)
            still_available = any(s.court_id == court_id and s.duration == duration for s in slots)
        except Exception:
            logger.debug("Availability check failed — sending reminder anyway", exc_info=True)

    if still_available:
        if booking_link:
            text = f"🎯 {threshold} Stimmen für {display}! Jetzt buchen:\n{booking_link}"
        else:
            text = f"🎯 {threshold} Stimmen für {display}! Auf Playtomic buchen."
    else:
        text = f"⚠️ {display} ist leider nicht mehr verfügbar — wählt einen anderen Slot!"

    await _send_text(wa_client, group_jid, text)
    logger.info("Booking threshold notification sent for '%s'", display)


async def _dispatch_wa_response(
    wa_client: NewAClient,
    sender_jid: Any,
    sender_id: str,
    response: WAResponse,
    user_state: UserState,
    storage: UserStorage,
    is_group: bool,
) -> None:
    """Send text parts then dispatch poll or vote link (groups only)."""
    # --- Text parts ---
    parts = [p for p in response.text_parts if p]
    for i, part in enumerate(parts):
        if i > 0:
            await _send_text(wa_client, sender_jid, part)
        else:
            # Part 0: keep-typing was already active during agent invoke,
            # so skip the double typing indicator from _send_text.
            await wa_client.send_message(sender_jid, part)
    if parts:
        logger.info("Replied to %s (%d message(s))", sender_id, len(parts))

    if not is_group:
        return

    # --- Poll dispatch ---
    if response.poll is not None:
        poll = response.poll
        display_options = [s.display for s in poll.slots]
        if len(display_options) < 2:
            logger.warning("respond.poll has <2 options — skipping poll send")
        else:
            poll_msg = await wa_client.build_poll_vote_creation(
                name=poll.question,
                options=display_options,
                selectable_count=VoteType.MULTIPLE,
            )
            send_resp = await wa_client.send_message(sender_jid, poll_msg)
            user_state.active_poll = {
                "message_id": send_resp.ID,
                "question": poll.question,
                "court_type": poll.court_type,
                "options": [
                    {
                        "display": s.display,
                        "booking_link": s.booking_link,
                        "court_type": s.court_type,
                        "voters": [],
                    }
                    for s in poll.slots
                ],
            }
            user_state.poll_count += 1
            storage.save(sender_id, user_state)
            logger.info(
                "Poll sent to group %s (%d options, id=%s)",
                sender_id,
                len(display_options),
                send_resp.ID,
            )

    # --- Vote link dispatch ---
    elif response.vote_link is not None:
        vl = response.vote_link
        if len(vl.slots) < 2:
            logger.warning("respond.vote_link has <2 options — skipping")
            return
        payload = {
            "slots": [s.model_dump() for s in vl.slots],
            "metadata": {
                "group_jid": f"{sender_jid.User}@{sender_jid.Server}",
            },
        }
        resp = None
        try:
            resp = await asyncio.to_thread(
                requests.post,
                f"{get_settings().web_api_url}/api/votes",
                json=payload,
                timeout=10,
            )
            resp.raise_for_status()
            vote_id = resp.json().get("vote_id")
            user_state.active_poll = {
                "vote_id": vote_id,
                "question": vl.question,
                "court_type": vl.court_type,
                "options": [
                    {
                        "display": s.display,
                        "booking_link": s.booking_link,
                        "court_type": s.court_type,
                        "voters": [],
                    }
                    for s in vl.slots
                ],
            }
            storage.save(sender_id, user_state)
            vote_url = f"{get_settings().web_public_base_url}/vote/{vote_id}"
            vote_msg = f"🗳️ *{vl.question}*\n\nHier abstimmen:\n{vote_url}"
            await _send_text(wa_client, sender_jid, vote_msg)
            user_state.poll_count += 1
            storage.save(sender_id, user_state)
            logger.info(
                "Vote link created via Web API and sent to %s (vote_id=%s)",
                sender_id,
                vote_id,
            )
        except Exception as exc:
            if resp is not None and not resp.ok:
                logger.error(
                    "Web API rejected vote creation: %s — %s",
                    resp.status_code,
                    resp.text,
                )
            logger.error("Failed to create web vote via API: %s", exc)
            await _send_text(
                wa_client,
                sender_jid,
                "Entschuldigung, beim Erstellen der Web-Abstimmung ist ein Fehler aufgetreten. "
                "Bitte versuche es später noch einmal.",
            )


def main() -> None:
    """Entry point for the whatsapp-agent command."""
    setup_logging(os.environ.get("LOG_LEVEL", "INFO"))

    settings = get_settings()
    if settings.whatsapp_clear_storage_on_start:
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(settings.whatsapp_db_path + suffix)
            except FileNotFoundError:
                pass
        logger.info(
            "Cleared user storage at %s (WHATSAPP_CLEAR_STORAGE_ON_START)",
            settings.whatsapp_db_path,
        )
    storage = UserStorage(settings.whatsapp_db_path)
    _platform_name = settings.whatsapp_device_platform.upper()
    _platform_int = getattr(DeviceProps, _platform_name, None)
    if _platform_int is None:
        logger.warning(
            "Unknown WHATSAPP_DEVICE_PLATFORM=%r — falling back to CHROME",
            settings.whatsapp_device_platform,
        )
        _platform_int = DeviceProps.CHROME

    client = NewAClient(
        settings.whatsapp_session_db,
        props=DeviceProps(
            os=settings.whatsapp_device_os,
            platformType=_platform_int,
        ),
    )
    user_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
    _ready = False  # Set to True once offline sync is complete; gates on_message

    @client.event.paircode
    async def on_paircode(wa_client: NewAClient, code: str, connected: bool) -> None:
        if connected:
            logger.info("WhatsApp authenticated via pairing code.")
        else:
            logger.info("=" * 50)
            logger.info("PAIRING CODE: %s", code)
            logger.info("On your phone: WhatsApp → Linked Devices → Link with phone number")
            logger.info("=" * 50)

    @client.event(OfflineSyncCompletedEv)
    async def on_offline_sync_completed(
        wa_client: NewAClient, event: OfflineSyncCompletedEv
    ) -> None:
        nonlocal _ready
        _ready = True
        logger.info("Offline sync complete — bot is now processing incoming messages")

    _PERMANENT_FAILURES = {
        ConnectFailureReason.LOGGED_OUT,
        ConnectFailureReason.MAIN_DEVICE_GONE,
        ConnectFailureReason.UNKNOWN_LOGOUT,
        ConnectFailureReason.CLIENT_OUTDATED,
        ConnectFailureReason.BAD_USER_AGENT,
        ConnectFailureReason.TEMP_BANNED,
    }

    @client.event(ConnectFailureEv)
    async def on_connect_failure(wa_client: NewAClient, event: ConnectFailureEv) -> None:
        if event.Reason in _PERMANENT_FAILURES:
            logger.error(
                "WhatsApp connection permanently failed (reason=%s message=%s) — manual intervention may be required",
                event.Reason,
                event.Message,
            )
        else:
            logger.warning(
                "WhatsApp connection failed (reason=%s message=%s) — transient, restarting",
                event.Reason,
                event.Message,
            )
        os._exit(1)

    @client.event(LoggedOutEv)
    async def on_logged_out(wa_client: NewAClient, event: LoggedOutEv) -> None:
        logger.error(
            "WhatsApp session logged out (reason=%s on_connect=%s) — deleting session and exiting",
            event.Reason,
            event.OnConnect,
        )
        try:
            os.remove(settings.whatsapp_session_db)
            logger.info("Session DB deleted — next restart will trigger re-pairing")
        except OSError:
            logger.warning("Could not delete session DB at %s", settings.whatsapp_session_db)
        os._exit(1)

    _pairing_triggered = False

    @client.event.qr
    async def on_qr(wa_client: NewAClient, qr_data: bytes) -> None:
        nonlocal _pairing_triggered
        if _pairing_triggered:
            return
        if not settings.whatsapp_phone_number:
            logger.error("No WHATSAPP_PHONE_NUMBER configured — cannot pair, exiting")
            os._exit(1)
        _pairing_triggered = True
        logger.info(
            "No session found — switching to pairing code for %s…",
            settings.whatsapp_phone_number,
        )
        await wa_client.PairPhone(settings.whatsapp_phone_number, True)

    @client.event(JoinedGroupEv)
    async def on_joined_group(wa_client: NewAClient, event: JoinedGroupEv) -> None:
        """Fires when the bot itself joins a group (added by admin or via invite link)."""
        group_jid = event.GroupInfo.JID
        logger.info(
            "JoinedGroupEv — group=%s@%s reason=%s type=%s",
            group_jid.User,
            group_jid.Server,
            event.Reason,
            event.Type,
        )
        await _send_text(wa_client, group_jid, _group_intro())

    @client.event(GroupInfoEv)
    async def on_group_info(wa_client: NewAClient, event: GroupInfoEv) -> None:
        # Logging only — intro is sent exclusively via JoinedGroupEv to avoid
        # sending a duplicate when both events fire for the same join action.
        logger.info(
            "GroupInfoEv — group=%s@%s join=%s leave=%s",
            event.JID.User,
            event.JID.Server,
            [f"{j.User}@{j.Server}" for j in event.Join],
            [f"{j.User}@{j.Server}" for j in event.Leave],
        )

    @client.event(MessageEv)
    async def on_message(wa_client: NewAClient, message: MessageEv) -> None:
        if message.Info.MessageSource.IsFromMe:
            return

        # Skip messages replayed from the offline period; only process once sync is done
        if not _ready:
            return

        sender_jid = message.Info.MessageSource.Chat
        sender_id = f"{sender_jid.User}@{sender_jid.Server}"

        if message.Info.MessageSource.IsGroup:
            bot_jids = _get_bot_jids(client)
            if not bot_jids:
                logger.info("Group message received but client.me is not set yet — ignoring")
                return
            ctx = message.Message.extendedTextMessage.contextInfo
            mentioned = list(ctx.mentionedJID)
            logger.info(
                "Group message — bot_jids=%s mentioned=%s participant=%s has_extended=%s",
                bot_jids,
                mentioned,
                ctx.participant or None,
                message.Message.HasField("extendedTextMessage"),
            )
            is_directed = _is_bot_mentioned(message, bot_jids)
            # Mark delivered (grey ticks) for every group message; only mark read
            # (blue ticks) when the message is actually directed at the bot.
            receipt = ReceiptType.READ if is_directed else ReceiptType.DELIVERED
            try:
                await wa_client.mark_read(
                    message.Info.ID,
                    chat=message.Info.MessageSource.Chat,
                    sender=message.Info.MessageSource.Sender,
                    receipt=receipt,
                )
            except Exception:
                logger.debug("mark_read failed for %s (non-fatal)", sender_id)
            # Poll votes arrive as pollUpdateMessage — handle before direction check
            if get_poll_update_message(message):
                await _handle_poll_vote(
                    wa_client, message, sender_jid, sender_id, storage, user_locks
                )
                return

            if not is_directed:
                return
        else:
            # DMs: always mark as read.
            try:
                await wa_client.mark_read(
                    message.Info.ID,
                    chat=message.Info.MessageSource.Chat,
                    sender=message.Info.MessageSource.Sender,
                    receipt=ReceiptType.READ,
                )
            except Exception:
                logger.debug("mark_read failed for %s (non-fatal)", sender_id)

        # Detect non-text media — send friendly reply, skip agent
        media_type = _detect_media_type(message.Message)
        if media_type:
            label_de = _MEDIA_LABELS_DE.get(media_type, media_type)
            reply = (
                f"Ich sehe, dass du {label_de} geschickt hast — "
                "ich kann leider nur Text verarbeiten. "
                "Schreib mir einfach, welchen Court du suchst! 🎾"
            )
            await _send_text(wa_client, sender_jid, reply)
            return

        user_input = extract_text(message.Message).strip()
        if not user_input:
            return

        # Enrich user_input with quoted context when user replies to a message.
        # Skip if the quoted message was sent by the bot itself (it's already in history).
        try:
            ctx = message.Message.extendedTextMessage.contextInfo
            bot_jids = _get_bot_jids(client)
            if ctx.participant not in bot_jids:
                quoted_raw = extract_text(ctx.quotedMessage).strip()
            else:
                quoted_raw = ""
        except Exception:
            quoted_raw = ""
        user_input = _prepend_quoted_context(user_input, quoted_raw)

        async with user_locks[sender_id]:
            if message.Info.MessageSource.IsGroup:
                actual_sender = message.Info.MessageSource.Sender
                logger.info(
                    "Incoming group message in %s from %s@%s",
                    sender_id,
                    actual_sender.User,
                    actual_sender.Server,
                )
            else:
                logger.info("Incoming message from %s", sender_id)

            is_group = message.Info.MessageSource.IsGroup
            user_state = storage.load(sender_id)
            messages = user_state.history + [{"role": "user", "content": user_input}]
            agent = create_whatsapp_agent(
                user_profile=user_state.profile,
                language=user_state.language,
                is_group=is_group,
                poll_count=user_state.poll_count,
                poll_threshold=settings.vote_link_poll_threshold,
            )

            # Inject live UserState so the WA update_user_profile tool can mutate it
            # directly via ContextVar — asyncio.to_thread copies the current context.
            set_wa_invocation_state(user_state)

            async def _keep_typing(stop: asyncio.Event) -> None:
                while not stop.is_set():
                    try:
                        await wa_client.send_chat_presence(
                            sender_jid,
                            ChatPresence.CHAT_PRESENCE_COMPOSING,
                            ChatPresenceMedia.CHAT_PRESENCE_MEDIA_TEXT,
                        )
                    except Exception:
                        pass
                    try:
                        await asyncio.wait_for(stop.wait(), timeout=4)
                    except TimeoutError:
                        pass  # resend typing on next iteration

            stop_typing = asyncio.Event()
            typing_task = asyncio.create_task(_keep_typing(stop_typing))
            result: dict | None = None
            timed_out = False
            wa_response: WAResponse | None = None
            final_text = ""
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(
                        lambda: agent.invoke(
                            {"messages": messages},
                            {"recursion_limit": 30},
                        )
                    ),
                    timeout=settings.agent_timeout_seconds,
                )
                wa_response = extract_response(result) if result is not None else None
                final_text = extract_final_text(result) if result is not None else ""
                _delay_text = (
                    wa_response.text_parts[0] if wa_response and wa_response.text_parts else ""
                ) or final_text
                if _delay_text:
                    _delay = _compute_send_delay(_delay_text, settings.whatsapp_send_delay_wpm)
                    if _delay > 0:
                        logger.debug(
                            "Send delay %.2fs for %s (%d words)",
                            _delay,
                            sender_id,
                            len(_delay_text.split()),
                        )
                        await asyncio.sleep(_delay)
            except TimeoutError:
                timed_out = True
                logger.error(
                    "Agent timed out after %ds for %s",
                    settings.agent_timeout_seconds,
                    sender_id,
                )
            except Exception:
                logger.exception("Agent failed for sender %s", sender_id)
            finally:
                stop_typing.set()
                typing_task.cancel()
                try:
                    await typing_task
                except (asyncio.CancelledError, Exception):
                    pass
                try:
                    await wa_client.send_chat_presence(
                        sender_jid,
                        ChatPresence.CHAT_PRESENCE_PAUSED,
                        ChatPresenceMedia.CHAT_PRESENCE_MEDIA_TEXT,
                    )
                except Exception:
                    pass

            if result is None:
                msg = (
                    "Der KI-Dienst antwortet gerade nicht rechtzeitig. Bitte versuche es gleich nochmal. 🙏"
                    if timed_out
                    else "Entschuldigung, da ist etwas schiefgelaufen. Bitte versuche es nochmal. 🙏"
                )
                await wa_client.send_message(sender_jid, msg)
                return

            # Profile updates were applied in-place by the WA update_user_profile tool
            # via _wa_state_ctx — no post-hoc extraction needed.
            history_text = (
                "\n\n".join(wa_response.text_parts)
                if wa_response and wa_response.text_parts
                else final_text
            )
            user_state.history = (messages + [{"role": "assistant", "content": history_text}])[-20:]
            storage.save(sender_id, user_state)

            if wa_response:
                await _dispatch_wa_response(
                    wa_client, sender_jid, sender_id, wa_response, user_state, storage, is_group
                )
            elif final_text:
                await wa_client.send_message(sender_jid, final_text)
                logger.info("Replied to %s (fallback final_text)", sender_id)

    async def _run() -> None:
        webhook_app.state.wa_client = client
        webhook_app.state.neonize_loop = asyncio.get_running_loop()
        config = uvicorn.Config(
            webhook_app,
            port=get_settings().whatsapp_webhook_port,
            host="0.0.0.0",
            log_level="warning",
        )
        server = uvicorn.Server(config)
        _webhook_task = asyncio.create_task(server.serve())
        _webhook_task.add_done_callback(
            lambda t: (
                logger.error("Webhook server exited unexpectedly: %s", t.exception())
                if not t.cancelled() and t.exception()
                else None
            )
        )

        await client.connect()
        await client.idle()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logger.info("WhatsApp agent stopped.")
