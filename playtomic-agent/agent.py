from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
from langchain_core.rate_limiters import InMemoryRateLimiter
import os
from tools import find_slots, create_booking_link, is_weekend
from datetime import datetime

def create_rate_limiter(requests_per_minute: int) -> InMemoryRateLimiter:
    """Creates a rate limiter for API requests.

    Args:
        requests_per_minute (int): The number of requests allowed per minute.

    Returns:
        InMemoryRateLimiter: An in-memory rate limiter instance.
    """
    return InMemoryRateLimiter(
        requests_per_second=requests_per_minute / 60,
        check_every_n_seconds=0.1,
        max_bucket_size=10,
    )

# --- LLM and API Key Configuration ---
# Load API keys from environment variables
GEMINI_API_KEY_FREE = os.environ.get("GEMINI_API_KEY_1")
GEMINI_API_KEY_PAID = os.environ.get("GEMINI_API_KEY_2")
if not GEMINI_API_KEY_FREE or not GEMINI_API_KEY_PAID:
    raise ValueError("GEMINI_API_KEY_1 or GEMINI_API_KEY_2 is not set")

# Initialize different language models with appropriate rate limiters
gemini_3_flash_free = ChatGoogleGenerativeAI(model="gemini-3-flash-preview", google_api_key=GEMINI_API_KEY_FREE, rate_limiter=create_rate_limiter(100))
gemini_2_5_flash_paid = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=GEMINI_API_KEY_PAID, rate_limiter=create_rate_limiter(1000))
gemini_2_5_pro = ChatGoogleGenerativeAI(model="gemini-2.5-pro", google_api_key=GEMINI_API_KEY_PAID, rate_limiter=create_rate_limiter(150))

# Select the language model to be used by the agents
llm = gemini_3_flash_free

# --- Agent Creation ---
# Create individual agents using the create_react_agent function from langgraph.
# Each agent is configured with a language model, name, tools, and a system prompt.
playtomic_agent = create_agent(
    model=llm,
    name="playtomic_agent",
    tools=[find_slots, create_booking_link, is_weekend],
    system_prompt=f"""You are an assistant that helps people finding available padel courts. 
                    Todays date is {datetime.now().strftime("%Y-%m-%d")}.
                    You are located in the timezone Europe/Berlin.
                    Do not format the output."""
)

if __name__ == "__main__":
    for chunk in playtomic_agent.stream(  
    {"messages": [{"role": "user", "content": """
                                            Search for the next available 90 minutes slot for a double court at lemon-padel-club on 
                                            between 18:00 and 20:00. Search until you found one.
                                            """}]},
    stream_mode="updates",):
        for step, data in chunk.items():
            print(f"step: {step}")
            print(f"content: {data['messages'][-1].content_blocks[0].text}")
