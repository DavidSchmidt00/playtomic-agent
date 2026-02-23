"""Command-line interface for Playtomic agent."""

import argparse
import logging
from datetime import datetime

from playtomic_agent.client.api import PlaytomicClient
from playtomic_agent.models import Club

logger = logging.getLogger(__name__)


def _print_clubs(clubs: list[Club]):
    """Print list of clubs to stdout."""
    if not clubs:
        print("No clubs found.")
        return

    print(f"Found {len(clubs)} clubs:")
    for club in clubs:
        print(f"- {club.name} (ID: {club.club_id})")
        print(f"  Slug: {club.slug}")
        print(f"  Timezone: {club.timezone}")
        print("")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Playtomic Agent CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    
    # Global arguments
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    subparsers = parser.add_subparsers(dest="command", required=True, help="Command to run")

    # --- Command: slots ---
    slots_parser = subparsers.add_parser("slots", help="Find available court slots")
    slots_parser.add_argument(
        "--club-slug",
        type=str,
        required=True,
        help="Club slug/identifier",
    )
    slots_parser.add_argument(
        "--date",
        type=str,
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Date to check (YYYY-MM-DD)",
    )
    slots_parser.add_argument(
        "--court-type",
        type=str,
        choices=["SINGLE", "DOUBLE"],
        help="Type of court to filter by",
    )
    slots_parser.add_argument(
        "--start-time",
        type=str,
        help="Start time to search from (HH:MM, in local timezone)",
    )
    slots_parser.add_argument(
        "--end-time",
        type=str,
        help="End time to search until (HH:MM, in local timezone)",
    )
    slots_parser.add_argument(
        "--duration",
        type=int,
        choices=[60, 90, 120],
        help="Duration of slots to filter (minutes)",
    )
    slots_parser.add_argument(
        "--timezone",
        type=str,
        default="Europe/Berlin",
        help="Timezone for time filters",
    )

    # --- Command: search ---
    search_parser = subparsers.add_parser("search", help="Search for clubs")
    search_group = search_parser.add_mutually_exclusive_group(required=True)
    search_group.add_argument(
        "--location",
        type=str,
        help="Search by location (City, Address, etc.) - uses Geocoding",
    )
    search_group.add_argument(
        "--name",
        type=str,
        help="Search by Club Name - uses specific name search",
    )
    search_parser.add_argument(
        "--radius",
        type=int,
        default=50000,
        help="Search radius in meters (only for --location)",
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    try:
        with PlaytomicClient() as client:
            if args.command == "slots":
                client.find_slots(
                    club_slug=args.club_slug,
                    date=args.date,
                    court_type=args.court_type,
                    start_time=args.start_time,
                    end_time=args.end_time,
                    timezone=args.timezone,
                    duration=args.duration,
                    log_slots=True,
                )
            elif args.command == "search":
                if args.location:
                    logger.info(f"Geocoding location: {args.location}")
                    coords = client.geocode(args.location)
                    if not coords:
                        logger.error(f"Could not find coordinates for location: {args.location}")
                        return 1
                    
                    lat, lon = coords
                    logger.info(f"Found coordinates: {lat}, {lon}. Searching for clubs...")
                    clubs = client.search_clubs(args.location, lat=lat, lon=lon, radius=args.radius)
                    _print_clubs(clubs)
                
                elif args.name:
                    logger.info(f"Searching for club name: {args.name}")
                    clubs = client.search_clubs(args.name)
                    _print_clubs(clubs)

    except Exception as e:
        logger.error(f"Error: {e}")
        if args.verbose:
            raise
        return 1


if __name__ == "__main__":
    exit(main() or 0)
