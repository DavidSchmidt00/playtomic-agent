"""Prometheus metrics for Padel Agent."""

from typing import Any

from prometheus_client import Counter, Gauge, Histogram
from prometheus_client import make_asgi_app as _make_asgi_app

# ── WhatsApp connection ──────────────────────────────────────────────────────
WA_CONNECTED = Gauge(
    "whatsapp_connected",
    "1 when connected to WhatsApp, 0 when disconnected",
)
WA_FAILURES = Counter(
    "whatsapp_connection_failures",
    "WhatsApp connection failure events",
    ["failure_type"],  # ban | logged_out | transient
)
WA_MESSAGES = Counter(
    "whatsapp_messages_processed",
    "WhatsApp messages passed to the agent",
)

# ── Playtomic API health ─────────────────────────────────────────────────────
PLAYTOMIC_REQUESTS = Counter(
    "playtomic_api_requests",
    "Playtomic API HTTP requests",
    ["endpoint", "status"],  # status: success | error
)
PLAYTOMIC_LATENCY = Histogram(
    "playtomic_api_latency_seconds",
    "Playtomic API request latency in seconds",
    ["endpoint"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0],
)
PLAYTOMIC_SCHEMA_ERRORS = Counter(
    "playtomic_api_schema_errors",
    "Playtomic API responses that failed Pydantic schema validation",
)

# ── LLM usage ───────────────────────────────────────────────────────────────
LLM_INPUT_TOKENS = Counter(
    "llm_input_tokens",
    "LLM input tokens consumed",
    ["channel"],  # web | whatsapp
)
LLM_OUTPUT_TOKENS = Counter(
    "llm_output_tokens",
    "LLM output tokens generated",
    ["channel"],
)
LLM_INVOCATIONS = Counter(
    "llm_invocations",
    "LLM agent invocations",
    ["channel"],
)
PLAYTOMIC_TOOL_CALLS = Counter(
    "playtomic_tool_calls",
    "Playtomic tool calls made by the agent",
    ["tool", "channel"],
)

_PLAYTOMIC_TOOLS = frozenset(
    {
        "find_slots",
        "find_slots_date_range",
        "find_clubs_by_name",
        "find_clubs_by_location",
    }
)


class UsageCallbackHandler:
    """LangChain callback that records Gemini token usage and tool calls to Prometheus."""

    def __init__(self, channel: str) -> None:
        self._channel = channel

    def on_llm_end(self, response: Any, **kwargs: object) -> None:
        LLM_INVOCATIONS.labels(channel=self._channel).inc()
        try:
            usage = response.generations[0][0].message.usage_metadata
            if usage:
                LLM_INPUT_TOKENS.labels(channel=self._channel).inc(usage.get("input_tokens", 0))
                LLM_OUTPUT_TOKENS.labels(channel=self._channel).inc(usage.get("output_tokens", 0))
        except (IndexError, AttributeError, TypeError):
            pass  # Graceful degradation: metrics unavailable, don't crash

    def on_tool_end(self, output: object, *, name: str = "", **kwargs: object) -> None:
        if name in _PLAYTOMIC_TOOLS:
            PLAYTOMIC_TOOL_CALLS.labels(tool=name, channel=self._channel).inc()


metrics_app = _make_asgi_app()
