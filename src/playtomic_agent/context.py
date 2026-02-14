"""Per-request context variables for region settings.

These are set by the API layer before the agent runs, and read by tools
to get the correct country/language/timezone for the current request.
Falls back to settings defaults when not set.
"""

from contextvars import ContextVar

from playtomic_agent.config import get_settings

# ContextVars — set per-request, read by tools
_country_var: ContextVar[str | None] = ContextVar("country", default=None)
_language_var: ContextVar[str] = ContextVar("language", default="en")
_timezone_var: ContextVar[str] = ContextVar("timezone", default="UTC")


def set_request_region(
    country: str | None = None,
    language: str | None = None,
    timezone: str | None = None,
) -> None:
    """Set region context for the current request."""
    settings = get_settings()
    _country_var.set(country)
    _language_var.set(language or "en")
    _timezone_var.set(timezone or settings.default_timezone)


def get_country() -> str | None:
    """Get the country code for the current request."""
    return _country_var.get()


def get_language() -> str:
    """Get the language for the current request."""
    return _language_var.get()


def get_timezone() -> str:
    """Get the timezone for the current request."""
    return _timezone_var.get()
