"""Playtomic Agent - AI-powered Padel court slot finder.

This package provides tools to search for available Padel court slots
on Playtomic using AI-powered natural language interaction.
"""

__version__ = "0.1.0"

from playtomic_agent.models import AvailableSlots, Club, Court, Slot
from playtomic_agent.config import Settings, get_settings

__all__ = [
    "Club",
    "Court",
    "Slot",
    "AvailableSlots",
    "Settings",
    "get_settings",
]
