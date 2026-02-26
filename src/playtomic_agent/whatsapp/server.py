"""WhatsApp webhook server — standalone entry point for the WhatsApp agent."""

import asyncio
import logging
import os
import threading
from collections import defaultdict

from neonize.aioze.client import NewAClient
from neonize.aioze.events import (
    ConnectFailureEv,
    GroupInfoEv,
    JoinedGroupEv,
    LoggedOutEv,
    MessageEv,
    event_global_loop,
)
from neonize.proto.Neonize_pb2 import ConnectFailureReason
from neonize.utils.enum import ChatPresence, ChatPresenceMedia, ReceiptType, VoteType
from neonize.utils.message import extract_text

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


def main() -> None:
    """Entry point for the whatsapp-agent command."""
    setup_logging(os.environ.get("LOG_LEVEL", "INFO"))

    settings = get_settings()
    storage = UserStorage(settings.whatsapp_storage_path)
    client = NewAClient(settings.whatsapp_session_db)
    user_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    @client.event.paircode
    async def on_paircode(wa_client: NewAClient, code: str, connected: bool) -> None:
        if connected:
            logger.info("WhatsApp authenticated via pairing code.")
        else:
            logger.info("=" * 50)
            logger.info("PAIRING CODE: %s", code)
            logger.info("On your phone: WhatsApp → Linked Devices → Link with phone number")
            logger.info("=" * 50)

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
            "WhatsApp session logged out (reason=%s on_connect=%s) — exiting so the process restarts",
            event.Reason,
            event.OnConnect,
        )
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
            try:
                result = await asyncio.to_thread(
                    agent.invoke,
                    {"messages": messages},
                    {"recursion_limit": 30},
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
                await wa_client.send_message(
                    sender_jid, "Sorry, something went wrong. Please try again."
                )
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
                    question = str(poll_data["question"])
                    options: list[str] = poll_data["options"]
                    poll_msg = await wa_client.build_poll_vote_creation(
                        name=question,
                        options=options,
                        selectable_count=VoteType.SINGLE,
                    )
                    await wa_client.send_message(sender_jid, poll_msg)
                    logger.info("Poll sent to group %s (%d options)", sender_id, len(options))

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
