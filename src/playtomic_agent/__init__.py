"""Playtomic Agent - AI-powered Padel court slot finder.

This package provides tools to search for available Padel court slots
on Playtomic using AI-powered natural language interaction.
"""

__version__ = "0.1.0"

from playtomic_agent.config import Settings, get_settings
from playtomic_agent.models import Club, Court, Slot

__all__ = [
    "Club",
    "Court",
    "Slot",
    "Settings",
    "get_settings",
]
