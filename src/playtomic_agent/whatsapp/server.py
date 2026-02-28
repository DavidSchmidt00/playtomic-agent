"""WhatsApp webhook server — standalone entry point for the WhatsApp agent."""

import asyncio
import logging
import os
import random
import threading
from collections import defaultdict
from typing import Any

from neonize.aioze.client import NewAClient
from neonize.aioze.events import (
    ConnectFailureEv,
    GroupInfoEv,
    JoinedGroupEv,
    LoggedOutEv,
    MessageEv,
    OfflineSyncCompletedEv,
    event_global_loop,
)
from neonize.proto.Neonize_pb2 import ConnectFailureReason
from neonize.proto.waCompanionReg.WAWebProtobufsCompanionReg_pb2 import DeviceProps
from neonize.utils.enum import ChatPresence, ChatPresenceMedia, ReceiptType, VoteType
from neonize.utils.message import extract_text, get_poll_update_message

from playtomic_agent.config import get_settings
from playtomic_agent.log_config import setup_logging
from playtomic_agent.whatsapp.agent import (
    create_whatsapp_agent,
    extract_final_text,
    extract_poll_data,
    extract_preference_updates,
)
from playtomic_agent.whatsapp.storage import UserStorage

logger = logging.getLogger(__name__)

_GROUP_INTRO = (
    "Hallo! 👋 Ich bin der Padel-Agent und helfe dabei, freie Court-Slots auf "
    "Playtomic zu finden. 🎾\n\n"
    "So funktioniert's:\n"
    "Erwähnt mich mit @ und stellt eure Frage, z.B.:\n"
    "* Gibt es morgen Abend freie Courts bei Lemon Padel?\n"
    "* Suche Doppel-Courts in Berlin am Samstag\n"
    "Ihr könnt auch einfach auf meine Nachricht antworten (Swipe über meine Nachricht)\n\n"
    "Übrigens: Mich gibts auch auf https://padelagent.de 🌐"
)


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

        # Only handle votes for the current active poll
        received_id = poll_update.pollCreationMessageKey.ID
        stored_id = user_state.active_poll["message_id"]
        if received_id != stored_id:
            logger.info(
                "Poll vote ID mismatch in %s: received=%r stored=%r — ignoring",
                sender_id,
                received_id,
                stored_id,
            )
            return

        voter_jid = (
            f"{message.Info.MessageSource.Sender.User}"
            f"@{message.Info.MessageSource.Sender.Server}"
        )
        court_type = user_state.active_poll.get("court_type", "DOUBLE")
        threshold = 2 if court_type == "SINGLE" else 4

        n_selected = len(poll_vote.selectedOptions)
        logger.info(
            "Poll vote from %s in %s: %d option(s) selected, threshold=%d",
            voter_jid,
            sender_id,
            n_selected,
            threshold,
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

        # Find options that just hit threshold and haven't been notified yet.
        # We keep the poll alive (don't clear active_poll) so other options can
        # still accumulate votes and trigger their own notifications later.
        ready = [
            o
            for o in user_state.active_poll["options"]
            if len(o["voters"]) >= threshold and not o.get("notified")
        ]
        if ready:
            for option in ready:
                option["notified"] = True
            storage.save(sender_id, user_state)
            for option in ready:
                logger.info(
                    "Poll threshold reached in %s for '%s' (%d voters)",
                    sender_id,
                    option["display"],
                    len(option["voters"]),
                )
                await _notify_booking_threshold(wa_client, sender_jid, option, threshold)


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

    await wa_client.send_message(group_jid, text)
    logger.info("Booking threshold notification sent for '%s'", display)


def main() -> None:
    """Entry point for the whatsapp-agent command."""
    setup_logging(os.environ.get("LOG_LEVEL", "INFO"))

    settings = get_settings()
    if settings.whatsapp_clear_storage_on_start:
        try:
            os.remove(settings.whatsapp_storage_path)
            logger.info(
                "Cleared user storage at %s (WHATSAPP_CLEAR_STORAGE_ON_START)",
                settings.whatsapp_storage_path,
            )
        except FileNotFoundError:
            pass
    storage = UserStorage(settings.whatsapp_storage_path)
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
        await wa_client.disconnect()
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
        await wa_client.send_message(group_jid, _GROUP_INTRO)

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

        user_input = extract_text(message.Message).strip()
        if not user_input:
            return

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
            )

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
            result = None
            timed_out = False
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(
                        agent.invoke,
                        {"messages": messages},
                        {"recursion_limit": 30},
                    ),
                    timeout=settings.agent_timeout_seconds,
                )
                # Delay while the typing indicator is still active so there's
                # no visible gap between typing stopping and the message arriving.
                _preview = extract_final_text(result) if result is not None else ""
                if _preview:
                    _delay = _compute_send_delay(_preview, settings.whatsapp_send_delay_wpm)
                    if _delay > 0:
                        logger.debug(
                            "Send delay %.2fs for %s (%d words)",
                            _delay,
                            sender_id,
                            len(_preview.split()),
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

            final_text = extract_final_text(result)
            prefs = extract_preference_updates(result)

            if prefs:
                if detected_lang := prefs.pop("language", None):
                    user_state.language = detected_lang
                user_state.profile.update(prefs)
                logger.info("Updated profile for %s: %s", sender_id, prefs)
            user_state.history = (messages + [{"role": "assistant", "content": final_text}])[-20:]
            storage.save(sender_id, user_state)

            if is_group:
                poll_data = extract_poll_data(result)
                if poll_data:
                    slots_meta: list[dict] = poll_data.get("slots", [])
                    question = str(poll_data["question"])
                    court_type = str(poll_data.get("court_type", "DOUBLE"))
                    display_options = [s.get("display", "") for s in slots_meta]
                    if len(display_options) < 2:
                        logger.warning("send_poll called with <2 options — skipping poll send")
                        display_options = []
                        poll_data = None
                if poll_data:
                    poll_msg = await wa_client.build_poll_vote_creation(
                        name=question,
                        options=display_options,
                        selectable_count=VoteType.MULTIPLE,
                    )
                    send_resp = await wa_client.send_message(sender_jid, poll_msg)
                    user_state.active_poll = {
                        "message_id": send_resp.ID,
                        "question": question,
                        "court_type": court_type,
                        "options": [
                            {
                                "display": s.get("display", ""),
                                "booking_link": s.get("booking_link", ""),
                                "voters": [],
                            }
                            for s in slots_meta
                        ],
                    }
                    storage.save(sender_id, user_state)
                    logger.info(
                        "Poll sent to group %s (%d options, id=%s)",
                        sender_id,
                        len(display_options),
                        send_resp.ID,
                    )

            if final_text:
                await wa_client.send_message(sender_jid, final_text)
                logger.info("Replied to %s", sender_id)

    # event_global_loop is a separate asyncio loop created by neonize that runs
    # the connection task and dispatches async event handlers.  We must start it
    # in a background thread before scheduling anything on it.
    threading.Thread(target=event_global_loop.run_forever, daemon=True).start()

    asyncio.run_coroutine_threadsafe(client.connect(), event_global_loop).result()

    try:
        asyncio.run_coroutine_threadsafe(client.idle(), event_global_loop).result()
    except KeyboardInterrupt:
        logger.info("WhatsApp agent stopped.")
    finally:
        event_global_loop.call_soon_threadsafe(event_global_loop.stop)
