"""Configuration management for playtomic-agent using pydantic-settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent.parent.parent / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # API Key
    gemini_api_key: str = Field(
        alias="GEMINI_API_KEY", 
        description="Google Gemini API key"
    )

    # Default Configuration
    default_timezone: str = Field(
        default="Europe/Berlin",
        alias="DEFAULT_TIMEZONE",
        description="Default timezone for the application"
    )

    # API Configuration
    playtomic_api_base_url: str = Field(
        default="https://api.playtomic.io/v1",
        alias="PLAYTOMIC_API_BASE_URL",
        description="Base URL for Playtomic API"
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        alias="LOG_LEVEL",
        description="Logging level"
    )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance.
    
    Returns:
        Settings instance with environment variables loaded
    """
    return Settings()
