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


class VoteSlot(BaseModel):
    slot_id: str
    date: str  # YYYY-MM-DD
    local_time: str  # HH:MM
    court: str
    court_type: str  # "SINGLE" | "DOUBLE"
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
                        created_at REAL NOT NULL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS votes (
                        vote_id TEXT NOT NULL,
                        voter_name TEXT NOT NULL,
                        slot_id TEXT NOT NULL,
                        PRIMARY KEY (vote_id, voter_name),
                        FOREIGN KEY (vote_id) REFERENCES vote_sessions(vote_id)
                    )
                """)
        finally:
            conn.close()

    @staticmethod
    def _new_id() -> str:
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=8))

    def create(self, slots: list[VoteSlot]) -> str:
        vote_id = self._new_id()
        conn = self._connect()
        try:
            with conn:
                while conn.execute(
                    "SELECT 1 FROM vote_sessions WHERE vote_id=?", (vote_id,)
                ).fetchone():
                    vote_id = self._new_id()
                conn.execute(
                    "INSERT INTO vote_sessions (vote_id, slots_json, created_at) VALUES (?,?,?)",
                    (vote_id, json.dumps([s.model_dump() for s in slots]), time.time()),
                )
        finally:
            conn.close()
        return vote_id

    def get(self, vote_id: str) -> dict[str, Any] | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT slots_json FROM vote_sessions WHERE vote_id=?",
                (vote_id,),
            ).fetchone()
            if row is None:
                return None

            slots = json.loads(row["slots_json"])

            # Expire the day after the latest slot date
            if slots:
                max_date = max(s["date"] for s in slots)
                expiry = date.fromisoformat(max_date) + timedelta(days=1)
                if date.today() > expiry:
                    return None

            slot_ids = {s["slot_id"] for s in slots}

            vote_rows = conn.execute(
                "SELECT voter_name, slot_id FROM votes WHERE vote_id=?", (vote_id,)
            ).fetchall()
        finally:
            conn.close()

        tally = dict.fromkeys(slot_ids, 0)
        votes: dict[str, str] = {}
        for vr in vote_rows:
            votes[vr["voter_name"]] = vr["slot_id"]
        for sid in votes.values():
            if sid in tally:
                tally[sid] += 1

        return {
            "vote_id": vote_id,
            "slots": slots,
            "tally": tally,
            "voter_count": len(votes),
        }

    def record_vote(self, vote_id: str, voter: str, slot_id: str) -> dict[str, Any]:
        session = self.get(vote_id)
        if session is None:
            raise ValueError(f"Vote session {vote_id!r} not found or expired")
        slot_ids = {s["slot_id"] for s in session["slots"]}
        if slot_id not in slot_ids:
            raise ValueError(f"Invalid slot_id: {slot_id!r}")
        conn = self._connect()
        try:
            with conn:
                conn.execute(
                    """INSERT INTO votes (vote_id, voter_name, slot_id) VALUES (?,?,?)
                       ON CONFLICT(vote_id, voter_name) DO UPDATE SET slot_id=excluded.slot_id""",
                    (vote_id, voter, slot_id),
                )
        finally:
            conn.close()
        return self.get(vote_id)  # type: ignore[return-value]
