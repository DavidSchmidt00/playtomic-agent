"""Playtomic API client for fetching club and slot information."""

import json
import logging
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

import requests

from playtomic_agent.client.exceptions import (
    APIError,
    ClubNotFoundError,
    MultipleClubsFoundError,
    ValidationError,
)
from playtomic_agent.config import get_settings
from playtomic_agent.models import Club, Court, Slot

logger = logging.getLogger(__name__)


class PlaytomicClient:
    """Client for interacting with the Playtomic API.

    This class provides methods to fetch club information and available court slots
    from the Playtomic API with improved error handling and resource management.

    Attributes:
        api_base_url: Base URL for the Playtomic API
        session: Requests session for connection pooling
    """

    def __init__(self, api_base_url: str | None = None):
        """Initialize the Playtomic client.

        Args:
            api_base_url: Base URL for the API. If None, uses default from settings.
        """
        settings = get_settings()
        self.api_base_url = api_base_url or settings.playtomic_api_base_url
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "playtomic-agent/0.1.0"})

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - closes session."""
        self.close()

    def close(self):
        """Close the HTTP session."""
        self.session.close()

    def get_club(self, slug: str | None = None, name: str | None = None) -> Club:
        """Fetch club information by slug or name.

        Args:
            slug: Club slug/identifier
            name: Club name

        Returns:
            Club object with courts and metadata

        Raises:
            ValidationError: If neither slug nor name is provided
            ClubNotFoundError: If no club is found
            MultipleClubsFoundError: If multiple clubs match the identifier
            APIError: If the API request fails
        """
        if not slug and not name:
            raise ValidationError("Either slug or name must be provided")

        # Determine search type
        if slug:
            identifier: str = slug
            search_type = "slug"
        else:
            identifier = name  # type: ignore[assignment]
            search_type = "name"

        try:
            params: dict[str, str] = {}
            if slug:
                params["tenant_uid"] = slug
            elif name:
                params["tenant_name"] = name

            response = self.session.get(
                f"{self.api_base_url}/tenants",
                params=params,
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            raise APIError(
                f"Failed to fetch club with {search_type}: {identifier}",
                status_code=(
                    getattr(e.response, "status_code", None) if hasattr(e, "response") else None
                ),
            ) from e

        try:
            data = response.json()
        except json.JSONDecodeError as e:
            raise APIError("Invalid JSON response from API") from e

        if len(data) == 0:
            raise ClubNotFoundError(identifier, search_type)

        if len(data) > 1:
            raise MultipleClubsFoundError(identifier, len(data))

        # Parse club data
        try:
            club_data = data[0]
            club = Club(
                slug=slug or club_data.get("tenant_uid", ""),
                name=club_data["tenant_name"],
                club_id=club_data["tenant_id"],
                timezone=club_data["address"]["timezone"],
                courts=[],
            )

            for resource in club_data.get("resources", []):
                court = Court(
                    id=resource["resource_id"],
                    name=resource["name"],
                    type=resource["properties"]["resource_size"],
                )
                club.courts.append(court)

            logger.info(f"Found club '{club.name}' with {len(club.courts)} courts")
            return club

        except (KeyError, TypeError) as e:
            raise APIError(f"Failed to parse club data: {e}") from e

    def get_available_slots(
        self,
        club: Club,
        date: str,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> list[Slot]:
        """Fetch available slots for a club on a specific date.

        Args:
            club: Club object
            date: Date in YYYY-MM-DD format
            start_time: Optional start time filter in HH:MM format (UTC)
            end_time: Optional end time filter in HH:MM format (UTC)

        Returns:
            List of available slots

        Raises:
            APIError: If the API request fails
        """
        params = {
            "tenant_id": club.club_id,
            "date": date,
            "sport_id": "PADEL",
            "start_min": f"{date}T{start_time if start_time else '00:00'}:00",
            "start_max": f"{date}T{end_time if end_time else '23:59'}:59",
        }

        try:
            response = self.session.get(
                f"{self.api_base_url}/availability",
                params=params,
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            raise APIError(
                f"Failed to fetch availability for {club.name}",
                status_code=(
                    getattr(e.response, "status_code", None) if hasattr(e, "response") else None
                ),
            ) from e

        try:
            data = response.json()
        except json.JSONDecodeError as e:
            raise APIError("Invalid JSON response from availability API") from e

        available_slots = []

        for resource_availability in data:
            resource_id = resource_availability.get("resource_id")
            court = club.get_court_by_id(resource_id)
            court_name = court.name if court else "Unknown Court"

            for slot_data in resource_availability.get("slots", []):
                try:
                    slot_time = datetime.strptime(
                        f"{date}T{slot_data['start_time']}", "%Y-%m-%dT%H:%M:%S"
                    ).replace(tzinfo=ZoneInfo("UTC"))

                    slot = Slot(
                        club_id=club.club_id,
                        court_id=resource_id,
                        court_name=court_name,
                        time=slot_time,
                        duration=slot_data["duration"],
                        price=slot_data["price"],
                    )
                    available_slots.append(slot)
                except (KeyError, ValueError) as e:
                    logger.warning(f"Skipping invalid slot data: {e}")
                    continue

        # Build informative log message
        time_range = "all day"
        if start_time and end_time:
            time_range = f"between {start_time} and {end_time} (UTC)"
        elif start_time:
            time_range = f"from {start_time} (UTC) onwards"
        elif end_time:
            time_range = f"until {end_time} (UTC)"

        logger.info(
            f"Found {len(available_slots)} available slots for {club.name} on {date} {time_range}"
        )
        return available_slots

    def filter_slots(
        self,
        club: Club,
        available_slots: list[Slot],
        court_type: Literal["SINGLE", "DOUBLE"] | None = None,
        duration: int | None = None,
    ) -> list[Slot]:
        """Filter slots by court type and duration.

        Args:
            club: Club object
            available_slots: Available slots to filter
            court_type: Optional court type filter (SINGLE or DOUBLE)
            duration: Optional duration filter in minutes

        Returns:
            List of filtered slots
        """
        # Determine target court IDs
        if court_type == "SINGLE":
            target_court_ids = {court.id for court in club.get_court_by_type("single")}
        elif court_type == "DOUBLE":
            target_court_ids = {court.id for court in club.get_court_by_type("double")}
        else:
            target_court_ids = {court.id for court in club.courts}

        # Filter slots
        filtered_slots = []
        for slot in available_slots:
            if slot.court_id not in target_court_ids:
                continue
            if duration is not None and slot.duration != duration:
                continue
            filtered_slots.append(slot)

        logger.debug(f"Filtered to {len(filtered_slots)} slots")
        return filtered_slots

    def find_slots(
        self,
        club_slug: str,
        date: str,
        court_type: Literal["SINGLE", "DOUBLE"] | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        timezone: str | None = None,
        duration: int | None = None,
        log_slots: bool = False,
    ) -> list[Slot]:
        """Find available slots with filtering.

        This is a convenience method that combines club fetch, slot fetch, and filtering.

        Args:
            club_slug: Club identifier
            date: Date in YYYY-MM-DD format
            court_type: Optional court type filter
            start_time: Optional start time in HH:MM format (in the specified timezone)
            end_time: Optional end time in HH:MM format (in the specified timezone)
            timezone: Timezone for time filters (required if times are specified)
            duration: Optional duration filter in minutes
            log_slots: Whether to log the slots

        Returns:
            List of filtered slots

        Raises:
            ValidationError: If time filters are specified without timezone
            ClubNotFoundError: If club is not found
            APIError: If API requests fail
        """
        if (start_time or end_time) and not timezone:
            raise ValidationError(
                "timezone is required when start_time or end_time is provided",
                field="timezone",
            )

        # Convert local times to UTC
        utc_start = None
        utc_end = None
        if start_time:
            assert timezone is not None
            local_dt = datetime.strptime(f"{date}T{start_time}", "%Y-%m-%dT%H:%M")
            local_dt = local_dt.replace(tzinfo=ZoneInfo(timezone))
            utc_start = local_dt.astimezone(ZoneInfo("UTC")).strftime("%H:%M")

        if end_time:
            assert timezone is not None
            local_dt = datetime.strptime(f"{date}T{end_time}", "%Y-%m-%dT%H:%M")
            local_dt = local_dt.replace(tzinfo=ZoneInfo(timezone))
            utc_end = local_dt.astimezone(ZoneInfo("UTC")).strftime("%H:%M")

        # Fetch club and slots
        club = self.get_club(slug=club_slug)
        available_slots = self.get_available_slots(club, date, utc_start, utc_end)
        filtered_slots = self.filter_slots(club, available_slots, court_type, duration)

        # Build filter criteria message
        filters = [f"date: {date}"]
        if court_type:
            filters.append(f"court type: {court_type}")
        if duration:
            filters.append(f"duration: {duration}min")
        if start_time:
            filters.append(f"from: {start_time}")
        if end_time:
            filters.append(f"until: {end_time}")

        filter_msg = f" ({', '.join(filters)})" if filters else ""
        if filtered_slots:
            logger.info(f"Found {len(filtered_slots)} slots matching criteria{filter_msg}")
            if log_slots:
                assert timezone is not None
                _print_results(filtered_slots, timezone)
        else:
            logger.warning(f"No slots found matching criteria{filter_msg}")

        return filtered_slots


def _print_results(slots: list[Slot], timezone: str):
    """Print slots grouped by court."""
    slots_by_court: dict[str, list[Slot]] = {}
    for slot in slots:
        if slot.court_name not in slots_by_court:
            slots_by_court[slot.court_name] = []
        slots_by_court[slot.court_name].append(slot)

    for court_name, court_slots in slots_by_court.items():
        print(f"\nCourt: {court_name}")
        for slot in court_slots:
            local_time = slot.time.astimezone(ZoneInfo(timezone)).strftime("%H:%M")
            print(
                f"  Time: {local_time} | "
                f"Duration: {slot.duration}min | "
                f"Price: {slot.price} | "
                f"Link: {slot.get_link()}"
            )
