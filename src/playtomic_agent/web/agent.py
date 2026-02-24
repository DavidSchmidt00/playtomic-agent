from datetime import datetime

from langchain.agents import create_agent
from langgraph.graph.state import CompiledStateGraph

from playtomic_agent.config import get_settings
from playtomic_agent.llm import gemini
from playtomic_agent.tools import (
    create_booking_link,
    find_clubs_by_location,
    find_clubs_by_name,
    find_slots,
    is_weekend,
    suggest_next_steps,
    update_user_profile,
)

settings = get_settings()

TOOLS = [
    find_slots,
    create_booking_link,
    is_weekend,
    find_clubs_by_location,
    find_clubs_by_name,
    update_user_profile,
    suggest_next_steps,
]


def _build_system_prompt(user_profile: dict | None = None, language: str | None = None) -> str:
    """Build the system prompt with optional user profile context and language."""
    profile_section = ""
    if user_profile:
        prefs = []
        if user_profile.get("preferred_club_name"):
            prefs.append(
                f"- Preferred club: {user_profile['preferred_club_name']} (slug: {user_profile.get('preferred_club_slug', 'unknown')})"
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
                + "\nUse these as defaults when the user doesn't specify. Do NOT ask for these values if they are already set."
            )

    lang_map = {
        "de": "German",
        "en": "English",
        "es": "Spanish",
        "fr": "French",
        "it": "Italian",
        "pt": "Portuguese",
        "nl": "Dutch",
    }

    # Use provided language or fall back to context/settings
    if not language:
        try:
            from playtomic_agent.context import get_language

            language = get_language()
        except ImportError:
            language = "en"

    lang_name = lang_map.get(language, language)

    return f"""You are a Padel court finder assistant. Today: {datetime.now().strftime("%Y-%m-%d")}. Timezone: {settings.default_timezone}. Language: {lang_name}.

GOAL: help users find and book Padel courts.

RULES:
1. ONLY answer about Padel courts/bookings.
2. NEVER invent data (names, times, prices, links). Use EXACT tool outputs.

WORKFLOW:
1. Specific club mentioned? -> `find_clubs_by_name` (use SHORT name).
2. City/Region mentioned? -> `find_clubs_by_location`.
3. Availability needed? -> `find_slots` (club slug + date).
4. Results found (>0 slots)? -> Show top 5 slots. Ask to see more if needed.
   - Format: **HH:MM** - DURATION min - **PRICE** - [Book](booking_link)
   - NEVER construct links manually. Use `booking_link` from tool.
5. Multiple options/decisions? -> `suggest_next_steps`.

PREFERENCES:
- Detect new preferences (club, court, etc.) -> Call `update_user_profile` silently.
- Known Club -> Call `update_user_profile` TWICE: once for `preferred_club_slug`, once for `preferred_club_name`.

keep responses SHORT and formatting CLEAN.{profile_section}"""


def create_playtomic_agent(
    user_profile: dict | None = None, language: str | None = None
) -> CompiledStateGraph:
    """Create the playtomic agent with an optional user profile injected into the system prompt."""
    return create_agent(
        model=gemini,
        name="playtomic_agent",
        tools=TOOLS,
        system_prompt=_build_system_prompt(user_profile, language=language),
    )


# Default agent instance (no profile) for backward compatibility
playtomic_agent: CompiledStateGraph = create_playtomic_agent()

if __name__ == "__main__":
    for chunk in playtomic_agent.stream(
        {
            "messages": [
                {
                    "role": "user",
                    "content": """
                                            Search for the next available 90 minutes slot for a double court at lemon-padel-club on
                                            after 12:00. Search until you found one.
                                            """,
                }
            ]
        },
        stream_mode="updates",
    ):
        for step, data in chunk.items():
            print(f"\nstep: {step}\n")
            print(data)
