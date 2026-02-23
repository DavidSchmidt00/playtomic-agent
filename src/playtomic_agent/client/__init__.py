"""Playtomic API client module.

Provides functionality to interact with the Playtomic API for
fetching club information and available court slots.
"""

# Import at module level causes circular dependency with models
# Use direct imports instead: from playtomic_agent.client.api import find_slots
from playtomic_agent.client.exceptions import (
    APIError,
    ClubNotFoundError,
    MultipleClubsFoundError,
    PlaytomicError,
    SlotNotFoundError,
    ValidationError,
)

__all__ = [
    "api",
    "utils",
    "exceptions",
    # Exception classes
    "PlaytomicError",
    "ClubNotFoundError",
    "MultipleClubsFoundError",
    "APIError",
    "ValidationError",
    "SlotNotFoundError",
]
