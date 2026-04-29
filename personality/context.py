"""Context buffer for desk-buddy.

Keeps a rolling window of recent notes with timestamps,
auto-expiring entries older than 24 hours. Persists to disk.
"""

from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path
from typing import Any

# Maximum notes to keep in the buffer
MAX_NOTES = 10

# Notes expire after 24 hours (in seconds)
EXPIRY_SECONDS = 24 * 60 * 60

# Default persistence path
DEFAULT_PATH = Path.home() / ".desk-buddy" / "context.json"


class ContextBuffer:
    """Rolling buffer of recent context notes with auto-expiry."""

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path else DEFAULT_PATH
        self._notes: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        """Load notes from disk if the file exists."""
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self._notes = data
            except (json.JSONDecodeError, OSError):
                self._notes = []
        self._prune()

    def _save(self) -> None:
        """Persist notes to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._notes, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _prune(self) -> None:
        """Remove expired notes and trim to MAX_NOTES."""
        now = time.time()
        self._notes = [
            n for n in self._notes
            if (now - n.get("ts", 0)) < EXPIRY_SECONDS
        ]
        # Keep only the most recent MAX_NOTES
        if len(self._notes) > MAX_NOTES:
            self._notes = self._notes[-MAX_NOTES:]

    def add(self, note: str) -> None:
        """Add a note with the current timestamp."""
        self._notes.append({
            "note": note,
            "ts": time.time(),
        })
        self._prune()
        self._save()

    def recent(self, n: int = 5) -> list[dict[str, Any]]:
        """Return the most recent *n* non-expired notes.

        Each entry is a dict with keys 'note' and 'ts'.
        """
        self._prune()
        return list(self._notes[-n:])

    def random_one(self) -> str | None:
        """Pick a random note from the buffer, or None if empty."""
        self._prune()
        if not self._notes:
            return None
        return random.choice(self._notes)["note"]

    def __len__(self) -> int:
        self._prune()
        return len(self._notes)
