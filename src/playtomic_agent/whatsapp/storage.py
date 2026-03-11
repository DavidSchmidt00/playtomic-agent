import datetime
import json
import logging
import os
import sqlite3
import threading
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class UserState:
    """Per-user state persisted across WhatsApp conversations."""

    profile: dict = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)
    language: str = ""  # BCP-47 code e.g. "de", "en" — empty until first detected
    active_poll: dict | None = None  # Most recent group poll; cleared once threshold is hit
    poll_count: int = 0  # Total native polls sent; switches to web vote links above threshold


class UserStorage:
    """Thread-safe SQLite-backed store keyed by WhatsApp sender ID.

    Schema: single table ``user_states`` with JSON-serialised columns for
    profile, history and active_poll.  Mirrors the VoteStore pattern
    (WAL mode, _connect / _init_db, ``with conn:`` transactions).
    """

    def __init__(self, path: str) -> None:
        self._path = path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        conn = self._connect()
        try:
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS user_states (
                        sender_id   TEXT PRIMARY KEY,
                        profile     TEXT NOT NULL DEFAULT '{}',
                        history     TEXT NOT NULL DEFAULT '[]',
                        language    TEXT NOT NULL DEFAULT '',
                        active_poll TEXT,
                        poll_count  INTEGER NOT NULL DEFAULT 0,
                        updated_at  TEXT NOT NULL
                    )
                """)
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, sender_id: str) -> UserState:
        """Return the stored state for a sender, or an empty UserState if unknown."""
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT profile, history, language, active_poll, poll_count "
                    "FROM user_states WHERE sender_id = ?",
                    (sender_id,),
                ).fetchone()
            finally:
                conn.close()
        if row is None:
            return UserState()
        return UserState(
            profile=json.loads(row["profile"]),
            history=json.loads(row["history"]),
            language=row["language"],
            active_poll=json.loads(row["active_poll"]) if row["active_poll"] else None,
            poll_count=row["poll_count"],
        )

    def save(self, sender_id: str, state: UserState) -> None:
        """Persist the state for a sender."""
        now = datetime.datetime.now(datetime.UTC).isoformat()
        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO user_states
                            (sender_id, profile, history, language, active_poll, poll_count, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(sender_id) DO UPDATE SET
                            profile     = excluded.profile,
                            history     = excluded.history,
                            language    = excluded.language,
                            active_poll = excluded.active_poll,
                            poll_count  = excluded.poll_count,
                            updated_at  = excluded.updated_at
                        """,
                        (
                            sender_id,
                            json.dumps(state.profile, ensure_ascii=False),
                            json.dumps(state.history, ensure_ascii=False),
                            state.language,
                            json.dumps(state.active_poll, ensure_ascii=False)
                            if state.active_poll is not None
                            else None,
                            state.poll_count,
                            now,
                        ),
                    )
            finally:
                conn.close()
        logger.debug("Saved state for sender %s", sender_id)
