from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from playtomic_utils import create_booking_link

@dataclass
class Court:
    id: str
    name: str
    type: Literal["single", "double"]

    def __str__(self) -> str:
        return f"{self.name} ({self.id})"

@dataclass
class Club:
    slug: str
    name: str
    club_id: str
    timezone: str
    courts: list[Court] = field(default_factory=list)

    def __str__(self) -> str:
        header = f" {self.name} ({self.slug}) "
        club_id = f" {self.club_id} "
        line = "#" * len(header)
        courts = "\n".join(f"  - {c}" for c in self.courts)
        return f"\n{line}\n{header}\n{club_id}\n{line}\nCourts:\n{courts}"

    def get_court_by_id(self, court_id: str) -> Court | None:
        for court in self.courts:
            if court.id == court_id:
                return court
        return None
    
    def get_court_by_type(self, court_type: Literal["single", "double"]) -> list[Court]:
        return [court for court in self.courts if court.type == court_type]

@dataclass
class Slot:
    club_id: str
    court_id: str
    court_name: str
    time: datetime
    duration: int
    price: str

    def get_link(self) -> str:
        return create_booking_link(self.club_id, self.court_id, self.time.strftime("%Y-%m-%dT%H:%M:%S.000Z"), self.duration)

    def to_json(self) -> dict:
        return {
            "club_id": self.club_id,
            "court_id": self.court_id,
            "court_name": self.court_name,
            "time": self.time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "duration": self.duration,
            "price": self.price
        }

@dataclass
class AvailableSlots:
    club_id: str
    date: datetime
    slots: list[Slot] = field(default_factory=list)
