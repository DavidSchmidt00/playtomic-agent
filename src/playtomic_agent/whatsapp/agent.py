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


@tool(
    description=(
        "Send a reply as multiple sequential WhatsApp messages. Use when your response has "
        "distinct parts (e.g. intro text + slot list, or context + booking link). "
        "Each part becomes its own message, sent in order."
    )
)
def send_messages(
    parts: Annotated[list[str], "Ordered list of message texts, one per WhatsApp message."],
) -> Annotated[dict, "Message parts payload forwarded to WhatsApp."]:
    """Instructs the server to send each part as a separate WhatsApp message."""
    return {"wa_messages": parts}


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
    if len(slots) < 2:
        return {
            "error": "WhatsApp polls require at least 2 options. List the single slot as text instead."
        }
    return {"wa_poll": {"question": question, "slots": slots[:12], "court_type": court_type}}


@tool(description="Present slot options as a shareable web voting link. Only use in groups.")
def send_vote_link(
    question: Annotated[str, "Short poll question, e.g. 'Welcher Slot passt euch?'"],
    slots: Annotated[
        list[dict],
        "List of slot dicts from find_slots. Each MUST have 'display' and 'booking_link'. Max 12.",
    ],
    court_type: Annotated[
        str,
        "'SINGLE' for 1v1 courts (threshold: 2 votes) or 'DOUBLE' for 2v2 courts (threshold: 4 votes). Default: 'DOUBLE'.",
    ] = "DOUBLE",
) -> Annotated[dict, "Web vote link payload to generate a URL."]:
    """Sends a web voting link. Slot display labels come pre-formatted from find_slots."""
    if len(slots) < 2:
        return {
            "error": "Voting links require at least 2 options. List the single slot as text instead."
        }
    return {"wa_vote_link": {"question": question, "slots": slots[:12], "court_type": court_type}}


WA_TOOLS = [
    find_slots,
    find_slots_date_range,
    create_booking_link,
    is_weekend,
    find_clubs_by_location,
    find_clubs_by_name,
    update_user_profile,
    send_messages,
    send_poll,
    send_vote_link,
]


def _build_system_prompt(
    user_profile: dict | None = None,
    language: str = "",
    is_group: bool = False,
    poll_count: int = 0,
    poll_threshold: int = 3,
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

    voting_tool = "send_poll" if poll_count < poll_threshold else "send_vote_link"
    voting_action = (
        f"call `{voting_tool}` (WhatsApp requires ≥2 options)"
        if poll_count < poll_threshold
        else f"call `{voting_tool}`"
    )
    voting_mechanic = (
        "once 4 people pick the same slot, I'll send the booking link!"
        if poll_count < poll_threshold
        else "Click the link to vote"
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
        "2. Keep responses SHORT. Use only WhatsApp formatting: *bold*, _italic_, ~strikethrough~, "
        "`monospace`. No markdown (no #headers, no [links](url), no tables).\n"
        "   For booking links: ALWAYS paste the bare URL on its own line. NEVER wrap it as [text](url).\n"
        "   When your reply has distinct parts (e.g. intro + slot list, or context + booking link), "
        "call `send_messages` with each part as a separate list item instead of combining them.\n"
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
            f"If 2+ slots: {voting_action}. If exactly 1 slot: send it as plain text with the booking link — do NOT call `{voting_tool}`.\n"
            if is_group
            else "List them as a numbered plain text list in your reply.\n"
        )
        + "5. No slots found? -> Tell the user with a sympathetic quip and suggest a different date or time.\n\n"
        + (
            f"POLLS/VOTING LINKS — MANDATORY in groups:\n"
            f"- ALWAYS use `{voting_tool}` whenever you have 2+ slot options.\n"
            f"- NEVER list slots as plain text in a group — always use `{voting_tool}`.\n"
            f"- Pass each slot dict from find_slots directly as-is (it already has 'display' and 'booking_link').\n"
            f"- Set court_type='SINGLE' if the user is looking for singles courts, otherwise 'DOUBLE'.\n"
            f"- Always send a short text reply alongside {voting_tool} AND briefly explain the voting mechanic:\n"
            f"  e.g. 'Vote for all slots that work for you — {voting_mechanic}' (adjust threshold: 2 for singles, 4 for doubles).\n\n"
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
    poll_count: int = 0,
    poll_threshold: int = 3,
) -> CompiledStateGraph:
    """Create the WhatsApp agent with optional user profile injected into the system prompt."""
    return create_agent(
        model=llm,
        name="whatsapp_agent",
        tools=WA_TOOLS,
        system_prompt=_build_system_prompt(
            user_profile,
            language=language,
            is_group=is_group,
            poll_count=poll_count,
            poll_threshold=poll_threshold,
        ),
    )


def _extract_tool_message(result: dict, tool_name: str) -> dict | None:
    """Return the parsed dict content of the first tool message matching tool_name."""
    for m in result.get("messages", []):
        if getattr(m, "name", None) != tool_name:
            continue
        content = getattr(m, "content", "")
        try:
            parsed = json.loads(content) if isinstance(content, str) else content
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
    return None


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


def extract_message_parts(result: dict) -> list[str]:
    """Scan tool messages for a wa_messages payload from send_messages."""
    payload = _extract_tool_message(result, send_messages.name)
    if payload:
        parts = payload.get("wa_messages")
        if isinstance(parts, list):
            return [str(p) for p in parts if p]
    return []


def extract_poll_data(result: dict) -> "dict[str, Any] | None":
    """Scan tool messages for a wa_poll payload from send_poll."""
    payload = _extract_tool_message(result, send_poll.name)
    if payload:
        wa_poll = payload.get("wa_poll")
        if isinstance(wa_poll, dict):
            return wa_poll
    return None


def extract_vote_link_data(result: dict) -> "dict[str, Any] | None":
    """Scan tool messages for a wa_vote_link payload from send_vote_link."""
    payload = _extract_tool_message(result, send_vote_link.name)
    if payload:
        wa_vote_link = payload.get("wa_vote_link")
        if isinstance(wa_vote_link, dict):
            return wa_vote_link
    return None


def extract_preference_updates(result: dict) -> dict:
    """Scan tool messages for profile_update payloads from update_user_profile."""
    updates: dict = {}
    for m in result.get("messages", []):
        if getattr(m, "name", None) != update_user_profile.name:
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
