import json
import logging
import os
import tempfile
import threading
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class UserState:
    """Per-user state persisted across WhatsApp conversations."""

    profile: dict = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)
    language: str = ""  # BCP-47 code e.g. "de", "en" — empty until first detected


class UserStorage:
    """Thread-safe JSON-backed store keyed by WhatsApp sender phone number.

    The storage file is a flat JSON object mapping sender IDs to their state.
    Writes are atomic: data is written to a temp file and then renamed.
    """

    def __init__(self, path: str) -> None:
        self._path = path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    def _read_all(self) -> dict[str, dict]:
        if not os.path.exists(self._path):
            return {}
        try:
            with open(self._path) as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            logger.warning("Could not read user storage at %s, starting fresh", self._path)
            return {}

    def _write_all(self, data: dict) -> None:
        dir_ = os.path.dirname(os.path.abspath(self._path))
        with tempfile.NamedTemporaryFile("w", dir=dir_, delete=False, suffix=".tmp") as tmp:
            json.dump(data, tmp, ensure_ascii=False, indent=2)
            tmp_path = tmp.name
        os.replace(tmp_path, self._path)

    def load(self, sender_id: str) -> UserState:
        """Return the stored state for a sender, or an empty UserState if unknown."""
        with self._lock:
            all_data = self._read_all()
        raw = all_data.get(sender_id, {})
        return UserState(
            profile=raw.get("profile", {}),
            history=raw.get("history", []),
            language=raw.get("language", ""),
        )

    def save(self, sender_id: str, state: UserState) -> None:
        """Persist the state for a sender."""
        with self._lock:
            all_data = self._read_all()
            all_data[sender_id] = {
                "profile": state.profile,
                "history": state.history,
                "language": state.language,
            }
            self._write_all(all_data)
        logger.debug("Saved state for sender %s", sender_id)
