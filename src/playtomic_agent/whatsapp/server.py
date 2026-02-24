"""WhatsApp webhook server — standalone entry point for the WhatsApp agent."""

import asyncio
import logging
import sys

logger = logging.getLogger(__name__)


def _format_wa_poll(poll_data: dict, recipient: str) -> dict:
    """Build the native WhatsApp interactive poll JSON payload."""
    options = [
        {"name": f"{s['local_time']} · {s['duration']}min · {s['price']}"}
        for s in poll_data.get("slots", [])
    ]
    return {
        "messaging_product": "whatsapp",
        "to": recipient,
        "type": "interactive",
        "interactive": {
            "type": "poll",
            "body": {"text": "Available padel slots:"},
            "action": {
                "name": "poll",
                "parameters": {
                    "question": poll_data.get("question", "Which slot do you want to book?"),
                    "options": options,
                    "allow_multiple_answers": False,
                },
            },
        },
    }


def _extract_poll_response(interactive: dict) -> str:
    """Extract the selected option text from an incoming poll/button/list response."""
    for key in ("poll_response", "list_reply", "button_reply"):
        reply = interactive.get(key)
        if reply:
            return str(reply.get("title") or reply.get("id", ""))
    return ""


def main() -> None:
    """Entry point for the whatsapp-agent command."""
    import os

    from whatsapp import Message, WhatsApp

    from playtomic_agent.config import get_settings
    from playtomic_agent.whatsapp.agent import (
        create_whatsapp_agent,
        extract_final_text,
        extract_poll_data,
        extract_preference_updates,
    )
    from playtomic_agent.whatsapp.storage import UserStorage

    # Configure logging
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    settings = get_settings()

    if not settings.whatsapp_token:
        logger.error("WHATSAPP_TOKEN is not set. Exiting.")
        sys.exit(1)
    if not settings.whatsapp_phone_number_id:
        logger.error("WHATSAPP_PHONE_NUMBER_ID is not set. Exiting.")
        sys.exit(1)

    messenger = WhatsApp(
        token=settings.whatsapp_token,
        phone_number_id={"main": settings.whatsapp_phone_number_id},
        verify_token=settings.whatsapp_verify_token,
        logger=True,
        debug=False,
    )
    storage = UserStorage(settings.whatsapp_storage_path)

    @messenger.on_message
    async def handle_message(message: Message) -> None:
        sender = message.sender
        logger.info("Incoming message from %s (type=%s)", sender, message.type)

        user_state = storage.load(sender)

        if message.type == "text":
            user_input = message.content or ""
        elif message.type == "interactive":
            user_input = _extract_poll_response(message.interactive or {})
        else:
            logger.debug("Ignoring message type: %s", message.type)
            return

        if not user_input.strip():
            return

        messages = user_state.history + [{"role": "user", "content": user_input}]
        agent = create_whatsapp_agent(
            user_profile=user_state.profile,
            language=user_state.language,
        )

        try:
            result = await asyncio.to_thread(
                agent.invoke,
                {"messages": messages},
                {"recursion_limit": 30},
            )
        except Exception:
            logger.exception("Agent failed for sender %s", sender)
            Message(
                instance=messenger,
                to=sender,
                content="Sorry, something went wrong. Please try again.",
            ).send()
            return

        final_text = extract_final_text(result)
        poll_data = extract_poll_data(result)
        prefs = extract_preference_updates(result)

        # Persist updated state
        if prefs:
            user_state.profile.update(prefs)
            logger.info("Updated profile for %s: %s", sender, prefs)
        user_state.history = (messages + [{"role": "assistant", "content": final_text}])[-20:]
        storage.save(sender, user_state)

        # Send text reply
        if final_text:
            Message(instance=messenger, to=sender, content=final_text).send()

        # Send native WhatsApp poll (separate message)
        if poll_data:
            messenger.send_custom_json(sender, _format_wa_poll(poll_data, sender))
            logger.info("Sent poll with %d options to %s", len(poll_data.get("slots", [])), sender)

    @messenger.on_verification
    async def verify(challenge: str) -> None:
        logger.info("Webhook verified (challenge=%s)", challenge)

    port = int(os.environ.get("WHATSAPP_PORT", "5001"))
    logger.info("Starting WhatsApp webhook server on port %d", port)
    messenger.run(host="0.0.0.0", port=port)
