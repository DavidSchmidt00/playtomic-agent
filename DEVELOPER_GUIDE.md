# Developer Guide

> [!NOTE]
> This guide is intended for developers and AI agents who want to understand the internal workings of the Playtomic Agent project. Use this reference when extending the agent's capabilities or debugging issues.

## 1. Project Overview

**Playtomic Agent** is an AI-powered assistant designed to help users find and book Padel courts on Playtomic. It leverages **LangGraph** for orchestrating the agent workflow and **Google Gemini** as the underlying LLM. The project is split into a Python backend (FastAPI) and a React frontend.

## 2. Architecture

### Backend Stack
*   **Language**: Python 3.11+
*   **Framework**: FastAPI (API layer), Uvicorn (Server)
*   **AI Orchestration**: LangChain, LangGraph
*   **LLM**: Google Gemini (via `langchain-google-genai`)
*   **External API**: Playtomic API (unofficial client)

### Frontend Stack
*   **Framework**: React 18
*   **Build Tool**: Vite
*   **Styling**: CSS Modules / Standard CSS
*   **State Management**: React Hooks (`useProfile`, `useRegion`)
*   **Protocol**: Server-Sent Events (SSE) for streaming agent responses

### Infrastructure
*   **Containerization**: Docker, Docker Compose
*   **Dev Environment**: VS Code DevContainers, `.devcontainer` configuration

---

## 3. Core Components Deep Dive

### 3.1. Agent Logic (`src/playtomic_agent/agent.py`)
The heart of the application.
*   **`create_playtomic_agent`**: Initializes the LangGraph agent. It injects a system prompt that defines the agent's persona, rules, and available tools.
*   **System Prompt**: Dynamically built to include user preferences (e.g., favorite club, court type) and the current date/time.
*   **Tools**: The agent has access to a specific set of tools defined in `TOOLS` list.

### 3.2. Tools (`src/playtomic_agent/tools.py`)
The agent interacts with the world through these functions:
*   **`find_slots`**: The primary tool. Searches for available courts based on detailed filters (date, time, duration, type). Returns a summarized list of slots.
*   **`find_clubs_by_location`**: Geocodes a user query (city/address) and finds nearby clubs.
*   **`find_clubs_by_name`**:  Searches for a club by name. Critical for resolving "Lemon Padel" to the correct `club_slug`.
*   **`update_user_profile`**:  A "silent" tool. The agent calls this to suggest saving a user preference (e.g., "I always play doubles"). The frontend intercepts this to show a UI prompt.
*   **`suggest_next_steps`**: Emits clickable suggestion chips to the frontend (e.g. "Check Lemon Padel", "Book 18:00").
*   **`create_booking_link`**: Generates the direct Playtomic booking URL.

### 3.3. API Layer (`src/playtomic_agent/api.py`)
Exposes the agent to the web frontend via a single endpoint: `POST /api/chat`.
*   **Streaming**: Uses Server-Sent Events (SSE) to stream the agent's "thought process" and final response.
*   **Token Optimization**:
    *   **History Truncation**: The API truncates conversation history to the last 20 messages to keep the context window manageable and reduce costs.
*   **Event Types**:
    *   `tool_start`: Agent is calling a tool.
    *   `tool_end`: Tool execution finished.
    *   `message`: Final text response from the agent.
    *   `profile_suggestion`: Agent suggests saving a preference.
    *   `suggestion_chips`: List of clickable options for the user.
    *   `error`: Something went wrong.

### 3.4. API Client (`src/playtomic_agent/client/`)
A robust, class-based Python client for the Playtomic API.
*   Handles authentication (if needed), request headers, and error parsing.
*   **`PlaytomicClient`**: The main entry point. Context manager support (`with PlaytomicClient() as client:`).

### 3.5. Command Line Interface (`src/playtomic_agent/client/cli.py`)
Provides a direct way to interact with the Playtomic API without the agent or web UI. Useful for debugging or quick lookups.
*   **`main()`**: Entry point using `argparse`.
*   **Commands**:
    *   `search`: specific club name search or location-based search (geocoding).
    *   `slots`: fetches slots for a specific club/date with all available filters.

---

## 4. Codebase Reference

### Backend (`src/playtomic_agent/`)

#### `client/api.py`
The core communication layer with Playtomic.
*   **`PlaytomicClient`**
    *   `get_club(slug=None, name=None)`: Fetches club details. Handles both slug (ID) and loose user input names.
    *   `search_clubs(query, lat=None, lon=None)`: Searches clubs by text or location coordinates.
    *   `get_available_slots(club, date, ...)`: Low-level slot fetching from Playtomic `/availability` endpoint.
    *   `filter_slots(...)`: Applies Python-side filtering (Court Type: Single/Double, Duration).
    *   `find_slots(...)`: High-level convenience method that chains `get_club`, `get_available_slots`, and `filter_slots`.

#### `models.py`
Pydantic models ensuring type safety.
*   `Club`: `slug`, `name`, `club_id`, `timezone`, `courts` list.
*   `Court`: `id`, `name`, `type` ("single"|"double").
*   `Slot`: `time` (UTC datetime), `price`, `duration`, `court_name`, `get_link()`.

#### `client/cli.py`
Command-line interface implementation using `argparse`.
*   `main()`: Handles argument parsing and command dispatch (`slots` vs `search`).
*   `_print_clubs(clubs)`: Helper to format club search results.
*   `slots` command: Invokes `client.find_slots(...)` with extensive CLI arguments.
*   `search` command: Invokes `client.geocode(...)` (if location) and `client.search_clubs(...)`.

#### `config.py`
Manages settings via `pydantic-settings`.
*   `Settings`: Loads from `.env`.
    *   `GEMINI_API_KEY`: Required.
    *   `DEFAULT_TIMEZONE`: Default `Europe/Berlin`.
    *   `PLAYTOMIC_API_BASE_URL`: For potential proxying/mocking.

### Frontend (`web/src/`)

#### `components/Chat.jsx`
Main chat interface.
*   **State**: `messages` (list), `input`, `loading`, `toolStatus`.
*   **SSE Handling**: Consumes the `/api/chat` stream. Parses `tool_start`, `tool_end`, etc.
*   **New Chat**: "Trash" icon button clears chat history instantly (no confirmation).
*   **Profile Integration**: Updates local storage profile based on `profile_suggestion` events.

#### `hooks/useProfile.js`
Manages User Preferences.
*   Persists to `localStorage` key `padel-agent-profile`.
*   Fields: `preferred_club_slug`, `preferred_club_name`, `court_type`, etc.

---

## 5. Development Workflow

### Prerequisites
*   Python 3.11+
*   Node.js 18+ (for frontend)
*   Docker (optional but recommended)

### Setting up Environment
1.  **Clone & Install**:
    ```bash
    git clone <repo>
    pip install -e ".[dev]"
    ```
2.  **Environment Variables**:
    Copy `.env.example` to `.env` and fill in your `GEMINI_API_KEY`.

### Running Locally
*   **Backend**: `uvicorn playtomic_agent.api:app --reload --port 8082`
*   **Frontend**: `cd web && npm run dev -- --port 8080`

### Running with Docker
```bash
docker-compose up --build
```

### Testing
We use `pytest` for the backend.
```bash
pytest tests/
```

### Linting
We use `ruff` and `black`.
```bash
ruff check .
black .
```

---

## 6. Common Extension Tasks

### Adding a New Tool
1.  Define the tool function in `src/playtomic_agent/tools.py` using the `@tool` decorator.
2.  Add type hints and a docstring (this is used by the LLM).
3.  Import the tool in `src/playtomic_agent/agent.py`.
4.  Add it to the `TOOLS` list in `agent.py`.
5.  Restart the backend.

### Adding a User Preference
1.  **Backend**:
    *   Update `_build_system_prompt` in `agent.py` to recognize the new preference key.
    *   Update `update_user_profile` tool docstring in `tools.py` to include the new key as a valid option.
2.  **Frontend**:
    *   Update `PROFILE_LABELS` in `web/src/hooks/useProfile.js` to map the key to a human-readable label.
    *   (Optional) Update `ProfileCard.jsx` if it needs special rendering.

---

## 7. Troubleshooting

### "Agent not responding"
*   Check `api.py` logs.
*   Verify `GEMINI_API_KEY` is valid.
*   Check for `429 ResourceExhausted` (rate limiting).

### "No slots found"
*   Ensure the `club_slug` is correct.
*   Check if the date is too far in the future (Playtomic usually opens slots ~2-4 weeks ahead).
*   Verify timezone settings in `.env` (`DEFAULT_TIMEZONE`).

### Frontend Connection Error
*   Ensure backend is running on port `8082`.
*   Check CORS settings in `api.py` if running on a different port/domain.
