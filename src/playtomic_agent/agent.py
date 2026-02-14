from datetime import datetime

from langchain.agents import create_agent
from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph.state import CompiledStateGraph

from playtomic_agent.config import get_settings
from playtomic_agent.tools import (
    create_booking_link,
    find_clubs_by_location,
    find_clubs_by_name,
    find_slots,
    is_weekend,
    update_user_profile,
)

# Load settings
settings = get_settings()

TOOLS = [
    find_slots,
    create_booking_link,
    is_weekend,
    find_clubs_by_location,
    find_clubs_by_name,
    update_user_profile,
]


def create_rate_limiter(requests_per_minute: int) -> InMemoryRateLimiter:
    """Creates a rate limiter for API requests.

    Args:
        requests_per_minute: The number of requests allowed per minute.

    Returns:
        InMemoryRateLimiter: An in-memory rate limiter instance.
    """
    return InMemoryRateLimiter(
        requests_per_second=requests_per_minute / 60,
        check_every_n_seconds=0.1,
        max_bucket_size=10,
    )


# Initialize language model with rate limiter
gemini = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    # model="gemini-3-flash-preview",
    google_api_key=settings.gemini_api_key,
    rate_limiter=create_rate_limiter(10),
)
llm = gemini


def _build_system_prompt(user_profile: dict | None = None) -> str:
    """Build the system prompt, optionally injecting user profile context."""
    profile_section = ""
    if user_profile:
        prefs = []
        if user_profile.get("preferred_club_name"):
            prefs.append(f"- Preferred club: {user_profile['preferred_club_name']} (slug: {user_profile.get('preferred_club_slug', 'unknown')})")
        if user_profile.get("preferred_city"):
            prefs.append(f"- Preferred city: {user_profile['preferred_city']}")
        if user_profile.get("court_type"):
            prefs.append(f"- Preferred court type: {user_profile['court_type']}")
        if user_profile.get("duration"):
            prefs.append(f"- Preferred duration: {user_profile['duration']} minutes")
        if user_profile.get("preferred_time"):
            prefs.append(f"- Preferred time: {user_profile['preferred_time']}")

        if prefs:
            profile_section = "\n\nUSER PREFERENCES (from previous sessions):\n" + "\n".join(prefs) + "\nUse these as defaults when the user doesn't specify. Do NOT ask for these values if they are already set."

    return f"""You are a Padel court finder assistant. Today is {datetime.now().strftime("%Y-%m-%d")}. Timezone: {settings.default_timezone}.

RULES:
- Only answer questions about Padel courts and bookings. Refuse anything else.
- NEVER make up club names, times, prices or links. Only use EXACT data from tools.

WORKFLOW:
1. If the user mentions a specific club name, use `find_clubs_by_name` with the SHORT core name (e.g. "Lemon Padel", NOT "Lemon Padel Club Limburg").
2. If the user asks about a city/region, use `find_clubs_by_location`.
3. To find available slots, use `find_slots` with the club slug and date.
4. The `find_slots` tool returns a dict with a "count" field and a "slots" list. If count > 0, slots ARE available — present them to the user.
5. Each slot has: `local_time` (already in local timezone), `court`, `duration`, `price`, and `booking_link` (a complete URL). Use these values EXACTLY as provided.
6. NEVER construct booking links yourself. Always use the `booking_link` from the slot data.
7. STOP after finding results for the specific club the user asked about. Do NOT search other clubs unless the user asks.

PREFERENCE MANAGEMENT:
- When you detect a new preference (club, court type, duration), silently call `update_user_profile`. Do NOT mention it in chat.
- Do NOT suggest preferences the user already has saved.

RESPONSE FORMAT:
- Keep responses SHORT. Answer only what was asked.
- Use **bold** for key info (club, date, time, price).
- For each slot, display as: **local_time** - duration min - **price** on court [Book here](booking_link)
- Do NOT suggest other clubs or add unsolicited information.{profile_section}"""


def create_playtomic_agent(user_profile: dict | None = None) -> CompiledStateGraph:
    """Create the playtomic agent with an optional user profile injected into the system prompt."""
    return create_agent(
        model=llm,
        name="playtomic_agent",
        tools=TOOLS,
        system_prompt=_build_system_prompt(user_profile),
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
