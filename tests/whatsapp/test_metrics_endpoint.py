from fastapi.testclient import TestClient


def test_metrics_endpoint_returns_200():
    from playtomic_agent.whatsapp.server import webhook_app

    client = TestClient(webhook_app)
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "whatsapp_connected" in resp.text
