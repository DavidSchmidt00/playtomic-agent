import json
from datetime import datetime
from typing import Annotated, Any

from langchain.agents import create_agent
from langchain_core.tools import tool
from langgraph.graph.state import CompiledStateGraph

from playtomic_agent.config import get_settings
from playtomic_agent.llm import llm
from playtomic_agent.tools import (
    create_booking_link,
    find_clubs_by_location,
    find_clubs_by_name,
    find_slots,
    find_slots_date_range,
    is_weekend,
    update_user_profile,
)

settings = get_settings()


@tool(description="Present slot options as a native WhatsApp poll. Only use in groups.")
def send_poll(
    question: Annotated[str, "Short poll question, e.g. 'Welcher Slot passt euch?'"],
    slots: Annotated[
        list[dict],
        "List of slot dicts from find_slots. Each MUST have 'display' and 'booking_link'. Max 12.",
    ],
    court_type: Annotated[
        str,
        "'SINGLE' for 1v1 courts (threshold: 2 votes) or 'DOUBLE' for 2v2 courts (threshold: 4 votes). Default: 'DOUBLE'.",
    ] = "DOUBLE",
) -> Annotated[dict, "Poll payload forwarded to WhatsApp."]:
    """Sends a native WhatsApp poll. Slot display labels come pre-formatted from find_slots."""
    return {"wa_poll": {"question": question, "slots": slots[:12], "court_type": court_type}}


WA_TOOLS = [
    find_slots,
    find_slots_date_range,
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
        f"You are Padel Agent — a friendly, witty Padel court finder on WhatsApp. "
        f"Today: {datetime.now().strftime('%Y-%m-%d')}. "
        f"Timezone: {settings.default_timezone}.\n\n"
        "PERSONALITY:\n"
        "- You love Padel and can drop the occasional pun or light joke (keep it quick).\n"
        "- Short friendly banter is welcome — just steer back to Padel.\n"
        "- If someone says 'hi' or chats casually, respond warmly in 1-2 sentences then offer help.\n"
        "- If a topic is clearly unrelated to Padel or sports, politely redirect.\n\n"
        "GOAL: help users find and book Padel courts via WhatsApp.\n\n"
        f"{'User language: ' + language + chr(10) if language else ''}"
        "RULES:\n"
        "1. NEVER invent data (names, times, prices, links). Use EXACT tool outputs.\n"
        "2. Keep responses SHORT — plain text only, no markdown.\n"
        "3. Always reply in the same language the user writes in.\n"
        "4. On first message: detect the user's language and call"
        " `update_user_profile('language', '<code>')` (e.g. 'de', 'en', 'es').\n\n"
        "WORKFLOW:\n"
        "1. Specific club mentioned? -> `find_clubs_by_name` (use SHORT name).\n"
        "2. City/Region mentioned? -> `find_clubs_by_location`.\n"
        "3. Availability needed?\n"
        "   - Single date -> `find_slots` (club slug + date).\n"
        "   - Multiple days ('next 3 days', 'this weekend', etc.) -> `find_slots_date_range` (start_date + end_date).\n"
        "4. Slots found (>0)? -> "
        + (
            "You MUST call `send_poll` — do NOT list slots as text. Send a short text reply alongside the poll.\n"
            if is_group
            else "List them as a numbered plain text list in your reply.\n"
        )
        + "5. No slots found? -> Tell the user with a sympathetic quip and suggest a different date or time.\n\n"
        + (
            "POLLS — MANDATORY in groups:\n"
            "- ALWAYS use `send_poll` whenever you have 2+ slot options.\n"
            "- NEVER list slots as plain text in a group — always a poll.\n"
            "- Pass each slot dict from find_slots directly as-is (it already has 'display' and 'booking_link').\n"
            "- Set court_type='SINGLE' if the user is looking for singles courts, otherwise 'DOUBLE'.\n"
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
        model=llm,
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
            return content.strip()
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                    return str(item["text"]).strip()
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
