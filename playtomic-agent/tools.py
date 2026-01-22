from langchain_core.tools import tool
from typing import Literal, Annotated
import playtomic_client.client
from playtomic_client.models import Slot
from datetime import datetime
from zoneinfo import ZoneInfo
import playtomic_client.utils

@tool(description="Finds available slots for a specific club and date and filters them by court type, start time and duration.")
def find_slots(club_slug: Annotated[str, "The slug of the club"],
               date: Annotated[str, "The date to check (YYYY-MM-DD)"],
               court_type: Annotated[Literal["SINGLE", "DOUBLE"] | None, "Optional: The type of court to filter by (SINGLE, DOUBLE)"] = None, 
               start_time: Annotated[str | None, "Optional: The start time to filter by (HH:MM)"] = None,
               end_time: Annotated[str | None, "Optional: The end time to filter by (HH:MM)"] = None,
               timezone: Annotated[str | None, "Optional: The timezone to use. Must be provided if start_time or end_time is set."] = None,
               duration: Annotated[int | None, "Optional: The duration to filter by (minutes)"] = None,
               print_results: Annotated[bool, "Optional: Whether to print the results"] = False) -> Annotated[list[Slot] | None, "The filtered slots."]:
    return playtomic_client.find_slots(club_slug=club_slug,
                                       date=date,
                                       court_type=court_type,
                                       start_time=start_time,
                                       end_time=end_time,
                                       timezone=timezone,
                                       duration=duration,
                                       print_results=print_results)

@tool(description="Returns the link to book a slot.")
def create_booking_link(club_id: Annotated[str, "The club id of the slot"],
                  court_id: Annotated[str, "The court id of the slot"],
                  time: Annotated[str, "The time of the slot (format: 2026-02-18T08:00:00.000Z)"],
                  duration: Annotated[int, "The duration of the slot (minutes)"],
                  ) -> str:
    return playtomic_utils.create_booking_link(club_id=club_id, court_id=court_id, time=time, duration=duration)

@tool(description="Returns whether a date is a weekend.")
def is_weekend(date: Annotated[str, "The date to check (YYYY-MM-DD)"]):
    return datetime.strptime(date, "%Y-%m-%d").weekday() >= 5
