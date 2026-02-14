"""LangChain tools for the Playtomic agent."""

from datetime import datetime
from typing import Annotated, Literal

from langchain_core.tools import tool

from playtomic_agent.client.api import PlaytomicClient
from playtomic_agent.client.utils import create_booking_link as utils_create_booking_link
from playtomic_agent.models import Slot


@tool(
    description="Finds available slots for a specific club and date and filters them by court type, start time and duration."
)
def find_slots(
    club_slug: Annotated[str, "The slug of the club"],
    date: Annotated[str, "The date to check (YYYY-MM-DD)"],
    court_type: Annotated[
        Literal["SINGLE", "DOUBLE"] | None,
        "Optional: The type of court to filter by (SINGLE, DOUBLE)",
    ] = None,
    start_time: Annotated[str | None, "Optional: The start time to filter by (HH:MM)"] = None,
    end_time: Annotated[str | None, "Optional: The end time to filter by (HH:MM)"] = None,
    timezone: Annotated[
        str | None,
        "Optional: The timezone to use. Must be provided if start_time or end_time is set.",
    ] = None,
    duration: Annotated[int | None, "Optional: The duration to filter by (minutes)"] = None,
) -> Annotated[dict | None, "A summary of available slots with count and details."]:
    """Find available slots using PlaytomicClient."""
    try:
        from playtomic_agent.config import get_settings
        effective_tz = timezone or get_settings().default_timezone
        with PlaytomicClient() as client:
            slots = client.find_slots(
                club_slug=club_slug,
                date=date,
                court_type=court_type,
                start_time=start_time,
                end_time=end_time,
                timezone=effective_tz,
                duration=duration,
                log_slots=True
            )
            if not slots:
                return {"count": 0, "slots": []}

            # Return compact summaries with pre-computed local times and booking links
            # Limit to 10 slots to keep LLM context manageable
            from zoneinfo import ZoneInfo
            from playtomic_agent.client.utils import create_booking_link as _make_link
            tz = ZoneInfo(effective_tz)
            return {
                "count": len(slots),
                "date": date,
                "slots": [
                    {
                        "local_time": s.time.astimezone(tz).strftime("%H:%M"),
                        "court": s.court_name,
                        "duration": s.duration,
                        "price": s.price,
                        "booking_link": _make_link(
                            s.club_id, s.court_id,
                            s.time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                            s.duration,
                        ),
                    }
                    for s in slots
                ],
            }
    except Exception as exc:
        import logging
        logging.exception(f"find_slots failed: {exc}")
        return None


@tool(description="Returns the link to book a slot.")
def create_booking_link(
    club_id: Annotated[str, "The club id of the slot"],
    court_id: Annotated[str, "The court id of the slot"],
    time: Annotated[str, "The time of the slot (format: 2026-02-18T08:00:00.000Z)"],
    duration: Annotated[int, "The duration of the slot (minutes)"],
) -> str:
    return utils_create_booking_link(
        club_id=club_id, court_id=court_id, time=time, duration=duration
    )


@tool(description="Returns whether a date is a weekend.")
def is_weekend(date: Annotated[str, "The date to check (YYYY-MM-DD)"]):
    return datetime.strptime(date, "%Y-%m-%d").weekday() >= 5


@tool(description="Finds clubs by location (city, region, or address). Use this when the user mentions a place (e.g. 'Clubs in Berlin').")
def find_clubs_by_location(
    query: Annotated[str, "The search query (e.g. 'Berlin', 'Munich', 'Cologne')"],
) -> Annotated[list[dict] | None, "List of found clubs with name and slug."]:
    """Finds clubs near a specific location using geocoding."""
    try:
        from playtomic_agent.config import get_settings
        from playtomic_agent.context import get_country
        
        # Use per-request country or fall back to settings
        try:
            country = get_country()
        except (ImportError, LookupError):
            country = get_settings().country
            
        with PlaytomicClient() as client:
            coordinates = client.geocode(query, country_code=country)
            if not coordinates:
                return None
            
            lat, lon = coordinates
            clubs = client.search_clubs(query, lat=lat, lon=lon)
            
            # Limit to top 5 result
            return [
                {
                    "name": club.name,
                    "slug": club.slug,
                    "id": club.club_id,
                    "timezone": club.timezone,
                }
                for club in clubs[:5]
            ]
    except Exception:
        return None

@tool(description="Finds clubs by name. Use this when the user mentions a specific club name (e.g. 'Lemon Padel', 'Red Club'). Use only the core club name, without location suffixes.")
def find_clubs_by_name(
    name: Annotated[str, "The core club name to search for (e.g. 'Lemon Padel', not 'Lemon Padel Club Limburg')"],
) -> Annotated[list[dict] | None, "List of found clubs with name and slug."]:
    """Finds clubs matching a specific name. Retries with shorter queries if needed."""
    try:
        with PlaytomicClient() as client:
            clubs = client.search_clubs(name)

            # If no results, try progressively shorter queries
            # e.g. "Lemon Padel Club Limburg" -> "Lemon Padel Club" -> "Lemon Padel"
            if not clubs:
                words = name.split()
                for length in range(len(words) - 1, 1, -1):
                    shorter = " ".join(words[:length])
                    clubs = client.search_clubs(shorter)
                    if clubs:
                        break

            return [
                {
                    "name": club.name,
                    "slug": club.slug,
                    "id": club.club_id,
                    "timezone": club.timezone,
                }
                for club in clubs[:5]
            ]
    except Exception:
        return None

@tool(description="Silently suggests saving a user preference. The UI will prompt the user to accept or decline. Call this whenever you detect a new preference from the user's request. Valid keys: 'preferred_club_slug', 'preferred_club_name', 'preferred_city', 'court_type', 'duration', 'preferred_time'.")
def update_user_profile(
    key: Annotated[str, "The preference key (e.g. 'preferred_club_slug', 'preferred_city', 'court_type')"],
    value: Annotated[str, "The preference value (e.g. 'lemon-padel-club', 'Berlin', 'DOUBLE')"],
) -> Annotated[dict, "A profile update instruction for the frontend."]:
    """Suggests a user preference update. The frontend will show a confirmation prompt."""
    return {"profile_update": {"key": key, "value": value}}

