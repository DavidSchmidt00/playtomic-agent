import os
from unittest.mock import patch


def test_alert_webhook_url_defaults_to_none():
    from playtomic_agent.config import Settings

    with patch.dict(os.environ, {}, clear=True):
        s = Settings()
        assert s.whatsapp_alert_webhook_url is None


def test_alert_webhook_url_reads_from_env():
    from playtomic_agent.config import Settings

    with patch.dict(os.environ, {"WHATSAPP_ALERT_WEBHOOK_URL": "https://example.com/hook"}):
        s = Settings()
        assert s.whatsapp_alert_webhook_url == "https://example.com/hook"
