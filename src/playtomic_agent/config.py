"""Configuration management for playtomic-agent using pydantic-settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent.parent.parent / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # LLM provider selection
    llm_provider: Literal["gemini", "nvidia"] = Field(
        default="gemini",
        alias="LLM_PROVIDER",
        description="Which LLM provider to use: 'gemini' or 'nvidia'",
    )
    default_model: str | None = Field(
        default=None,
        alias="DEFAULT_MODEL",
        description="Override the default model for the selected provider",
    )

    # Gemini
    gemini_api_key: str | None = Field(
        default=None, alias="GEMINI_API_KEY", description="Google Gemini API key"
    )
    gemini_rpm: int = Field(
        default=500,
        alias="GEMINI_RPM",
        description="Client-side rate limit for Gemini API calls (requests per minute). Free tier: 15, paid: ~1000.",
    )

    # NVIDIA
    nvidia_api_key: str | None = Field(
        default=None, alias="NVIDIA_API_KEY", description="NVIDIA API key (nvapi-…)"
    )
    nvidia_rpm: int = Field(
        default=40,
        alias="NVIDIA_RPM",
        description="Client-side rate limit for NVIDIA API calls (requests per minute).",
    )

    # Default Configuration
    default_timezone: str = Field(
        default="Europe/Berlin",
        alias="DEFAULT_TIMEZONE",
        description="Default timezone for the application",
    )

    # API Configuration
    playtomic_api_base_url: str = Field(
        default="https://api.playtomic.io/v1",
        alias="PLAYTOMIC_API_BASE_URL",
        description="Base URL for Playtomic API",
    )

    # Agent
    agent_timeout_seconds: int = Field(
        default=60,
        alias="AGENT_TIMEOUT_SECONDS",
        description="Maximum seconds to wait for the agent to respond before giving up.",
    )

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL", description="Logging level")

    # WhatsApp integration (optional — only required when running whatsapp-agent)
    whatsapp_session_db: str = Field(
        default="data/whatsapp_session.db",
        alias="WHATSAPP_SESSION_DB",
        description="Path to the SQLite file where Neonize stores the WhatsApp session",
    )
    whatsapp_db_path: str = Field(
        default="data/whatsapp_users.db",
        alias="WHATSAPP_STORAGE_PATH",
        description="Path to the SQLite DB storing per-user WhatsApp state",
    )
    whatsapp_clear_storage_on_start: bool = Field(
        default=False,
        alias="WHATSAPP_CLEAR_STORAGE_ON_START",
        description="If true, delete the user state DB on startup (useful for resetting state in production)",
    )
    whatsapp_phone_number: str | None = Field(
        default=None,
        alias="WHATSAPP_PHONE_NUMBER",
        description="Phone number (with country code, e.g. +49123456789) to use for pairing code login instead of QR scan",
    )
    whatsapp_device_os: str = Field(
        default="Chrome",
        alias="WHATSAPP_DEVICE_OS",
        description="Device OS name reported to WhatsApp (avoids the default 'Neonize' fingerprint)",
    )
    whatsapp_device_platform: str = Field(
        default="CHROME",
        alias="WHATSAPP_DEVICE_PLATFORM",
        description=(
            "DeviceProps.PlatformType name reported to WhatsApp. "
            "Valid values: CHROME, FIREFOX, SAFARI, EDGE, DESKTOP, IOS_PHONE, ANDROID_PHONE, …"
        ),
    )
    whatsapp_send_delay_wpm: float = Field(
        default=400.0,
        alias="WHATSAPP_SEND_DELAY_WPM",
        description=(
            "Simulated typing speed (words per minute) used to calculate the post-agent send delay. "
            "Set to 0 to disable."
        ),
    )
    whatsapp_webhook_port: int = Field(
        default=8081,
        alias="WHATSAPP_WEBHOOK_PORT",
        description="Port for the internal WhatsApp webhook server.",
    )

    # Web/WhatsApp Integration
    web_api_url: str = Field(
        default="http://localhost:8082",
        alias="WEB_API_URL",
        description="URL of the Web API backend.",
    )
    whatsapp_webhook_url: str = Field(
        default="http://localhost:8081/api/webhook/consensus",
        alias="WHATSAPP_WEBHOOK_URL",
        description="URL to Ping when a web vote reaches consensus.",
    )
    vote_link_poll_threshold: int = Field(
        default=3,
        alias="VOTE_LINK_POLL_THRESHOLD",
        description="Native polls per group before switching to web voting links.",
    )
    web_public_base_url: str = Field(
        default="https://padelagent.de",
        alias="WEB_PUBLIC_BASE_URL",
        description="Public base URL for sharing vote links outside the dev environment.",
    )

    # Alerting (OPS-3)
    whatsapp_alert_webhook_url: str | None = Field(
        default=None,
        alias="WHATSAPP_ALERT_WEBHOOK_URL",
        description="HTTP webhook URL to POST when WhatsApp disconnects or is banned.",
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Returns:
        Settings instance with environment variables loaded
    """
    return Settings()
