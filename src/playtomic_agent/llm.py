from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_google_genai import ChatGoogleGenerativeAI

from playtomic_agent.config import get_settings


def create_rate_limiter(requests_per_minute: int) -> InMemoryRateLimiter:
    """Create a rate limiter for API requests.

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


settings = get_settings()

gemini = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
    google_api_key=settings.gemini_api_key,
    rate_limiter=create_rate_limiter(10),
)
