"""Tests for PlaytomicClient Prometheus instrumentation."""

import responses as responses_lib
from prometheus_client import REGISTRY

from playtomic_agent.client.api import PlaytomicClient
from playtomic_agent.client.exceptions import APIError


def _get_sample_value(name: str, labels: dict | None = None) -> float:
    for metric in REGISTRY.collect():
        for sample in metric.samples:
            if sample.name == name:
                if labels is None or all(sample.labels.get(k) == v for k, v in labels.items()):
                    return sample.value
    return 0.0


@responses_lib.activate
def test_successful_get_club_increments_success_counter(mock_api_response_club):
    responses_lib.add(
        responses_lib.GET,
        "https://api.playtomic.io/v1/tenants",
        json=mock_api_response_club,
        status=200,
    )
    before = _get_sample_value(
        "playtomic_api_requests_total", {"endpoint": "tenants", "status": "success"}
    )
    with PlaytomicClient() as client:
        client.get_club(slug="test-club")
    after = _get_sample_value(
        "playtomic_api_requests_total", {"endpoint": "tenants", "status": "success"}
    )
    assert after == before + 1.0


@responses_lib.activate
def test_failed_get_club_increments_error_counter():
    responses_lib.add(
        responses_lib.GET,
        "https://api.playtomic.io/v1/tenants",
        status=503,
    )
    before = _get_sample_value(
        "playtomic_api_requests_total", {"endpoint": "tenants", "status": "error"}
    )
    with PlaytomicClient() as client:
        try:
            client.get_club(slug="bad-club")
        except APIError:
            pass
    after = _get_sample_value(
        "playtomic_api_requests_total", {"endpoint": "tenants", "status": "error"}
    )
    assert after == before + 1.0
