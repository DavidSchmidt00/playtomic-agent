from langchain_core.language_models import BaseChatModel
from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_nvidia_ai_endpoints import ChatNVIDIA

from playtomic_agent.config import get_settings

_PROVIDER_DEFAULT_MODELS: dict[str, str] = {
    "gemini": "gemini-3.0-flash-preview",
    "nvidia": "deepseek-ai/deepseek-v3.1-terminus",
}


def create_rate_limiter(requests_per_minute: int) -> InMemoryRateLimiter:
    return InMemoryRateLimiter(
        requests_per_second=requests_per_minute / 60,
        check_every_n_seconds=0.1,
        max_bucket_size=10,
    )


def create_llm() -> BaseChatModel:
    """Instantiate the configured LLM (Gemini or NVIDIA)."""
    settings = get_settings()
    model = settings.default_model or _PROVIDER_DEFAULT_MODELS[settings.llm_provider]

    if settings.llm_provider == "nvidia":
        kwargs: dict = {"model": model, "rate_limiter": create_rate_limiter(settings.nvidia_rpm)}
        if settings.nvidia_api_key:
            kwargs["api_key"] = settings.nvidia_api_key
        return ChatNVIDIA(**kwargs)

    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=settings.gemini_api_key,
        rate_limiter=create_rate_limiter(settings.gemini_rpm),
    )


llm = create_llm()
