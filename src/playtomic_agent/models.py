"""Data models for Playtomic clubs, courts, and slots."""

from datetime import datetime
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field, field_validator

if TYPE_CHECKING:
    pass


class Court(BaseModel):
    """Represents a Padel court."""

    id: str = Field(description="Unique identifier for the court")
    name: str = Field(description="Display name of the court")
    type: Literal["single", "double"] = Field(description="Court type (single or double)")

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, v: str) -> str:
        """Normalize court type to lowercase."""
        if isinstance(v, str):
            return v.lower()
        return v

    def __str__(self) -> str:
        return f"{self.name} ({self.id})"


class Club(BaseModel):
    """Represents a Playtomic club with its courts."""

    slug: str = Field(description="URL-friendly club identifier")
    name: str = Field(description="Display name of the club")
    club_id: str = Field(description="Unique identifier for the club")
    timezone: str = Field(description="Timezone of the club location")
    courts: list[Court] = Field(default_factory=list, description="List of courts at this club")

    def __str__(self) -> str:
        header = f" {self.name} ({self.slug}) "
        club_id_line = f" {self.club_id} "
        line = "#" * len(header)
        courts_str = "\n".join(f"  - {c}" for c in self.courts)
        return f"\n{line}\n{header}\n{club_id_line}\n{line}\nCourts:\n{courts_str}"

    def get_court_by_id(self, court_id: str) -> Court | None:
        """Get a court by its ID.

        Args:
            court_id: The court ID to search for

        Returns:
            Court if found, None otherwise
        """
        for court in self.courts:
            if court.id == court_id:
                return court
        return None

    def get_court_by_type(self, court_type: Literal["single", "double"]) -> list[Court]:
        """Get all courts of a specific type.

        Args:
            court_type: The court type to filter by

        Returns:
            List of courts matching the type
        """
        return [court for court in self.courts if court.type == court_type]


class Slot(BaseModel):
    """Represents an available time slot for a court."""

    club_id: str = Field(description="ID of the club")
    court_id: str = Field(description="ID of the court")
    court_name: str = Field(description="Name of the court")
    time: datetime = Field(description="Start time of the slot (UTC)")
    duration: int = Field(description="Duration in minutes")
    price: str = Field(description="Price of the slot")

    def get_link(self) -> str:
        """Generate booking link for this slot.

        Returns:
            URL to book this slot on Playtomic
        """
        # Late import to avoid circular dependency
        from playtomic_agent.client.utils import create_booking_link

        return create_booking_link(
            self.club_id,
            self.court_id,
            self.time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            self.duration,
        )

    def to_json(self) -> dict:
        """Convert slot to JSON-serializable dict.

        Returns:
            Dictionary representation of the slot
        """
        return {
            "club_id": self.club_id,
            "court_id": self.court_id,
            "court_name": self.court_name,
            "time": self.time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "duration": self.duration,
            "price": self.price,
        }


class AvailableSlots(BaseModel):
    """Collection of available slots for a club on a specific date."""

    club_id: str = Field(description="ID of the club")
    date: str = Field(description="Date for these slots (YYYY-MM-DD)")  # TODO: use datetime
    slots: list[Slot] = Field(default_factory=list, description="List of available slots")
