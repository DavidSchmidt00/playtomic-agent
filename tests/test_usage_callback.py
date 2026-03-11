from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult


def _make_llm_result(input_tokens: int, output_tokens: int) -> LLMResult:
    """Create a fake LLMResult with Gemini-style usage_metadata."""
    msg = AIMessage(
        content="test",
        usage_metadata={
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        },
    )
    gen = ChatGeneration(message=msg)
    return LLMResult(generations=[[gen]])


def _get_value(name: str, labels: dict | None = None) -> float:
    from prometheus_client import REGISTRY

    for metric in REGISTRY.collect():
        for sample in metric.samples:
            if sample.name == name:
                if labels is None or all(sample.labels.get(k) == v for k, v in labels.items()):
                    return sample.value
    return 0.0


def test_on_llm_end_increments_token_counters():
    from playtomic_agent.metrics import UsageCallbackHandler

    handler = UsageCallbackHandler(channel="web")
    before_in = _get_value("llm_input_tokens_total", {"channel": "web"})
    before_out = _get_value("llm_output_tokens_total", {"channel": "web"})

    handler.on_llm_end(_make_llm_result(120, 45))

    assert _get_value("llm_input_tokens_total", {"channel": "web"}) == before_in + 120
    assert _get_value("llm_output_tokens_total", {"channel": "web"}) == before_out + 45


def test_on_llm_end_increments_invocation_counter():
    from playtomic_agent.metrics import UsageCallbackHandler

    handler = UsageCallbackHandler(channel="whatsapp")
    before = _get_value("llm_invocations_total", {"channel": "whatsapp"})
    handler.on_llm_end(_make_llm_result(10, 5))
    assert _get_value("llm_invocations_total", {"channel": "whatsapp"}) == before + 1


def test_on_tool_end_counts_playtomic_tools():
    from playtomic_agent.metrics import UsageCallbackHandler

    handler = UsageCallbackHandler(channel="web")
    before = _get_value("playtomic_tool_calls_total", {"tool": "find_slots", "channel": "web"})
    handler.on_tool_end("result", name="find_slots")
    assert (
        _get_value("playtomic_tool_calls_total", {"tool": "find_slots", "channel": "web"})
        == before + 1
    )


def test_on_tool_end_ignores_non_playtomic_tools():
    from playtomic_agent.metrics import UsageCallbackHandler

    handler = UsageCallbackHandler(channel="web")
    before = _get_value(
        "playtomic_tool_calls_total", {"tool": "suggest_next_steps", "channel": "web"}
    )
    handler.on_tool_end("result", name="suggest_next_steps")
    # counter should not exist or remain unchanged
    assert (
        _get_value("playtomic_tool_calls_total", {"tool": "suggest_next_steps", "channel": "web"})
        == before
    )


def test_on_llm_end_handles_missing_usage_metadata_gracefully():
    from playtomic_agent.metrics import UsageCallbackHandler

    handler = UsageCallbackHandler(channel="web")
    msg = AIMessage(content="no metadata")
    result = LLMResult(generations=[[ChatGeneration(message=msg)]])
    # Should not raise
    handler.on_llm_end(result)
