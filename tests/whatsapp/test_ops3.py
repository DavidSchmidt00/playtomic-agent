from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_fire_alert_posts_to_webhook():
    """_fire_alert() should POST to WHATSAPP_ALERT_WEBHOOK_URL when set."""
    from playtomic_agent.whatsapp.server import _fire_alert

    mock_settings = MagicMock()
    mock_settings.whatsapp_alert_webhook_url = "https://example.com/hook"

    with patch("playtomic_agent.whatsapp.server.get_settings", return_value=mock_settings):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await _fire_alert(event="connect_failure", reason="TEMP_BANNED", message="Banned")

    mock_client.post.assert_called_once()
    call_kwargs = mock_client.post.call_args
    payload = call_kwargs.kwargs.get("json") or call_kwargs.args[1]
    assert payload["event"] == "connect_failure"
    assert payload["reason"] == "TEMP_BANNED"
    assert "timestamp" in payload


@pytest.mark.asyncio
async def test_fire_alert_noop_when_url_not_set():
    """_fire_alert() should do nothing when WHATSAPP_ALERT_WEBHOOK_URL is not set."""
    from playtomic_agent.whatsapp.server import _fire_alert

    mock_settings = MagicMock()
    mock_settings.whatsapp_alert_webhook_url = None

    with patch("playtomic_agent.whatsapp.server.get_settings", return_value=mock_settings):
        with patch("httpx.AsyncClient") as mock_client_cls:
            await _fire_alert(event="logged_out", reason="UNKNOWN", message="")

    mock_client_cls.assert_not_called()


@pytest.mark.asyncio
async def test_fire_alert_swallows_exception():
    """_fire_alert() should never raise even if the POST fails."""
    from playtomic_agent.whatsapp.server import _fire_alert

    mock_settings = MagicMock()
    mock_settings.whatsapp_alert_webhook_url = "https://example.com/hook"

    with patch("playtomic_agent.whatsapp.server.get_settings", return_value=mock_settings):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = Exception("Network error")
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            # Should not raise
            await _fire_alert(event="logged_out", reason="UNKNOWN", message="")
