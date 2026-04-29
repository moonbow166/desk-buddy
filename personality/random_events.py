"""Random event trigger for desk-buddy.

Stochastic pulse system: most of the time nothing happens,
but occasionally the buddy pipes up with something relevant
pulled from context + current mood.
"""

from __future__ import annotations

import random
from typing import Any

from personality.context import ContextBuffer
from personality.phrases import get_phrase


class RandomEventEngine:
    """Probability-based random event generator.

    Each call to ``maybe_trigger`` has a *base_probability* chance
    of producing an event. Intended to be called every few minutes.
    """

    def __init__(self, base_probability: float = 0.1) -> None:
        self.base_probability = base_probability
        self._last_context_note: str | None = None

    def maybe_trigger(
        self,
        context_buffer: ContextBuffer,
        mood: str,
    ) -> dict[str, Any] | None:
        """Roll the dice. Return an event dict or None.

        Event dict shape::

            {
                "type": "say" | "show",
                "content": str,
                "mood": str,
            }
        """
        if random.random() > self.base_probability:
            return None

        # Try to use something from the context buffer
        context_note = context_buffer.random_one()

        # Skip context note if it's the same one we just said
        use_context = (
            context_note
            and context_note != self._last_context_note
            and random.random() < 0.6
        )

        if use_context:
            # Reference a context note (but don't repeat the last one)
            self._last_context_note = context_note
            content = self._context_remark(context_note, mood)
            event_type = "say"
        else:
            # Fall back to a mood phrase (always varied)
            content = get_phrase(mood)
            event_type = random.choice(["say", "show"])

        return {
            "type": event_type,
            "content": content,
            "mood": mood,
        }

    @staticmethod
    def _context_remark(note: str, mood: str) -> str:
        """Build a remark that references a context note."""
        prefixes = {
            "happy": "Oh hey, remember this?",
            "chill": "By the way...",
            "sleepy": "Mmm, I was just dreaming about...",
            "curious": "I've been thinking about something...",
            "celebrate": "And also!",
        }
        prefix = prefixes.get(mood, "Oh,")
        return f"{prefix} {note}"
