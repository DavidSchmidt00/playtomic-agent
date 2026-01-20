import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import argparse
import logging
from dataclasses import dataclass, field

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@dataclass
class Club:
    slug: str = ""
    name: str = ""
    tenant_id: str = ""
    courts: dict[str, list[Court]] = field(default_factory=dict)

    def __str__(self) -> str:
        header = f" {self.name} ({self.slug}) "
        tenant_id = f" {self.tenant_id} "
        line = "#" * len(header)
        single = "\n".join(f"  - {c}" for c in self.courts.get("SINGLE", []))
        double = "\n".join(f"  - {c}" for c in self.courts.get("DOUBLE", []))
        return f"\n{line}\n{header}\n{tenant_id}\n{line}\nSingle courts:\n{single}\nDouble courts:\n{double}"

    def get_court_by_id(self, court_id: str) -> Court | None:
        for court in self.courts.get("SINGLE", []) + self.courts.get("DOUBLE", []):
            if court.id == court_id:
                return court
        return None

@dataclass
class Court:
    id: str = ""
    name: str = ""

    def __str__(self) -> str:
        return f"{self.name} ({self.id})"


@dataclass
class Slot:
    tenant_id: str = ""
    court_id: str = ""
    court_name: str = ""
    time: datetime = None
    duration: int = 0
    price: str = ""

    def get_link(self) -> str:
        # calculate start time from date and start_time (result format: 2026-02-18T08%3A00%3A00.000Z)
        start_time = self.time.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        return f"https://app.playtomic.com/payments?type=CUSTOMER_MATCH&tenant_id={self.tenant_id}&resource_id={self.court_id}&start={start_time}&duration={self.duration}"

@dataclass
class AvailableSlots:
    tenant_id: str = ""
    date: datetime = None
    slots: list[Slot] = field(default_factory=list)

def get_club(slug: str) -> Club | None:
    """
    Fetches the club page and extracts the name and grouped courts (SINGLE/DOUBLE) with id and name.

    Args:
        slug (str): The slug of the club.

    Returns:
        Club | None: The club object or None if failed.
    """
    try:
        response = requests.get(f"https://playtomic.com/clubs/{slug}")
        response.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"Error fetching club page: {e}")
        return None

    soup = BeautifulSoup(response.content, 'html.parser')
    next_data_script = soup.find('script', id='__NEXT_DATA__')
    
    if not next_data_script:
        logging.error("Could not find __NEXT_DATA__ script tag.")
        return None

    try:
        data = json.loads(next_data_script.string)
        tenant_name = data['props']['pageProps']['tenant']['tenant_name']
        tenant_id = data['props']['pageProps']['tenant']['tenant_id']
        resources = data['props']['pageProps']['tenant']['resources']
    except (json.JSONDecodeError, KeyError) as e:
        logging.error(f"Error parsing club data: {e}")
        return None

    grouped_courts = {"SINGLE": [], "DOUBLE": []}
    
    for resource in resources:
        features = resource.get('features', [])
        court = Court(resource['resourceId'], resource['name'])
        
        if 'single' in features:
            grouped_courts["SINGLE"].append(court)
        elif 'double' in features:
            grouped_courts["DOUBLE"].append(court)
            
    logging.debug(f"Found {len(grouped_courts['SINGLE'])} single courts and {len(grouped_courts['DOUBLE'])} double courts for {tenant_name}.")
    return Club(slug, tenant_name, tenant_id, grouped_courts)

def get_available_slots(club: Club, date: str) -> AvailableSlots | None:
    """
    Fetches the available slots for a specific tenant and date.
    """
    availability_url = "https://playtomic.com/api/clubs/availability"
    params = {
        "tenant_id": club.tenant_id,
        "date": date,
        "sport_id": "PADEL"
    }
    
    try:
        response = requests.get(availability_url, params=params)
        response.raise_for_status()
        available_slots = AvailableSlots(club.tenant_id, date, [])
        for resource_availability in response.json():
            for slot in resource_availability.get('slots', []):
                resource_id = resource_availability['resource_id']
                court = club.get_court_by_id(resource_id)
                court_name = court.name if court else "Unknown Court"
                
                available_slots.slots.append(Slot(
                    tenant_id=club.tenant_id,
                    court_id=resource_id,
                    court_name=court_name,
                    # date and time are UTC in the API response
                    time=datetime.strptime(f"{date}T{slot['start_time']}", "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc),
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

def filter_slots(club: Club, available_slots: AvailableSlots, court_type: str | None, start_time: datetime | None, end_time: datetime | None, duration: int | None = None) -> list[Slot] | None:
    """
    Filters slots by court type, start time and duration.

    Args:
        club (Club): The club to filter slots for.
        available_slots (AvailableSlots): The available slots to filter slots from.
        court_type (str | None): The type of court to filter by (SINGLE, DOUBLE).
        start_time (datetime | None): The start time to filter by.
        end_time (datetime | None): The end time to filter by.
        duration (int | None): The duration to filter by.

    Returns:
        list[Slot] | None: The filtered slots.
    """
    filtered_slots = []

    if court_type == "SINGLE":
        target_courts_ids = [court.id for court in club.courts.get("SINGLE", [])]
    elif court_type == "DOUBLE":
        target_courts_ids = [court.id for court in club.courts.get("DOUBLE", [])]
    else:
        target_courts_ids = [court.id for court in club.courts.get("SINGLE", []) + club.courts.get("DOUBLE", [])]
    
    for slot in available_slots.slots:
        if slot.court_id not in target_courts_ids:
            continue
        if duration is not None and slot.duration != duration:
            continue
        if start_time is not None and slot.time < start_time.astimezone(timezone.utc):
            continue
        if end_time is not None and slot.time > end_time.astimezone(timezone.utc):
            continue
        filtered_slots.append(slot)
    
    return filtered_slots

def find_slots(club_slug: str, date: str, court_type: str | None, start_time: datetime | None, end_time: datetime | None, duration: int | None, timezone: str, print_results: bool = False) -> list[Slot] | None:
    """
    Finds available slots for a specific club and date.

    Args:
        club_slug (str): The slug of the club.
        date (str): The date to check (YYYY-MM-DD).
        court_type (str | None): The type of court to filter by (SINGLE, DOUBLE).
        start_time (datetime | None): The start time to filter by.
        end_time (datetime | None): The end time to filter by.
        duration (int | None): The duration to filter by.

    Returns:
        list[Slot] | None: The filtered slots.
    """
    
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

    club = get_club(club_slug)
    if not club:
        logging.error("No club found or error fetching club.")
        return None

    available_slots = get_available_slots(club, date)
    if not available_slots:
        logging.error("No availability data found or error fetching availability.")
        return None

    filtered_slots = filter_slots(club, available_slots, court_type, start_time, end_time, duration)

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

def main():
    parser = argparse.ArgumentParser(description="Find available Playtomic Padel slots.")
    parser.add_argument("--club-slug", type=str, default="lemon-padel-club", help="Club slug")
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
                                start_time=datetime.strptime(f"{args.date}T{args.start_time}", "%Y-%m-%dT%H:%M").replace(tzinfo=ZoneInfo(args.timezone)) if args.start_time else None,
                                end_time=datetime.strptime(f"{args.date}T{args.end_time}", "%Y-%m-%dT%H:%M").replace(tzinfo=ZoneInfo(args.timezone)) if args.end_time else None,
                                duration=args.duration,
                                timezone=args.timezone,
                                print_results=True)

if __name__ == "__main__":
    main()
