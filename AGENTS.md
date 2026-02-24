# AGENTS.md

Agent reference for the Playtomic Agent project. See [README.md](README.md) for general info and [.agent/](./agent/) for rules and backlog.

## Project Structure

```
src/playtomic_agent/
├── web/
│   ├── agent.py        # create_playtomic_agent(), _build_system_prompt()
│   └── api.py          # FastAPI POST /api/chat, SSE streaming
├── whatsapp/
│   ├── server.py       # neonize entry point, on_message handler, user_locks
│   ├── agent.py        # create_whatsapp_agent(), extract_final_text/preference_updates()
│   └── storage.py      # UserStorage (JSON), UserState dataclass
├── tools.py            # All @tool-decorated LangChain tools
├── llm.py              # Gemini instance (shared by both agents)
├── config.py           # Settings (pydantic-settings, reads .env)
├── context.py          # ContextVar per-request: language, country, timezone
├── models.py           # Club, Court, Slot pydantic models
└── client/
    ├── api.py          # PlaytomicClient
    ├── cli.py          # playtomic-agent CLI (search / slots)
    ├── utils.py        # geocoding, booking link helpers
    └── exceptions.py   # ClubNotFoundError, SlotNotFoundError, APIError, …
web/                    # React 18 + Vite frontend (port 8080)
data/                   # Runtime data (gitignored)
  whatsapp_session.db   # neonize SQLite session (auto-created)
  whatsapp_users.json   # per-user WhatsApp state (auto-created)
tests/                  # pytest suite
```

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `LLM_PROVIDER` | no | `gemini` | LLM backend: `gemini` or `nvidia` |
| `GEMINI_API_KEY` | if provider=gemini | — | Google Gemini API key |
| `NVIDIA_API_KEY` | if provider=nvidia | — | NVIDIA API key (`nvapi-…`) |
| `NVIDIA_BASE_URL` | no | — | Base URL for a self-hosted NVIDIA NIM |
| `DEFAULT_MODEL` | no | provider default | Override model ID (e.g. `meta/llama-3.3-70b-instruct`) |
| `DEFAULT_TIMEZONE` | no | `Europe/Berlin` | Agent timezone |
| `PLAYTOMIC_API_BASE_URL` | no | `https://api.playtomic.io/v1` | Playtomic API base |
| `WHATSAPP_SESSION_DB` | WhatsApp only | `data/whatsapp_session.db` | neonize session file |
| `WHATSAPP_STORAGE_PATH` | WhatsApp only | `data/whatsapp_users.json` | per-user state file |

## Commands

```bash
# Run web backend
uvicorn playtomic_agent.web.api:app --reload --port 8082

# Run WhatsApp agent (scan QR on first run)
whatsapp-agent
LOG_LEVEL=DEBUG whatsapp-agent

# Tests & quality
pytest tests/ -v
ruff format src/ tests/
ruff check src/ tests/
mypy src/

# CLI (test tools without agent)
playtomic-agent search --name "Lemon Padel"
playtomic-agent slots --club-slug lemon-padel-club --date 2026-02-25 --json
```

## Architecture

### Web Channel

```
Frontend (React) → POST /api/chat (FastAPI)
  → set_request_region() [ContextVar]
  → create_playtomic_agent(profile, language).stream()
  → SSE events: tool_start | tool_end | message | profile_suggestion | suggestion_chips | error
```

### WhatsApp Channel

```
WhatsApp → neonize on_message handler
  → UserStorage.load(sender_id)           # load history + profile + language
  → create_whatsapp_agent(profile, lang)
  → asyncio.to_thread(agent.invoke(...))  # offload sync call
  → extract_final_text() + extract_preference_updates()
  → UserStorage.save()
  → wa_client.send_message(text)
```

Concurrency: per-user `asyncio.Lock` in `user_locks` dict prevents overlapping replies.
neonize runs its own asyncio loop (`event_global_loop`) in a daemon thread.

## Web vs. WhatsApp Agent

| | Web (`web/agent.py`) | WhatsApp (`whatsapp/agent.py`) |
|---|---|---|
| Tools | full set incl. `suggest_next_steps` | core tools only; no `suggest_next_steps` |
| Output | Markdown | **plain text only** |
| Language | per-request `ContextVar` | detected on first msg, persisted in `UserState.language` |
| Profile storage | browser `localStorage` | `data/whatsapp_users.json` |
| Response mode | SSE streaming | single `send_message()` after full invoke |

## Tools (`tools.py`)

| Tool | Purpose |
|------|---------|
| `find_slots` | Main tool — club + date + filters → available slots |
| `find_clubs_by_location` | Geocoding + nearby club search |
| `find_clubs_by_name` | Fuzzy name match with retry |
| `create_booking_link` | Generate Playtomic booking URL |
| `update_user_profile` | Persist a user preference (key/value) |
| `suggest_next_steps` | Emit clickable suggestion chips (web only) |
| `is_weekend` | Check if a date falls on a weekend |

To add a tool: define with `@tool` + `Annotated` params in `tools.py`, add to `TOOLS` list in the relevant `agent.py`.

## User Profile Keys

`preferred_club_slug`, `preferred_club_name`, `preferred_city`, `court_type`, `duration`, `preferred_time`

Web: stored in `localStorage` key `padel-agent-profile`.
WhatsApp: stored in `UserState.profile` → `data/whatsapp_users.json`.

## Exceptions (`client/exceptions.py`)

| Exception | Meaning |
|-----------|---------|
| `ClubNotFoundError` | Club not found by slug or name |
| `MultipleClubsFoundError` | Name search returned >1 club |
| `SlotNotFoundError` | No slots match filters |
| `APIError` | Playtomic API 4xx/5xx |

## Patterns & Gotchas

- **ContextVars, not globals** — use `get_language()`, `get_country()`, `get_timezone()` from `context.py` for per-request data.
- **Tool return values** — must be structured `dict`/`list`, not plain strings.
- **Message history** — capped at last 20 messages in both channels.
- **Ruff line length** — 100 chars (not 120). Break lines early.
- **MyPy** — enabled but LangChain/LangGraph packages are exempt. Use `Annotated` for tool params; avoid `# type: ignore` (prefer `pyproject.toml` overrides).
- **Booking URLs** — `time.replace(':', '%3A')` required (handled in `client/utils.py`).
- **WhatsApp language detection** — agent calls `update_user_profile("language", "<code>")` on first message; server extracts it and saves to `UserState.language` so it persists across sessions.

## Git Conventions

- Branch: `feat/`, `fix/`, `refactor/`, `docs/`, `chore/`
- Commit: conventional commits (`feat(scope): description`)
- See `.agent/rules/git.md` for agent-specific commit rules (emoji prefix, authorship footer)
- Pre-commit hooks run automatically on commit (ruff + mypy)

## Before Opening a PR

```bash
pytest tests/ -v
ruff format src/ tests/ && ruff check src/ tests/
mypy src/
```
