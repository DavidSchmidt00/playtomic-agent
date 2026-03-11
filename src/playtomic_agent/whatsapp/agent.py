import json
import logging
from contextvars import ContextVar
from datetime import datetime
from typing import Annotated

from langchain.agents import create_agent
from langchain_core.tools import tool
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, model_validator

from playtomic_agent.config import get_settings
from playtomic_agent.llm import llm
from playtomic_agent.tools import (
    create_booking_link,
    find_clubs_by_location,
    find_clubs_by_name,
    find_slots,
    find_slots_date_range,
    is_weekend,
)
from playtomic_agent.whatsapp.storage import UserState

logger = logging.getLogger(__name__)
settings = get_settings()

# ---------------------------------------------------------------------------
# Per-invocation ContextVar — injected by server.py before asyncio.to_thread.
# asyncio.to_thread copies the current context into the worker thread so the
# update_user_profile tool can mutate the live UserState object in-place.
# ---------------------------------------------------------------------------

_wa_state_ctx: ContextVar[UserState | None] = ContextVar("_wa_state_ctx", default=None)


def set_wa_invocation_state(state: UserState) -> None:
    """Call before asyncio.to_thread(agent.invoke, ...) to inject the live state."""
    _wa_state_ctx.set(state)


# ---------------------------------------------------------------------------
# WA-specific update_user_profile — direct side-effect, no post-hoc extraction
# ---------------------------------------------------------------------------


@tool(
    description=(
        "Silently saves a user preference. "
        "KEYS: 'preferred_club_slug', 'preferred_club_name', 'preferred_city', "
        "'court_type', 'duration', 'preferred_time', 'language'."
    )
)
def update_user_profile(
    key: Annotated[str, "Preference key."],
    value: Annotated[str, "Preference value."],
) -> Annotated[dict, "Confirmation that the preference was saved."]:
    """Mutates the live UserState in the current ContextVar context."""
    user_state = _wa_state_ctx.get()
    if user_state is not None:
        if key == "language":
            user_state.language = value
        else:
            user_state.profile[key] = value
    return {"status": "saved", "key": key, "value": value}


# ---------------------------------------------------------------------------
# Output model — replaces send_messages + send_poll + send_vote_link
# ---------------------------------------------------------------------------


class WAPoll(BaseModel):
    question: str
    slots: list[dict]
    court_type: str = "DOUBLE"


class WAVoteLink(BaseModel):
    question: str
    slots: list[dict]
    court_type: str = "DOUBLE"


class WAResponse(BaseModel):
    text_parts: list[str] = []
    poll: WAPoll | None = None
    vote_link: WAVoteLink | None = None

    @model_validator(mode="after")
    def _exclusive(self) -> "WAResponse":
        if self.poll is not None and self.vote_link is not None:
            raise ValueError("poll and vote_link are mutually exclusive")
        return self


@tool(
    description=(
        "Emit your complete response. Call exactly once as the final step. "
        "text_parts: ordered list of sequential WhatsApp messages. "
        "In groups with 2+ slots: set poll (below poll threshold) XOR vote_link (at/above threshold). "
        "Never set both. Never set poll or vote_link for a single slot — use text_parts only."
    )
)
def respond(
    response: Annotated[WAResponse, "The complete response to send."],
) -> dict:
    """Return the response payload for server.py to dispatch."""
    return response.model_dump()


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

WA_TOOLS = [
    find_slots,
    find_slots_date_range,
    create_booking_link,
    is_weekend,
    find_clubs_by_location,
    find_clubs_by_name,
    update_user_profile,
    respond,
]


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------


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

    voting_field = "poll" if poll_count < poll_threshold else "vote_link"
    voting_mechanic = (
        "once enough people vote for the same slot (2 for singles, 4 for doubles), "
        "I'll send the booking link!"
        if poll_count < poll_threshold
        else "click the link to vote on the web page"
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
        "put each part as a separate item in respond.text_parts instead of combining them.\n"
        "3. Always reply in the same language the user writes in.\n"
        "4. On first message: detect the user's language and call"
        " `update_user_profile('language', '<code>')` (e.g. 'de', 'en', 'es').\n"
        "5. ALWAYS call `respond` exactly once as your final step.\n\n"
        "WORKFLOW:\n"
        "1. Specific club mentioned? -> `find_clubs_by_name` (use SHORT name).\n"
        "2. City/Region mentioned? -> `find_clubs_by_location`.\n"
        "3. Availability needed?\n"
        "   - Single date -> `find_slots` (club slug + date).\n"
        "   - Multiple days ('next 3 days', 'this weekend', etc.) -> `find_slots_date_range`"
        " (start_date + end_date).\n"
        "4. Slots found (>0)? -> "
        + (
            f"If 2+ slots in a group: set respond.{voting_field} (see POLLS/VOTING section).\n"
            "   If exactly 1 slot, or in a DM: put the slot in respond.text_parts with the booking link.\n"
            if is_group
            else "Put them as a numbered list in respond.text_parts.\n"
        )
        + "5. No slots found? -> Tell the user with a sympathetic quip and suggest a different"
        " date or time.\n\n"
        + (
            f"POLLS/VOTING LINKS — MANDATORY in groups:\n"
            f"- ALWAYS set respond.{voting_field} whenever you have 2+ slot options.\n"
            f"- NEVER list slots as plain text in a group — always use respond.{voting_field}.\n"
            f"- Pass each slot dict from find_slots directly into respond.{voting_field}.slots"
            " (already has 'display' and 'booking_link').\n"
            f"- Set respond.{voting_field}.court_type='SINGLE' for singles courts, otherwise 'DOUBLE'.\n"
            f"- Always include at least one text_part alongside {voting_field} that explains the"
            f" voting mechanic:\n"
            f"  e.g. 'Vote for all slots that work for you — {voting_mechanic}'"
            " (threshold: 2 for singles, 4 for doubles).\n\n"
            if is_group
            else ""
        )
        + "PREFERENCES:\n"
        "- Detect new preferences (club, court, etc.) -> Call `update_user_profile` silently.\n"
        "- Known Club -> Call `update_user_profile` TWICE: once for `preferred_club_slug`,"
        " once for `preferred_club_name`."
        f"{profile_section}"
    )


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------


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
    """Extract the last AIMessage text from a LangGraph invoke result (fallback)."""
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


def extract_response(result: dict) -> WAResponse | None:
    """Return the WAResponse from the respond tool call, or None if not found."""
    payload = _extract_tool_message(result, respond.name)
    if payload is None:
        return None
    try:
        return WAResponse.model_validate(payload)
    except Exception:
        logger.warning("respond tool returned invalid WAResponse payload: %s", payload)
        return None
