# Playtomic CLI & AI Agent

> [!WARNING]
> This project is under **active development**. Features and APIs may change.

An AI-powered assistant and comprehensive toolkit for finding available Padel court slots on Playtomic. The project features a LangGraph-based agent that enables natural language interaction for slot search, along with a powerful Python client library and CLI.

## ✨ Features

- **🤖 AI Agent (LangGraph)**: Natural language interface to find the perfect slot
- **🐍 Python Client Library**: Class-based APIclient with full type hints
- **💻 Command-Line Interface**: Direct CLI for quick searches
- **🔍 Advanced Filtering**:
  - Filter by club (slug or name)
  - Filter by court type (SINGLE or DOUBLE)
  - Filter by time range with timezone support
  - Filter by slot duration (60, 90, 120 minutes)
- **🛡️ Robust Error Handling**: Custom exceptions for better debugging
- **✅ Fully Tested**: Comprehensive test suite with 65%+ coverage

## 📦 Installation

### From Source

```bash
git clone https://github.com/DavidSchmidt00/playtomic-agent.git
cd playtomic-agent
pip install -e .
```

### With Development Dependencies

```bash
pip install -e ".[dev]"
```

## ⚙️ Configuration

The application uses environment variables for configuration. Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

### Required Environment Variables

```bash
# Google Gemini API Keys (get from https://aistudio.google.com/)
GEMINI_API_KEY_FREE=your_free_tier_key
GEMINI_API_KEY_PAID=your_paid_tier_key

# Optional Configuration
DEFAULT_TIMEZONE=Europe/Berlin
DEFAULT_MODEL=gemini-3-flash-preview
PLAYTOMIC_API_BASE_URL=https://api.playtomic.io/v1
```

## 🚀 Usage

### 1. AI Agent (Natural Language)

#### Using LangGraph Studio/API

```bash
cd src/playtomic_agent
langgraph dev
```

Then interact through the LangGraph Studio UI or API.

#### Programmatic Usage

```python
from playtomic_agent.agent import playtomic_agent

# Stream agent responses
for chunk in playtomic_agent.stream(
    {"messages": [{"role": "user", "content":
        "Find a 90-minute double court slot at lemon-padel-club "
        "tomorrow between 18:00 and 20:00"
    }]},
    stream_mode="updates",
):
    for step, data in chunk.items():
        print(f"{step}: {data['messages'][-1].content}")
```

### 2. Python Client Library

The modern, class-based client provides full control:

```python
from playtomic_agent.client.api import PlaytomicClient

# Use as context manager for automatic cleanup
with PlaytomicClient() as client:
    # Find available slots
    slots = client.find_slots(
        club_slug="lemon-padel-club",
        date="2026-02-15",
        court_type="DOUBLE",
        start_time="18:00",
        end_time="20:00",
        timezone="Europe/Berlin",
        duration=90
    )

    for slot in slots:
        print(f"{slot.court_name}: {slot.time} - {slot.price}")
        print(f"Book: {slot.get_link()}")
```

#### Advanced Usage with Direct Methods

```python
from playtomic_agent.client.api import PlaytomicClient

with PlaytomicClient() as client:
    # 1. Get club information
    club = client.get_club(slug="lemon-padel-club")
    print(f"Club: {club.name} ({len(club.courts)} courts)")

    # 2. Get all available slots
    available_slots = client.get_available_slots(
        club,
        date="2026-02-15",
        start_time="18:00",  # UTC
        end_time="20:00"
    )

    # 3. Filter manually
    filtered = client.filter_slots(
        club,
        available_slots,
        court_type="DOUBLE",
        duration=90
    )
```

### 3. Command-Line Interface

The CLI supports two main modes: `search` and `slots`.

#### Search for Clubs
Find clubs by location (using geocoding) or by name.

```bash
# Search by Location
playtomic-agent search --location "Berlin"

# Search by Name
playtomic-agent search --name "Lemon Padel"
```

#### Find Available Slots
Find slots for a specific club.

```bash
# Find all slots for today
playtomic-agent slots --club-slug lemon-padel-club

# Find 90-minute double court slots tomorrow
playtomic-agent slots \
    --club-slug lemon-padel-club \
    --date 2026-02-15 \
    --court-type DOUBLE \
    --duration 90 \
    --start-time 18:00 \
    --end-time 20:00 \
    --timezone Europe/Berlin

# Output as JSON
playtomic-agent slots --club-slug lemon-padel-club --json
```

## � Web UI (Experimental) ✅

A minimal, extensible web frontend is included to interact with the LangGraph-based Playtomic agent. The frontend is a small React app (Vite) that talks to a FastAPI endpoint exposed by the Python service. It provides a centered chat UI with Markdown rendering and a loading indicator.

Quick start (Dev Container):

1. Install Python dependencies and start the API server (port 8082):

```bash
pip install -e .
uvicorn playtomic_agent.api:app --host 0.0.0.0 --port 8082
```

2. Start the frontend (port 8080):

```bash
cd web
npm install
npm run dev -- --port 8080
```

3. Open your browser at http://localhost:8080 to use the chat interface.

Notes:
- The frontend only displays the final assistant reply (internal reasoning/tool output is hidden).
- Add API-related settings (e.g. GEMINI API keys) to `.env` when using the agent for real runs.

---

## �🏗️ Architecture

```
playtomic-agent/
├── src/playtomic_agent/         # Main package
│   ├── agent.py                 # LangGraph AI agent
│   ├── tools.py                 # LangChain tools for agent
│   ├── config.py                # Configuration management
│   ├── models.py                # Pydantic data models
│   ├── client/                  # API client package
│   │   ├── api.py               # PlaytomicClient class
│   │   ├── exceptions.py        # Custom exceptions
│   │   ├── utils.py             # Utility functions
│   │   └── cli.py               # CLI implementation
│   └── langgraph.json           # LangGraph configuration
├── tests/                       # Comprehensive test suite
│   ├── conftest.py              # Pytest fixtures
│   ├── test_models.py           # Model tests
│   ├── test_exceptions.py       # Exception tests
│   └── test_client.py           # Client tests
├── pyproject.toml               # Modern Python packaging
└── .env                         # Environment configuration
```

## 🧪 Development

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src/playtomic_agent --cov-report=html

# Run specific test file
pytest tests/test_client.py -v
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint
ruff check src/ tests/

# Type checking
mypy src/
```

## 📚 API Reference

### PlaytomicClient

Main client class for interacting with the Playtomic API.

**Methods:**
- `get_club(slug=None, name=None)` - Fetch club information
- `get_available_slots(club, date, start_time=None, end_time=None)` - Get available slots
- `filter_slots(club, available_slots, court_type=None, duration=None)` - Filter slots
- `find_slots(club_slug, date, **filters)` - Convenience method combining all steps

**Exceptions:**
- `ClubNotFoundError` - Club not found
- `MultipleClubsFoundError` - Multiple clubs match identifier
- `APIError` - API request failed
- `ValidationError` - Invalid input parameters

### Models

All models are Pydantic models with full validation:

- `Club` - Represents a Playtomic club
- `Court` - Represents a court (single/double)
- `Slot` - Represents an available time slot

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch
3. Install development dependencies: `pip install -e ".[dev]"`
4. Write tests for new features
5. Ensure all tests pass: `pytest tests/`
6. Format code: `black src/ tests/`
7. Submit a pull request

## 📝 License

MIT

## 🙏 Acknowledgments

- Built with [LangGraph](https://github.com/langchain-ai/langgraph) for AI agent orchestration
- Powered by [Google Gemini](https://ai.google.dev/) for natural language understanding
- Uses the Playtomic API for court availability data

## 🔗 Links

- [Documentation](https://github.com/DavidSchmidt00/playtomic-agent)
- [Issue Tracker](https://github.com/DavidSchmidt00/playtomic-agent/issues)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
