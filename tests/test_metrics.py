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
