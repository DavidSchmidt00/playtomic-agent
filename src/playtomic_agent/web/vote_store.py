"""SQLite-backed vote session store for WEB-3 group coordination."""

import json
import random
import sqlite3
import string
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel

_DEFAULT_DB = Path("data/votes.db")


class SessionNotFoundError(ValueError):
    """Raised when a vote session does not exist or has expired."""


class InvalidSlotError(ValueError):
    """Raised when the requested slot_id is not part of the session."""


class VoteSlot(BaseModel):
    slot_id: str
    date: str  # YYYY-MM-DD
    local_time: str  # HH:MM
    court: str
    court_type: str | None = None  # "SINGLE" | "DOUBLE"
    duration: int
    price: str
    booking_link: str


class VoteStore:
    def __init__(self, db_path: Path = _DEFAULT_DB) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        conn = self._connect()
        try:
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS vote_sessions (
                        vote_id TEXT PRIMARY KEY,
                        slots_json TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        metadata_json TEXT DEFAULT '{}',
                        notified_slots TEXT DEFAULT '[]'
                    )
                """)
                # Handle migrations for existing DB — suppress only "duplicate column name"
                for col, default in [
                    ("metadata_json", "'{}'"),
                    ("notified_slots", "'[]'"),
                ]:
                    try:
                        conn.execute(
                            f"ALTER TABLE vote_sessions ADD COLUMN {col} TEXT DEFAULT {default}"
                        )
                    except sqlite3.OperationalError as exc:
                        if "duplicate column name" not in str(exc):
                            raise
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS votes (
                        vote_id TEXT NOT NULL,
                        voter_name TEXT NOT NULL,
                        slot_id TEXT NOT NULL,
                        can_attend INTEGER NOT NULL DEFAULT 1,
                        PRIMARY KEY (vote_id, voter_name, slot_id),
                        FOREIGN KEY (vote_id) REFERENCES vote_sessions(vote_id)
                    )
                """)
        finally:
            conn.close()

    @staticmethod
    def _new_id() -> str:
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=8))

    def create(self, slots: list[VoteSlot], metadata: dict | None = None) -> str:
        vote_id = self._new_id()
        conn = self._connect()
        try:
            with conn:
                while conn.execute(
                    "SELECT 1 FROM vote_sessions WHERE vote_id=?", (vote_id,)
                ).fetchone():
                    vote_id = self._new_id()
                conn.execute(
                    "INSERT INTO vote_sessions (vote_id, slots_json, created_at, metadata_json, notified_slots) VALUES (?,?,?,?,?)",
                    (
                        vote_id,
                        json.dumps([s.model_dump() for s in slots]),
                        time.time(),
                        json.dumps(metadata) if metadata else "{}",
                        "[]",
                    ),
                )
        finally:
            conn.close()
        return vote_id

    def get(self, vote_id: str) -> dict[str, Any] | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT slots_json, IFNULL(metadata_json, '{}') as metadata_json, IFNULL(notified_slots, '[]') as notified_slots FROM vote_sessions WHERE vote_id=?",
                (vote_id,),
            ).fetchone()
            if row is None:
                return None

            slots = json.loads(row["slots_json"])
            metadata = json.loads(row["metadata_json"])
            notified_slots = json.loads(row["notified_slots"])

            # Expire the day after the latest slot date
            if slots:
                max_date = max(s["date"] for s in slots)
                expiry = date.fromisoformat(max_date) + timedelta(days=1)
                if date.today() > expiry:
                    return None

            slot_ids = {s["slot_id"] for s in slots}

            vote_rows = conn.execute(
                "SELECT voter_name, slot_id, can_attend FROM votes WHERE vote_id=?", (vote_id,)
            ).fetchall()
        finally:
            conn.close()

        tally = dict.fromkeys(slot_ids, 0)
        attendees: dict[str, list[str]] = {sid: [] for sid in slot_ids}
        voters: set[str] = set()
        for vr in vote_rows:
            voters.add(vr["voter_name"])
            if vr["can_attend"]:
                tally[vr["slot_id"]] += 1
                attendees[vr["slot_id"]].append(vr["voter_name"])

        return {
            "vote_id": vote_id,
            "slots": slots,
            "tally": tally,
            "voter_count": len(voters),
            "voters": sorted(voters),
            "attendees": attendees,
            "metadata": metadata,
            "notified_slots": notified_slots,
        }

    def record_vote(self, vote_id: str, voter: str, votes: dict[str, bool]) -> dict[str, Any]:
        """Record per-slot availability for a voter.

        ``votes`` maps slot_id → can_attend (True = can attend, False = cannot).
        All existing votes for this voter in this session are replaced.
        """
        session = self.get(vote_id)
        if session is None:
            raise SessionNotFoundError(f"Vote session {vote_id!r} not found or expired")
        slot_ids = {s["slot_id"] for s in session["slots"]}
        for sid in votes:
            if sid not in slot_ids:
                raise InvalidSlotError(f"Invalid slot_id: {sid!r}")
        conn = self._connect()
        try:
            with conn:
                conn.execute("DELETE FROM votes WHERE vote_id=? AND voter_name=?", (vote_id, voter))
                for sid, can_attend in votes.items():
                    conn.execute(
                        "INSERT INTO votes (vote_id, voter_name, slot_id, can_attend) VALUES (?,?,?,?)",
                        (vote_id, voter, sid, int(can_attend)),
                    )
        finally:
            conn.close()
        result = self.get(vote_id)
        if result is None:
            raise SessionNotFoundError(
                f"Vote session {vote_id!r} expired immediately after recording"
            )
        return result

    def mark_notified(self, vote_id: str, slot_id: str) -> None:
        """Mark a specific slot as notified.

        Read and write happen inside the same connection/transaction to prevent
        a TOCTOU race where two concurrent callers could overwrite each other's update.
        """
        conn = self._connect()
        try:
            with conn:
                row = conn.execute(
                    "SELECT IFNULL(notified_slots, '[]') FROM vote_sessions WHERE vote_id=?",
                    (vote_id,),
                ).fetchone()
                if row is None:
                    return
                notified = set(json.loads(row[0]))
                notified.add(slot_id)
                conn.execute(
                    "UPDATE vote_sessions SET notified_slots=? WHERE vote_id=?",
                    (json.dumps(list(notified)), vote_id),
                )
        finally:
            conn.close()
