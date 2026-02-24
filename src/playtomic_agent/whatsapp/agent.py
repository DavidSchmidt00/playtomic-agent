import json
from datetime import datetime
from typing import Annotated, Any

from langchain.agents import create_agent
from langchain_core.tools import tool
from langgraph.graph.state import CompiledStateGraph

from playtomic_agent.config import get_settings
from playtomic_agent.llm import gemini
from playtomic_agent.tools import (
    create_booking_link,
    find_clubs_by_location,
    find_clubs_by_name,
    find_slots,
    is_weekend,
    update_user_profile,
)

settings = get_settings()


@tool(description="Present multiple options (slots, clubs, etc.) as a native WhatsApp poll.")
def send_poll(
    question: Annotated[str, "Short poll question, e.g. 'Which slot works for you?'"],
    options: Annotated[list[str], "Poll options as short strings (max 12)."],
) -> Annotated[dict, "Poll payload forwarded to WhatsApp."]:
    """Sends a native WhatsApp poll. Use in groups when presenting multiple choices."""
    return {"wa_poll": {"question": question, "options": options[:12]}}


WA_TOOLS = [
    find_slots,
    create_booking_link,
    is_weekend,
    find_clubs_by_location,
    find_clubs_by_name,
    update_user_profile,
    send_poll,
]


def _build_system_prompt(
    user_profile: dict | None = None, language: str = "", is_group: bool = False
) -> str:
    """Build the WhatsApp-specific system prompt."""
    profile_section = ""
    if user_profile:
        prefs = []
        if user_profile.get("preferred_club_name"):
            prefs.append(
                f"- Preferred club: {user_profile['preferred_club_name']} "
                f"(slug: {user_profile.get('preferred_club_slug', 'unknown')})"
            )
        if user_profile.get("preferred_city"):
            prefs.append(f"- Preferred city: {user_profile['preferred_city']}")
        if user_profile.get("court_type"):
            prefs.append(f"- Preferred court type: {user_profile['court_type']}")
        if user_profile.get("duration"):
            prefs.append(f"- Preferred duration: {user_profile['duration']} minutes")
        if user_profile.get("preferred_time"):
            prefs.append(f"- Preferred time: {user_profile['preferred_time']}")

        if prefs:
            profile_section = (
                "\n\nUSER PREFERENCES (from previous sessions):\n"
                + "\n".join(prefs)
                + "\nUse these as defaults when the user doesn't specify."
                " Do NOT ask for these values if they are already set."
            )

    return (
        f"You are a Padel court finder assistant on WhatsApp. "
        f"Today: {datetime.now().strftime('%Y-%m-%d')}. "
        f"Timezone: {settings.default_timezone}.\n\n"
        "GOAL: help users find and book Padel courts via WhatsApp.\n\n"
        f"{'User language: ' + language + chr(10) if language else ''}"
        "RULES:\n"
        "1. ONLY answer about Padel courts/bookings.\n"
        "2. NEVER invent data (names, times, prices, links). Use EXACT tool outputs.\n"
        "3. Keep responses SHORT — plain text only, no markdown.\n"
        "4. Always reply in the same language the user writes in.\n"
        "5. On first message: detect the user's language and call"
        " `update_user_profile('language', '<code>')` (e.g. 'de', 'en', 'es').\n\n"
        "WORKFLOW:\n"
        "1. Specific club mentioned? -> `find_clubs_by_name` (use SHORT name).\n"
        "2. City/Region mentioned? -> `find_clubs_by_location`.\n"
        "3. Availability needed? -> `find_slots` (club slug + date).\n"
        "4. Slots found (>0)? -> "
        + (
            "Call `send_poll` with the slot times as options, and send a brief text reply alongside.\n"
            if is_group
            else "List them as a numbered plain text list in your reply.\n"
        )
        + "5. No slots found? -> Tell the user and suggest a different date or time.\n\n"
        + (
            "POLLS:\n"
            "- Use `send_poll` when you have multiple slots or clubs to present.\n"
            "- Keep options short (e.g. '18:00 – 90 min – €12'). Max 12 options.\n"
            "- Always send a short text reply alongside the poll.\n\n"
            if is_group
            else ""
        )
        + "PREFERENCES:\n"
        "- Detect new preferences (club, court, etc.) -> Call `update_user_profile` silently.\n"
        "- Known Club -> Call `update_user_profile` TWICE: once for `preferred_club_slug`,"
        " once for `preferred_club_name`."
        f"{profile_section}"
    )


def create_whatsapp_agent(
    user_profile: dict | None = None,
    language: str = "",
    is_group: bool = False,
) -> CompiledStateGraph:
    """Create the WhatsApp agent with optional user profile injected into the system prompt."""
    return create_agent(
        model=gemini,
        name="whatsapp_agent",
        tools=WA_TOOLS,
        system_prompt=_build_system_prompt(user_profile, language=language, is_group=is_group),
    )


def extract_final_text(result: dict) -> str:
    """Extract the last AIMessage text from a LangGraph invoke result."""
    messages = result.get("messages", [])
    for m in reversed(messages):
        is_ai = (
            m.__class__.__name__ == "AIMessage"
            or getattr(m, "type", "") == "ai"
            or (isinstance(m, dict) and m.get("role") == "assistant")
        )
        if not is_ai:
            continue
        if getattr(m, "tool_calls", None):
            continue
        content = getattr(m, "content", None) or (m.get("content") if isinstance(m, dict) else None)
        if isinstance(content, str) and content:
            return content
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                    return str(item["text"])
    return ""


def extract_poll_data(result: dict) -> "dict[str, Any] | None":
    """Scan tool messages for a wa_poll payload from send_poll."""
    for m in result.get("messages", []):
        if getattr(m, "name", None) != "send_poll":
            continue
        content = getattr(m, "content", "")
        try:
            parsed = json.loads(content) if isinstance(content, str) else content
            wa_poll = parsed.get("wa_poll")
            if isinstance(parsed, dict) and isinstance(wa_poll, dict):
                return wa_poll
        except (json.JSONDecodeError, TypeError):
            pass
    return None


def extract_preference_updates(result: dict) -> dict:
    """Scan tool messages for profile_update payloads from update_user_profile."""
    updates: dict = {}
    messages = result.get("messages", [])
    for m in messages:
        if getattr(m, "name", None) != "update_user_profile":
            continue
        content = getattr(m, "content", "")
        try:
            parsed = json.loads(content) if isinstance(content, str) else content
            if isinstance(parsed, dict) and "profile_update" in parsed:
                upd = parsed["profile_update"]
                updates[upd["key"]] = upd["value"]
        except (json.JSONDecodeError, TypeError, KeyError):
            pass
    return updates
