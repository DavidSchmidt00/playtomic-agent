# Playtomic CLI & AI Agent

> [!WARNING]
> This project is a **Work in Progress**. Features and APIs are subject to change.


An AI-powered assistant and utility to find available Padel court slots on Playtomic. This project now features a LangGraph-based agent that can search for slots, check for weekends, and generate booking links through natural language interactions.

## Features

- **AI Agent (LangGraph)**: Talk to an AI assistant to find the perfect slot.
- **Automated Retrieval**: Fetches court information and availability directly from Playtomic.
- **Flexible Filtering**:
  - Filter by club (via slug).
  - Filter by court type ("SINGLE" or "DOUBLE").
  - Filter by time range (start and end time).
  - Filter by slot duration (60, 90, 120 minutes).
- **CLI Support**: Direct command-line interface for quick searches.

## Installation

1.  Clone the repository.
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

The AI Agent requires Google Gemini API keys. You can set them as environment variables or in an `.env` file.

1.  Obtain Gemini API keys from the [Google AI Studio](https://aistudio.google.com/).
2.  Set the following environment variables:
    ```bash
    export GEMINI_API_KEY_1="your_first_key"  # Used for free-tier/testing
    export GEMINI_API_KEY_2="your_second_key" # Used for higher rate limits/pro models
    ```

## Usage

### 1. AI Agent (Natural Language)

You can interact with the agent through the provided script or using LangGraph tools.

**Run the Agent locally:**
```bash
PYTHONPATH=./playtomic-agent python playtomic-agent/agent.py
```

**Example Query:**
> "Search for the next available 90 minutes slot for a double court at xy-club on between 18:00 and 20:00. Search until you find one."

### 2. CLI Slot Finder (Direct Search)

For a more traditional CLI experience, use the client utility:

```bash
PYTHONPATH=./playtomic-agent python playtomic-agent/playtomic_client/client.py [options]
```

#### CLI Arguments

| Argument | Description | Default |
| :--- | :--- | :--- |
| `--club-slug` | The slug of the club to search for. | None |
| `--date` | Date to check in `YYYY-MM-DD` format. | Today's date |
| `--court-type` | Filter by court type (`SINGLE`, `DOUBLE`). | All courts |
| `--start-time` | Start time to search from in `HH:MM` format. | None |
| `--end-time` | End time to search until in `HH:MM` format. | None |
| `--duration` | Filter by slot duration (60, 90, 120 minutes). | Any |
| `--timezone` | Timezone to use for time calculations. | `Europe/Berlin` |

#### Examples

**Find all slots for a club today:**
```bash
PYTHONPATH=./playtomic-agent python playtomic-agent/playtomic_client/client.py --club-slug xy-club
```

## How it works

1.  **AI Orchestration**: The LangGraph agent uses tools to fetch availability, check dates, and process your requests.
2.  **Court Discovery**: The system identifies resources and court types for the specified club.
3.  **Availability Fetching**: Queries the Playtomic API directly for real-time data.
4.  **Matching & Filtering**: Matches availability with identified courts and applies your specific criteria.

