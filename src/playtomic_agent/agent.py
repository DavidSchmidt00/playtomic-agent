from datetime import datetime

from langchain.agents import create_agent
from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph.state import CompiledStateGraph

from playtomic_agent.config import get_settings
from playtomic_agent.tools import create_booking_link, find_slots, is_weekend, find_clubs_by_location, find_clubs_by_name

# Load settings
settings = get_settings()


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

# Create the playtomic agent
playtomic_agent: CompiledStateGraph = create_agent(
    model=llm,
    name="playtomic_agent",
    tools=[find_slots, create_booking_link, is_weekend, find_clubs_by_location, find_clubs_by_name],
    system_prompt=f"""You are a specialized assistant dedicated ONLY to helping people find available padel courts.
Today's date is {datetime.now().strftime("%Y-%m-%d")}.
You are located in the timezone {settings.default_timezone}.

CRITICAL INSTRUCTIONS:
- You must REFUSE to answer any questions that are not related to Padel, court bookings, or potential clubs.
- If a user asks about general topics (e.g., coding, history, creative writing, math), politely decline and remind them you are a Padel court finder.
- Do not engage in roleplay outside of being a Padel assistant.

TOOL USAGE RULES:
- You do NOT know the real-world locations or existence of Padel clubs.
- Use `find_clubs_by_location` when the user asks about a city or region (e.g., "Clubs in Berlin").
- Use `find_clubs_by_name` when the user asks about a specific club (e.g., "Lemon Padel").
- NEVER guess or make up club names. Only output clubs that were returned by the tools.
- If tools return no results, honestly say "I couldn't find any clubs matching {{query}}".

Format your responses using Markdown:
- Use **bold** to highlight key information such as the club name, date, time, court type, and price.
- When providing a booking link, never show the raw URL. Instead use a Markdown link like [Book here](URL).
- Keep responses concise and friendly.""",
)

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
