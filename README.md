# Playtomic Slot Finder

A Python utility to find available Padel court slots on Playtomic for specific clubs (default: Lemon Padel Club).

## Features

- **Automated Retrieval**: Fetches court information and availability directly from Playtomic.
- **Flexible Filtering**:
  - Filter by club (via slug).
  - Filter by court type ("SINGLE" or "DOUBLE").
  - Filter by time range (start and end time).
  - Filter by slot duration (60, 90, 120 minutes).
- **CLI Support**: Easy-to-use Command Line Interface.

## Installation

1.  Clone the repository.
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

Run the script using Python:

```bash
python find_slots.py [options]
```

### Arguments

| Argument | Description | Default |
| :--- | :--- | :--- |
| `--club-slug` | The slug of the club to search for. | `lemon-padel-club` |
| `--date` | Date to check in `YYYY-MM-DD` format. | Today's date |
| `--court-type` | Filter by court type (`SINGLE`, `DOUBLE`). | All courts |
| `--start-time` | Start time to search from in `HH:MM` format. | None |
| `--end-time` | End time to search until in `HH:MM` format. | None |
| `--duration` | Filter by slot duration (60, 90, 120 minutes). | Any |
| `--timezone` | Timezone to use for time calculations. | `Europe/Berlin` |

### Examples

**Find all slots for the default club today:**
```bash
python find_slots.py
```

**Find "DOUBLE" court slots for a specific date:**
```bash
python find_slots.py --date 2026-03-23 --court-type DOUBLE
```

**Find slots between 18:00 and 22:00:**
```bash
python find_slots.py --start-time 18:00 --end-time 22:00
```

**Find 90-minute slots for a different club:**
```bash
python find_slots.py --club-slug another-padel-club --duration 90
```

## How it works

1.  **Court Discovery**: Scrapes the club's public page to identify resources and court types.
2.  **Availability Fetch**: Queries the Playtomic API for the specified date.
3.  **Matching & Filtering**: Matches availability data with identified courts and filters based on user criteria (time, duration, type).
