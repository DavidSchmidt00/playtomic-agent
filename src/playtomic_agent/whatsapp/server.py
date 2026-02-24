"""WhatsApp webhook server — standalone entry point for the WhatsApp agent."""

import asyncio
import logging
import os
import sys
import threading

from neonize.aioze.client import NewAClient
from neonize.aioze.events import MessageEv, event_global_loop
from neonize.utils.message import extract_text

from playtomic_agent.config import get_settings
from playtomic_agent.whatsapp.agent import (
    create_whatsapp_agent,
    extract_final_text,
    extract_preference_updates,
)
from playtomic_agent.whatsapp.storage import UserStorage

logger = logging.getLogger(__name__)


def main() -> None:
    """Entry point for the whatsapp-agent command."""
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    settings = get_settings()
    storage = UserStorage(settings.whatsapp_storage_path)
    client = NewAClient(settings.whatsapp_session_db)
    user_locks: dict[str, asyncio.Lock] = {}

    @client.event(MessageEv)
    async def on_message(wa_client: NewAClient, message: MessageEv) -> None:
        if message.Info.MessageSource.IsFromMe:
            return
        if message.Info.MessageSource.IsGroup:
            return

        sender_jid = message.Info.MessageSource.Chat
        sender_id = f"{sender_jid.User}@{sender_jid.Server}"

        user_input = extract_text(message.Message).strip()
        if not user_input:
            return

        if sender_id not in user_locks:
            user_locks[sender_id] = asyncio.Lock()

        async with user_locks[sender_id]:
            logger.info("Incoming message from %s", sender_id)

            user_state = storage.load(sender_id)
            messages = user_state.history + [{"role": "user", "content": user_input}]
            agent = create_whatsapp_agent(
                user_profile=user_state.profile, language=user_state.language
            )

            try:
                result = await asyncio.to_thread(
                    agent.invoke,
                    {"messages": messages},
                    {"recursion_limit": 30},
                )
            except Exception:
                logger.exception("Agent failed for sender %s", sender_id)
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

            if final_text:
                await wa_client.send_message(sender_jid, final_text)
                logger.info("Replied to %s", sender_id)

    # event_global_loop is a separate asyncio loop created by neonize that runs
    # the connection task and dispatches async event handlers.  We must start it
    # in a background thread before scheduling anything on it.
    threading.Thread(target=event_global_loop.run_forever, daemon=True).start()

    logger.info("Starting WhatsApp client (scan QR code if prompted)…")

    # connect() schedules the Go connection coroutine on event_global_loop and
    # returns immediately.  idle() then awaits that task, keeping us alive until
    # the connection drops or is cancelled.
    asyncio.run_coroutine_threadsafe(client.connect(), event_global_loop).result()

    try:
        asyncio.run_coroutine_threadsafe(client.idle(), event_global_loop).result()
    except KeyboardInterrupt:
        logger.info("WhatsApp agent stopped.")
    finally:
        event_global_loop.call_soon_threadsafe(event_global_loop.stop)
