"""Command-line interface for Playtomic agent."""

import argparse
import logging
from datetime import datetime

from playtomic_agent.client.api import PlaytomicClient

logger = logging.getLogger(__name__)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Find available Playtomic Padel court slots",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--club-slug",
        type=str,
        required=True,
        help="Club slug/identifier",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Date to check (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--court-type",
        type=str,
        choices=["SINGLE", "DOUBLE"],
        help="Type of court to filter by",
    )
    parser.add_argument(
        "--start-time",
        type=str,
        help="Start time to search from (HH:MM, in local timezone)",
    )
    parser.add_argument(
        "--end-time",
        type=str,
        help="End time to search until (HH:MM, in local timezone)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        choices=[60, 90, 120],
        help="Duration of slots to filter (minutes)",
    )
    parser.add_argument(
        "--timezone",
        type=str,
        default="Europe/Berlin",
        help="Timezone for time filters",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
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
    except Exception as e:
        logger.error(f"Error: {e}")
        if args.verbose:
            raise
        return 1


if __name__ == "__main__":
    exit(main() or 0)
