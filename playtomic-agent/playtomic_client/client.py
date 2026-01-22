import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse
import logging
from playtomic_client.models import Club, Court, Slot, AvailableSlots
from typing import Literal, Annotated

from langchain_core.tools import tool

API_BASE_URL = "https://api.playtomic.io/v1"

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def _get_club(slug: str | None = None, name: str | None = None) -> Club | None:
    """
    Fetches the club page and extracts the name and grouped courts (SINGLE/DOUBLE) with id and name.

    Args:
        slug (str | None): The slug of the club.
        name (str | None): The name of the club.

    Returns:
        Club | None: The club object or None if failed.
    """
    try:
        if slug:
            response = requests.get(f"{API_BASE_URL}/tenants?tenant_uid={slug}")
            response.raise_for_status()
        elif name:
            response = requests.get(f"{API_BASE_URL}/tenants?tenant_name={name}")
            response.raise_for_status()
        else:
            raise ValueError("Either slug or name must be provided.")
    except requests.RequestException as e:
        logging.error(f"Error fetching club page: {e}")
        return None
    try:
        data = response.json()
        if len(data) == 0:
            logging.error("No data found for club.")
            return None
        if len(data) > 1:
            logging.error("Multiple tenants found for club. Try different slug.")
            return None
        tenant_name = data[0]['tenant_name']
        tenant_id = data[0]['tenant_id']
        resources = data[0]['resources']
        timezone = data[0]['address']['timezone']
    except (json.JSONDecodeError, KeyError) as e:
        logging.error(f"Error parsing club data: {e}")
        return None
    
    club = Club(slug, tenant_name, tenant_id, timezone, [])
    for resource in resources:
        court = Court(resource['resource_id'], resource['name'], resource['properties']['resource_size'])
        club.courts.append(court)
    logging.debug(f"Found {len(club.courts)} courts for {tenant_name}.")
    return club

def _get_available_slots(club: Club, date: str, start_time: str | None = None, end_time: str | None = None) -> AvailableSlots | None:
    """
    Fetches the available slots for a specific tenant and date.

    Args:
        club (Club): The club to fetch slots for.
        date (str): The date to fetch slots for (YYYY-MM-DD).
        start_time (str | None): The start time to filter by (HH:MM).
        end_time (str | None): The end time to filter by (HH:MM).

    Returns:
        AvailableSlots | None: The available slots.
    """
    # https://api.playtomic.io/v1/availability?tenant_id=53dbecb5-218f-4517-9b92-30dcac52a261&date=2026-02-19&start_min=2026-02-19T09%3A00%3A00&start_max=2026-02-19T21%3A00%3A00&sport_id=PADEL
    params = {
        "tenant_id": club.club_id,
        "date": date,
        "sport_id": "PADEL"
    }
    if start_time:
        params["start_min"] = f"{date}T{start_time}:00"
    else:
        params["start_min"] = f"{date}T00:00:00"
    if end_time:
        params["start_max"] = f"{date}T{end_time}:00"
    else:
        params["start_max"] = f"{date}T23:59:59"
    
    try:
        response = requests.get(f"{API_BASE_URL}/availability", params=params)
        response.raise_for_status()
        available_slots = AvailableSlots(club.club_id, date, [])
        for resource_availability in response.json():
            for slot in resource_availability.get('slots', []):
                resource_id = resource_availability['resource_id']
                court = club.get_court_by_id(resource_id)
                court_name = court.name if court else "Unknown Court"
                
                available_slots.slots.append(Slot(
                    club_id=club.club_id,
                    court_id=resource_id,
                    court_name=court_name,
                    # date and time are UTC in the API response
                    time=datetime.strptime(f"{date}T{slot['start_time']}", "%Y-%m-%dT%H:%M:%S").replace(tzinfo=ZoneInfo("UTC")),
                    duration=slot['duration'],
                    price=slot['price']
                ))
        return available_slots
    except requests.RequestException as e:
        logging.error(f"Error fetching availability: {e}")
        return None
    except json.JSONDecodeError as e:
         logging.error(f"Error parsing availability JSON: {e}")
         return None

def _filter_slots(club: Club, available_slots: AvailableSlots, court_type: str | None, duration: int | None = None) -> list[Slot] | None:
    """
    Filters slots by court type, start time and duration.

    Args:
        club (Club): The club to filter slots for.
        available_slots (AvailableSlots): The available slots to filter slots from.
        court_type (str | None): The type of court to filter by (SINGLE, DOUBLE).
        duration (int | None): The duration to filter by.

    Returns:
        list[Slot] | None: The filtered slots.
    """
    filtered_slots = []

    if court_type == "SINGLE":
        target_courts_ids = [court.id for court in club.get_court_by_type("single")]
    elif court_type == "DOUBLE":
        target_courts_ids = [court.id for court in club.get_court_by_type("double")]
    else:
        target_courts_ids = [court.id for court in club.courts]
    
    for slot in available_slots.slots:
        if slot.court_id not in target_courts_ids:
            continue
        if duration is not None and slot.duration != duration:
            continue
        filtered_slots.append(slot)
    
    return filtered_slots

def find_slots(club_slug: str,
               date: str,
               court_type: Literal["SINGLE", "DOUBLE"] | None = None, 
               start_time: str | None = None,
               end_time: str | None = None,
               timezone: str | None = None,
               duration: int | None = None,
               print_results: bool = False) -> list[Slot] | None:
    """
    Finds available slots for a specific club and date.

    Args:
        club_slug (str): The slug of the club.
        date (str): The date to check (YYYY-MM-DD).
        court_type (str | None): The type of court to filter by (SINGLE, DOUBLE).
        start_time (str | None): The start time to filter by (HH:MM).
        end_time (str | None): The end time to filter by (HH:MM).
        duration (int | None): The duration to filter by.
        timezone (str | None): The timezone of the club.
        print_results (bool): Whether to print the results.

    Returns:
        list[Slot] | None: The filtered slots.
    """
    if (start_time or end_time) and not timezone:
        logging.error("If start_time or end_time is provided, timezone must be provided.")
        return None
    if start_time:
        start_time = datetime.strptime(f"{date}T{start_time}", "%Y-%m-%dT%H:%M").replace(tzinfo=ZoneInfo(timezone)).astimezone(ZoneInfo("UTC"))
    if end_time:
        end_time = datetime.strptime(f"{date}T{end_time}", "%Y-%m-%dT%H:%M").replace(tzinfo=ZoneInfo(timezone)).astimezone(ZoneInfo("UTC"))

    log_str = f"Searching slots for club {club_slug}"
    if date:
        log_str += f" on {date}"
    if court_type:
        log_str += f" for {court_type.lower()} courts"
    if start_time:
        log_str += f" starting from {start_time.strftime('%H:%M')}"
    if end_time:
        log_str += f" until {end_time.strftime('%H:%M')}"
    if duration:
        log_str += f" with duration {duration} minutes"
    logging.info(log_str)

    club = _get_club(club_slug)
    if not club:
        logging.error("No club found or error fetching club.")
        return None

    available_slots = _get_available_slots(club, date, start_time.strftime('%H:%M') if start_time else None, end_time.strftime('%H:%M') if end_time else None)
    if not available_slots:
        logging.error("No availability data found or error fetching availability.")
        return None

    filtered_slots = _filter_slots(club, available_slots, court_type, duration)

    logging.info(f"Found {len(filtered_slots)} available slots")
    if print_results:
        # group slots by court
        slots_by_court = {}
        for slot in filtered_slots:
            if slot.court_name not in slots_by_court:
                slots_by_court[slot.court_name] = []
            slots_by_court[slot.court_name].append(slot)
        
        for court_name, slots in slots_by_court.items():
            print(f"Court: {court_name}")
            for slot in slots:
                print(f"Time: {slot.time.astimezone(ZoneInfo(timezone)).strftime('%H:%M')} | Duration: {slot.duration}min | Price: {slot.price} | Link: {slot.get_link()}")
            print("\n")
    return filtered_slots

def cli():
    parser = argparse.ArgumentParser(description="Find available Playtomic Padel slots.")
    parser.add_argument("--club-slug", type=str, help="Club slug")
    parser.add_argument("--date", type=str, default=datetime.now().strftime("%Y-%m-%d"), help="Date to check (YYYY-MM-DD) (Default: today)")
    parser.add_argument("--court-type", type=str, choices=["SINGLE", "DOUBLE"], help="Optional type of court")
    parser.add_argument("--start-time", type=str, help="Optional start time to search from (HH:MM)")
    parser.add_argument("--end-time", type=str, help="Optional end time to search until (HH:MM)")
    parser.add_argument("--duration", type=int, choices=[60, 90, 120], help="Optional duration of slots to filter")
    parser.add_argument("--timezone", type=str, default="Europe/Berlin", help="Optional timezone")
    args = parser.parse_args()
    
    filtered_slots = find_slots(club_slug=args.club_slug,
                                date=args.date,
                                court_type=args.court_type,
                                # Input times are in local time (Berlin)
                                start_time=args.start_time,
                                end_time=args.end_time,
                                duration=args.duration,
                                timezone=args.timezone,
                                print_results=True)
    print([s.to_json() for s in filtered_slots])

if __name__ == "__main__":
    cli()
