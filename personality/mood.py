"""Mood state machine for desk-buddy.

Manages transitions between mood states based on time of day,
user events, and idle detection.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from personality.phrases import get_phrase

# Valid mood states
MOODS = {"happy", "chill", "sleepy", "curious", "celebrate"}

# Map each mood to a sprite name for display
MOOD_SPRITES: dict[str, str] = {
    "happy": "buddy_happy",
    "chill": "buddy_chill",
    "sleepy": "buddy_sleepy",
    "curious": "buddy_curious",
    "celebrate": "buddy_celebrate",
}

# How long the celebrate mood lasts (seconds)
CELEBRATE_DURATION = 120  # 2 minutes


class MoodMachine:
    """State machine that tracks and transitions the buddy's mood."""

    def __init__(self, initial_mood: str = "chill") -> None:
        if initial_mood not in MOODS:
            initial_mood = "chill"
        self._mood: str = initial_mood
        self._celebrate_start: float | None = None

    @property
    def current(self) -> str:
        """Return the current mood."""
        return self._mood

    @property
    def sprite(self) -> str:
        """Return the sprite name for the current mood."""
        return MOOD_SPRITES.get(self._mood, "buddy_chill")

    @property
    def phrase(self) -> str:
        """Return a random phrase matching the current mood."""
        return get_phrase(self._mood)

    def _set_mood(self, mood: str) -> None:
        """Set mood, resetting celebrate timer if leaving celebrate."""
        if mood not in MOODS:
            return
        if self._mood == "celebrate" and mood != "celebrate":
            self._celebrate_start = None
        self._mood = mood

    def update(self, event: str) -> str:
        """Process an event and transition mood accordingly.

        Supported events:
            task_complete  - user finished a task
            idle           - user has been idle a long time
            user_happy     - user said something happy
            time_check     - re-evaluate based on current time

        Returns the new mood after processing the event.
        """
        if event == "task_complete":
            self._mood = "celebrate"
            self._celebrate_start = time.monotonic()
        elif event == "idle":
            if self._mood != "celebrate":
                self._set_mood("curious")
        elif event == "user_happy":
            if self._mood != "celebrate":
                self._set_mood("happy")
        elif event == "time_check":
            self._apply_time_rules()

        return self._mood

    def tick(self) -> str:
        """Called periodically. Handles time-based transitions and
        the celebrate timeout.

        Returns the current mood after any transitions.
        """
        # Check celebrate timeout
        if (
            self._mood == "celebrate"
            and self._celebrate_start is not None
            and (time.monotonic() - self._celebrate_start) >= CELEBRATE_DURATION
        ):
            self._celebrate_start = None
            self._mood = "chill"

        # Apply time-based rules (but don't override celebrate)
        if self._mood != "celebrate":
            self._apply_time_rules()

        return self._mood

    def _apply_time_rules(self) -> None:
        """Transition mood based on current hour."""
        hour = datetime.now().hour

        if 6 <= hour < 9:
            # Early morning: drift from sleepy to chill
            if self._mood not in ("happy", "curious"):
                self._mood = "sleepy" if hour < 8 else "chill"
        elif 9 <= hour < 22:
            # Daytime: default to chill unless in a special state
            if self._mood == "sleepy":
                self._mood = "chill"
        else:
            # After 10pm or before 6am
            if self._mood not in ("celebrate",):
                self._mood = "sleepy"

    def to_dict(self) -> dict[str, Any]:
        """Serialize state for persistence or transport."""
        return {
            "mood": self._mood,
            "sprite": self.sprite,
            "celebrate_start": self._celebrate_start,
        }
