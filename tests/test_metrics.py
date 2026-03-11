from prometheus_client import REGISTRY


def _get_sample_value(name: str, labels: dict | None = None) -> float:
    """Read a metric value from the global Prometheus registry.

    Matches on sample.name so Counter metrics work regardless of whether the
    name was registered with or without the automatic '_total' suffix.
    """
    for metric in REGISTRY.collect():
        for sample in metric.samples:
            if sample.name == name:
                if labels is None or all(sample.labels.get(k) == v for k, v in labels.items()):
                    return sample.value
    return 0.0


def test_whatsapp_connected_gauge_exists():
    from playtomic_agent.metrics import WA_CONNECTED

    # gauge should start at 0 (unset)
    assert WA_CONNECTED._value.get() == 0.0


def test_whatsapp_connected_gauge_can_set():
    from playtomic_agent.metrics import WA_CONNECTED

    WA_CONNECTED.set(1)
    assert WA_CONNECTED._value.get() == 1.0
    WA_CONNECTED.set(0)
    assert WA_CONNECTED._value.get() == 0.0


def test_whatsapp_failures_counter_exists():
    from playtomic_agent.metrics import WA_FAILURES

    before = _get_sample_value(
        "whatsapp_connection_failures_total",
        {"failure_type": "ban"},
    )
    WA_FAILURES.labels(failure_type="ban").inc()
    after = _get_sample_value(
        "whatsapp_connection_failures_total",
        {"failure_type": "ban"},
    )
    assert after == before + 1.0


def test_playtomic_request_counter_exists():
    from playtomic_agent.metrics import PLAYTOMIC_REQUESTS

    before = _get_sample_value(
        "playtomic_api_requests_total",
        {"endpoint": "tenants", "status": "success"},
    )
    PLAYTOMIC_REQUESTS.labels(endpoint="tenants", status="success").inc()
    after = _get_sample_value(
        "playtomic_api_requests_total",
        {"endpoint": "tenants", "status": "success"},
    )
    assert after == before + 1.0


def test_playtomic_latency_histogram_exists():
    from playtomic_agent.metrics import PLAYTOMIC_LATENCY

    PLAYTOMIC_LATENCY.labels(endpoint="availability").observe(0.5)
    # just check no exception raised


def test_playtomic_schema_error_counter_exists():
    from playtomic_agent.metrics import PLAYTOMIC_SCHEMA_ERRORS

    before = _get_sample_value("playtomic_api_schema_errors_total")
    PLAYTOMIC_SCHEMA_ERRORS.inc()
    after = _get_sample_value("playtomic_api_schema_errors_total")
    assert after == before + 1.0


def test_llm_input_tokens_counter_exists():
    from playtomic_agent.metrics import LLM_INPUT_TOKENS

    before = _get_sample_value("llm_input_tokens_total", {"channel": "web"})
    LLM_INPUT_TOKENS.labels(channel="web").inc(100)
    after = _get_sample_value("llm_input_tokens_total", {"channel": "web"})
    assert after == before + 100.0


def test_llm_output_tokens_counter_exists():
    from playtomic_agent.metrics import LLM_OUTPUT_TOKENS

    before = _get_sample_value("llm_output_tokens_total", {"channel": "whatsapp"})
    LLM_OUTPUT_TOKENS.labels(channel="whatsapp").inc(50)
    after = _get_sample_value("llm_output_tokens_total", {"channel": "whatsapp"})
    assert after == before + 50.0
