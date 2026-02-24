# AGENTS.md

This document guides AI agents working on the Playtomic Agent project. For general information, see [README.md](README.md).

## 🏗️ Project Structure

```
padel-agent/
├── src/playtomic_agent/          # Main backend (Python)
│   ├── agent.py                  # LangGraph agent orchestration
│   ├── tools.py                  # LangChain tools for agent
│   ├── api.py                    # FastAPI server with SSE streaming
│   ├── config.py                 # Settings via pydantic-settings
│   ├── context.py                # Request context (language, region)
│   ├── models.py                 # Pydantic models (Club, Court, Slot)
│   └── client/                   # Playtomic API client
│       ├── api.py                # PlaytomicClient class
│       ├── cli.py                # CLI interface
│       ├── utils.py              # Helpers (geocoding, booking links)
│       └── exceptions.py         # Custom exceptions
├── web/                          # Frontend (React 18 + Vite)
│   ├── src/
│   │   ├── components/Chat.jsx   # Main chat interface
│   │   ├── hooks/useProfile.js   # User preferences management
│   │   └── App.jsx
│   └── package.json
├── tests/                        # Pytest test suite
├── .devcontainer/                # VS Code DevContainer config
├── .agent/                       # Agent workspace (rules, backlog)
├── pyproject.toml                # Python project metadata
└── .env.example                  # Environment template
```

**Note on `.agent/`:** Contains project-specific rules for AI agents (`rules/`) and a feature backlog (`backlog.md`). Read these for context on project conventions and planned features.

## 🚀 Development Setup

### Prerequisites
- **VS Code or Cursor** with DevContainer support
- **Docker** (required for DevContainer)

### Environment Variables

Create a `.env` file from `.env.example`:

```bash
cp .env.example .env
```

**Required variables:**
```
GEMINI_API_KEY=your_google_gemini_api_key
DEFAULT_TIMEZONE=Europe/Berlin
DEFAULT_MODEL=gemini-3-flash-preview
PLAYTOMIC_API_BASE_URL=https://api.playtomic.io/v1
```

Get your `GEMINI_API_KEY` from [Google AI Studio](https://aistudio.google.com/).

### Dev Container Setup (Recommended)

1. **Open in VS Code or Cursor:**
   - Clone the repository: `git clone https://github.com/DavidSchmidt00/playtomic-agent.git`
   - Open the folder in VS Code or Cursor

2. **Reopen in Container:**
   - When prompted, click "Reopen in Container"
   - (Or use Command Palette: `Dev Containers: Reopen in Container`)

3. **Automatic Startup:**
   - Backend (FastAPI) and frontend (React) start automatically via VS Code Tasks
   - Access the UI at `http://localhost:8080`

The DevContainer provides:
- Isolated Python 3.11+ environment
- Node.js 18+ for frontend
- All dependencies pre-installed
- Pre-configured development tools (ruff, pytest, etc.)

#### VS Code Tasks (Automatic on Container Open)

Two tasks run automatically when you open the container:

1. **Start Backend (FastAPI)** - Runs `uvicorn playtomic_agent.web.api:app` on port 8082
   - Auto-reloads when Python files change
   - View output in VS Code Terminal panel (group: "dev-servers")

2. **Start Frontend (React)** - Runs `npm run dev` on port 8080 (from `web/` directory)
   - Hot module replacement (HMR) enabled for instant UI updates
   - View output in same Terminal panel

Both tasks run in the background and share a terminal panel. You can:
- View logs: Open Terminal > "dev-servers" tab
- Stop/restart: Click the stop button or use Task palette
- Check status: Both services will show ready messages in terminal

#### Manual Task Management

If needed, manually control tasks:

**Run a task:**
- Use Command Palette: `Tasks: Run Task`
- Select "Start Backend (FastAPI)" or "Start Frontend (React)"

**Stop a task:**
- Terminal panel: Click the trash icon next to the task
- Or use Command Palette: `Tasks: Terminate Task`

### Local Development (Without Container)

For development outside a container (not recommended):

**Prerequisites:**
- Python 3.11+
- Node.js 18+

**Backend (FastAPI + LangGraph Agent):**
```bash
pip install -e ".[dev]"
uvicorn playtomic_agent.web.api:app --reload --port 8082
```

**Frontend (React + Vite):**
```bash
cd web
npm install
npm run dev -- --port 8080
```

Access the UI at `http://localhost:8080`.

## 🧪 Testing & Quality Assurance

### Running Tests
```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src/playtomic_agent --cov-report=html

# Specific test file
pytest tests/test_client.py -v
```

### Code Quality

```bash
# Format code (using ruff)
ruff format src/ tests/

# Lint
ruff check src/ tests/

# Type checking
mypy src/
```

**Configuration:**
- **Line length:** 100 characters (enforced by ruff)
- **Python version:** 3.11+
- **Type checking:** MyPy enabled (some LangChain/LangGraph libraries exempt from strict checking)

### Pre-commit Hooks

Pre-commit hooks are **automatically installed** when the DevContainer starts. They run on every commit and include:
- **Trailing whitespace** checks
- **File fixers** (end-of-file newlines, large files)
- **Ruff linter + formatter** (auto-fixes issues)
- **MyPy type checker** (excludes tests)

Manual run if needed:
```bash
pre-commit run --all-files
```

**In DevContainer:** Hooks are installed automatically via `.devcontainer/postCreateCommand.sh`

## 📝 Git & Commit Guidelines

### Branch Naming
- Feature: `feat/description`
- Bug fix: `fix/description`
- Refactor: `refactor/description`
- Docs: `docs/description`

### Commit Message Format

Use conventional commits:

```
type(scope): brief description

Longer explanation if needed.

Closes #123
```

**Type options:** `feat`, `fix`, `refactor`, `docs`, `test`, `chore`

**Example:**
```
feat(agent): add voice input support

Allows users to input queries via microphone using Web Speech API.
Integrates with Chat component and persists preference to profile.

Closes #45
```

### Pull Request Template

When creating a PR:
1. **Title**: Use same format as commit message (e.g., `feat(agent): add voice input`)
2. **Description**:
   - Summary of changes (2-3 bullet points)
   - Why this change was needed
   - Test plan (how to verify the changes work)
3. **Checklist**:
   - [ ] Tests pass (`pytest tests/`)
   - [ ] Code formatted (`ruff format`)
   - [ ] Linting passes (`ruff check`)
   - [ ] Type checking passes (`mypy src/`)
   - [ ] Updated DEVELOPER_GUIDE.md if needed
4. **Screenshots**: Add if UI changes

## 🔧 Key Components & Patterns

### Agent Architecture

**File:** `src/playtomic_agent/agent.py`

- **Function:** `create_playtomic_agent(user_profile, language)`
  - Returns a compiled LangGraph state graph
  - Injects system prompt with user preferences and current date/time
  - Uses Google Gemini as the LLM

- **System Prompt:**
  - Defines agent persona: "Padel court finder assistant"
  - Enforces rules: Only answer about Padel, never invent data
  - Provides workflow: Detect club → search → show results → suggest next steps
  - Includes user preferences dynamically

- **Tools Available:**
  - `find_slots`: Main tool, filters by club, date, court type, duration, time
  - `find_clubs_by_location`: Geocoding + nearby club search
  - `find_clubs_by_name`: Fuzzy name matching with retry logic
  - `create_booking_link`: Generates Playtomic booking URLs
  - `update_user_profile`: Silently save user preferences
  - `suggest_next_steps`: Send clickable suggestion chips
  - `is_weekend`: Check if date is weekend

### Playtomic Client

**File:** `src/playtomic_agent/client/api.py` - `PlaytomicClient` class

| Method | Purpose |
|--------|---------|
| `get_club(slug, name)` | Fetch club by slug or name |
| `get_available_slots(club, date, start_time, end_time)` | Get raw slots for a date |
| `filter_slots(club, slots, court_type, duration)` | Filter slots by type/duration |
| `find_slots(...)` | Convenience: chains get_club → get_available_slots → filter_slots |
| `search_clubs(query, lat, lon)` | Search by text or coordinates |
| `geocode(query, country_code)` | Get lat/lon from address |

Supports context manager: `with PlaytomicClient() as client:`

### Tools Implementation Pattern

**File:** `src/playtomic_agent/tools.py`

All tools use the `@tool` decorator from LangChain with type hints:

```python
@tool(description="Tool description shown to LLM")
def my_tool(
    param: Annotated[str, "Parameter description for LLM"],
) -> Annotated[ReturnType, "Return description"]:
    """Docstring seen by LLM."""
    # Implementation
    return result
```

### User Profile (Preferences)

**Backend:** `agent.py` - `_build_system_prompt()`
**Frontend:** `web/src/hooks/useProfile.js`

Supported keys:
- `preferred_club_slug` (e.g., "lemon-padel-club")
- `preferred_club_name` (e.g., "Lemon Padel")
- `preferred_city` (e.g., "Berlin")
- `court_type` (e.g., "DOUBLE")
- `duration` (e.g., 90)
- `preferred_time` (e.g., "evenings")

**Storage:** Persisted in browser `localStorage` key `padel-agent-profile`

When agent detects a preference, it calls `update_user_profile(key, value)`. Frontend intercepts `profile_suggestion` SSE events and shows a confirmation prompt.

### Request Context (Language, Country, Region)

**File:** `src/playtomic_agent/context.py`

The API sets per-request context variables that tools can read:

```python
from playtomic_agent.context import get_country, get_language, get_timezone

# In tools:
country = get_country()  # e.g., "DE"
language = get_language()  # e.g., "de"
timezone = get_timezone()  # e.g., "Europe/Berlin"
```

**How it works:**
1. Frontend sends `country`, `language`, `timezone` in request (via `RegionSelector` component)
2. API calls `set_request_region()` before agent runs
3. Tools read values via context vars (falls back to defaults if not set)
4. Agent system prompt uses language to respond in correct language

**Frontend:** `web/src/hooks/useRegion.js` manages selected region (persisted in `localStorage` key `padel_region`)

### API Layer & SSE Streaming

**File:** `src/playtomic_agent/api.py`

- **Endpoint:** `POST /api/chat`
- **Streaming:** Server-Sent Events (SSE)
- **Event types:**
  - `tool_start`: Agent calling a tool (e.g., `{"tool": "find_slots", "input": {...}}`)
  - `tool_end`: Tool finished (e.g., `{"tool": "find_slots", "output": {...}}`)
  - `message`: Final text response from agent
  - `profile_suggestion`: Preference to save
  - `suggestion_chips`: Clickable options list
  - `error`: Something failed

**Message truncation:** History limited to last 20 messages to keep context window manageable.

## ⚠️ Important Patterns & Gotchas

- **URL encoding**: Use `time.replace(':', '%3A')` in booking URLs (done in `client/utils.py`)
- **ContextVars, not globals**: Use `ContextVar` for per-request data (language, country, timezone) to avoid multi-user conflicts
- **Message truncation**: API keeps only last 20 messages. History beyond that unavailable to agent.
- **Tool returns**: Must be structured dicts/lists, not strings. Frontend expects specific schemas.
- **Ruff line length**: 100 character limit (stricter than 120/140). Break lines early.
- **MyPy strategy**: Enabled but selective (LangChain/LangGraph exempt). Use `Annotated` for tool params, avoid `# type: ignore` (prefer pyproject.toml overrides)

## 🔍 Common Tasks

### Adding a New Tool

1. **Define the tool** in `src/playtomic_agent/tools.py`:
   ```python
   @tool(description="What this tool does")
   def my_new_tool(
       param: Annotated[str, "Param description"],
   ) -> Annotated[dict, "Return description"]:
       """Docstring for LLM."""
       # Implementation
       return result
   ```

2. **Import & register** in `src/playtomic_agent/agent.py`:
   ```python
   from playtomic_agent.tools import my_new_tool

   TOOLS = [
       # ... existing tools
       my_new_tool,
   ]
   ```

3. **Restart backend** for changes to take effect.

### Adding a User Preference

1. **Backend** (`agent.py`):
   - Update `_build_system_prompt()` to include the new preference in the profile section
   - Update tool docstring if preference is saved via `update_user_profile`

2. **Frontend** (`web/src/hooks/useProfile.js`):
   - Add the key to `PROFILE_LABELS` for UI rendering
   - (Optional) Update `ProfileCard.jsx` for special handling

### Modifying System Prompt

Edit `_build_system_prompt()` in `agent.py`. The prompt includes:
- Current date/time (from `datetime.now()`)
- Timezone (from config)
- Language (from request context or config)
- User preferences (from profile dict)

Changes take effect after backend restart (or module reload if using `--reload`).

### Debugging Agent Behavior

1. **Check API logs** when backend is running
2. **Enable debug logging**:
   ```bash
   LOG_LEVEL=DEBUG uvicorn playtomic_agent.web.api:app --reload
   ```
3. **Test directly** (see `agent.py` `__main__`):
   ```python
   from playtomic_agent.web.agent import playtomic_agent

   for chunk in playtomic_agent.stream(
       {"messages": [{"role": "user", "content": "Find slots..."}]},
       stream_mode="updates"
   ):
       print(chunk)
   ```

### Testing & Debugging Tools

Test individual tools without the full agent:

**Via CLI:**
```bash
playtomic-agent search --name "Lemon Padel"
playtomic-agent slots --club-slug lemon-padel-club --date 2026-02-25
```

**Via Python:**
```python
from playtomic_agent.client.api import PlaytomicClient
with PlaytomicClient() as client:
    slots = client.find_slots("lemon-padel-club", "2026-02-25", court_type="DOUBLE")
    print(f"Found {len(slots)} slots")
```

**Debug tests:**
```bash
pytest tests/test_client.py::test_find_slots -v -s  # -s: show print output
pytest tests/ -v --pdb  # Drop into debugger on failure
```

### Running the CLI

The CLI entry point is defined in `pyproject.toml` and installed as `playtomic-agent` command.

**Search for clubs:**
```bash
playtomic-agent search --location "Berlin"
playtomic-agent search --name "Lemon Padel"
```

**Find slots:**
```bash
playtomic-agent slots \
    --club-slug lemon-padel-club \
    --date 2026-02-25 \
    --court-type DOUBLE \
    --duration 90 \
    --start-time 18:00 \
    --end-time 20:00 \
    --timezone Europe/Berlin
```

**Output as JSON:**
```bash
playtomic-agent slots --club-slug lemon-padel-club --json
```

**Implementation:** `src/playtomic_agent/client/cli.py` - Uses `argparse` with two subcommands: `search` and `slots`

## 🚨 Error Handling & Custom Exceptions

**File:** `src/playtomic_agent/client/exceptions.py`

The codebase defines specific exceptions for clear error handling:

| Exception | When raised | How to handle |
|-----------|-------------|---------------|
| `ClubNotFoundError` | Club lookup fails by slug/name | Suggest `find_clubs_by_name` or `find_clubs_by_location` |
| `MultipleClubsFoundError` | Name search returns multiple clubs | Ask user to be more specific |
| `SlotNotFoundError` | No slots match filters on date | Suggest nearby dates or relax filters |
| `APIError` | Playtomic API returns error (4xx/5xx) | Retry or inform user of service issue |
| `ValidationError` | Invalid input parameters | Check date format, club_slug format, etc. |

**Usage in tools:**

```python
from playtomic_agent.client.exceptions import ClubNotFoundError

try:
    club = client.get_club(slug="typo-club")
except ClubNotFoundError as e:
    # e.identifier, e.search_type, e.details available
    return None  # Tool should return None or handle gracefully
```

**In API responses:** Exceptions are caught and returned as error SSE events to frontend.

## 🛠️ Troubleshooting

| Issue | Solution |
|-------|----------|
| `No module named 'playtomic_agent'` | Run `pip install -e ".[dev]"` |
| Agent not responding / 429 errors | Check `GEMINI_API_KEY`, may be rate-limited (10 req/min), use `LOG_LEVEL=DEBUG` |
| Club not found | Verify `club_slug` format (lowercase, hyphens), use CLI `playtomic-agent search --name "X"` |
| No slots found | Check date isn't too far future (2-4 weeks ahead), verify date format `YYYY-MM-DD`, check timezone |
| Frontend connection error | Ensure backend on port 8082, check CORS in `api.py`, check browser console |

## 📚 Key Files for Agents

| File | Purpose | Key Functions/Classes |
|------|---------|----------------------|
| `agent.py` | Agent orchestration | `create_playtomic_agent()`, `_build_system_prompt()` |
| `tools.py` | LangChain tools | `find_slots`, `find_clubs_by_*`, `update_user_profile` |
| `api.py` | FastAPI server | `POST /api/chat`, SSE event streaming |
| `client/api.py` | Playtomic API client | `PlaytomicClient`, `find_slots()` |
| `config.py` | Settings | `Settings`, `get_settings()` |
| `models.py` | Data models | `Club`, `Court`, `Slot` |
| `client/cli.py` | CLI | `search`, `slots` commands |
| `web/src/components/Chat.jsx` | React chat UI | SSE consumption, message rendering |
| `web/src/hooks/useProfile.js` | User preferences | Profile storage & management |

## 🎯 Code Style & Conventions

- **Python**: Follow PEP 8, enforced by Ruff
- **Type hints**: Required for all function signatures
- **Docstrings**: Add to public functions/classes
- **Error handling**: Use custom exceptions from `client/exceptions.py`
- **Tools**: Always use `@tool` decorator with `Annotated` type hints
- **Frontend**: React hooks, CSS modules for styling

## 💡 Agent Tips & Best Practices

1. **Always use DevContainer** - Pre-configured, no local setup needed
2. **Data flow**: Frontend → API (FastAPI) → Agent (LangGraph) → Tools → Playtomic API → SSE back to frontend
3. **Tools are LLM's interface** - Only tools in `TOOLS` list (agent.py) are available to the agent
4. **Test tools directly** via CLI: `playtomic-agent search --name "Lemon Padel"`
5. **Profile updates are silent** - `update_user_profile()` returns dict; frontend handles UI
6. **Language support built-in** - Use `get_language()` for localization
7. **Use ContextVars, not globals** - Prevents multi-user conflicts
8. **Debug agent via system prompt** - `_build_system_prompt()` defines rules and workflow
9. **SSE events are the contract** - Frontend expects specific types/shapes (check `api.py`)
10. **Pre-commit runs automatically** - Hooks catch issues on commit; no manual linting needed

## ✅ Verification Checklist Before PR

- [ ] Tests pass: `pytest tests/ -v`
- [ ] Code formatted: `ruff format src/ tests/`
- [ ] Linting passes: `ruff check src/ tests/`
- [ ] Type checking: `mypy src/`
- [ ] No hardcoded API keys or secrets
- [ ] Commit messages follow convention
- [ ] PR title is descriptive
- [ ] Changes documented in commit message

---

**This is the primary guide for developers and AI agents working on the project.**
