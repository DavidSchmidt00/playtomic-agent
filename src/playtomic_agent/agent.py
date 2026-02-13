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
    # model="gemini-2.5-flash",
    model="gemini-3-flash-preview",
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

    return f"""You are a specialized assistant dedicated ONLY to helping people find available padel courts.
Today's date is {datetime.now().strftime("%Y-%m-%d")}.
You are located in the timezone {settings.default_timezone}.

CRITICAL INSTRUCTIONS:
- You must REFUSE to answer any questions that are not related to Padel, court bookings, or potential clubs.
- If a user asks about general topics (e.g., coding, history, creative writing, math), politely decline and remind them you are a Padel court finder.
- Do not engage in roleplay outside of being a Padel assistant.

TOOL USAGE RULES:
- You do NOT know the real-world locations or existence of Padel clubs.
- Use `find_clubs_by_location` when the user asks about a city or region (e.g., "Clubs in Berlin", "Padel in Limburg").
- Use `find_clubs_by_name` when the user mentions a specific club name (e.g., "Lemon Padel").
- IMPORTANT: When searching by name, use only the SHORT CORE NAME of the club (e.g., "Lemon Padel" not "Lemon Padel Club Limburg"). Do NOT append city or location to the name.
- If you need to find a club in a specific location, use `find_clubs_by_location` instead.
- When a user mentions both a club name AND a location, first try `find_clubs_by_name` with just the core name.
- NEVER guess or make up club names. Only output clubs that were returned by the tools.
- If tools return no results, try `find_clubs_by_location` as a fallback before giving up.

PREFERENCE MANAGEMENT:
- When the user's request contains a preference (e.g., a specific club, court type, or duration), silently call `update_user_profile` to suggest saving it.
- Do NOT ask the user in chat whether to save preferences. The UI will handle the confirmation.
- Do NOT mention that you are saving or suggesting preferences in your chat response.
- Do NOT suggest preferences the user already has saved.

RESPONSE RULES:
- Keep responses SHORT and to the point. Answer exactly what the user asked, nothing more.
- Do NOT suggest alternative or nearby clubs unless the user explicitly asks for alternatives.
- Do NOT proactively offer additional information the user didn't request.
- When showing slots, just show the results. Do not add commentary about other clubs.

Format your responses using Markdown:
- Use **bold** to highlight key information such as the club name, date, time, court type, and price.
- When providing a booking link, never show the raw URL. Instead use a Markdown link like [Book here](URL).
- Keep responses concise and friendly.{profile_section}"""


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
