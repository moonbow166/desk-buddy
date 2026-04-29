"""ABC music composer for desk-buddy.

Generates short, original melodies in ABC notation that can be rendered
in the browser via ABCJS.  No external music dependencies required.
"""

from __future__ import annotations

import logging
import random

logger = logging.getLogger(__name__)


# ── Mood profiles ──────────────────────────────────────────────────────

_MOOD_PROFILES: dict[str, dict] = {
    "happy": {
        "keys": ["C", "G", "D", "F"],
        "mode": "major",
        "tempo_range": (120, 140),
        "meter": "4/4",
        "default_length": "1/8",
        "note_pool": ["C", "D", "E", "F", "G", "A", "B", "c", "d", "e", "f", "g"],
        "rest_weight": 0.05,
        "leap_chance": 0.25,
        "bars": (8, 12),
        "style": "bright and cheerful",
    },
    "chill": {
        "keys": ["G", "C", "D"],
        "mode": "mixolydian",
        "tempo_range": (90, 100),
        "meter": "4/4",
        "default_length": "1/8",
        "note_pool": ["C", "D", "E", "F", "G", "A", "B", "c", "d", "e"],
        "rest_weight": 0.12,
        "leap_chance": 0.15,
        "bars": (8, 12),
        "style": "relaxed and mellow",
    },
    "sleepy": {
        "keys": ["F", "C", "Bb"],
        "mode": "major",
        "tempo_range": (60, 70),
        "meter": "3/4",
        "default_length": "1/4",
        "note_pool": ["C", "D", "E", "F", "G", "A", "c"],
        "rest_weight": 0.15,
        "leap_chance": 0.10,
        "bars": (8, 12),
        "style": "gentle lullaby",
    },
    "curious": {
        "keys": ["D", "A", "E"],
        "mode": "major",
        "tempo_range": (100, 115),
        "meter": "4/4",
        "default_length": "1/8",
        "note_pool": ["C", "D", "E", "^F", "G", "A", "B", "c", "d", "e", "^f", "g"],
        "rest_weight": 0.08,
        "leap_chance": 0.35,
        "bars": (8, 12),
        "style": "playful and inquisitive",
    },
    "celebrate": {
        "keys": ["D", "G", "C"],
        "mode": "major",
        "tempo_range": (132, 150),
        "meter": "4/4",
        "default_length": "1/8",
        "note_pool": ["C", "D", "E", "F", "G", "A", "B", "c", "d", "e", "f", "g", "a"],
        "rest_weight": 0.03,
        "leap_chance": 0.30,
        "bars": (10, 16),
        "style": "triumphant and bright",
    },
}

# Note durations expressed in multiples of the default length
_DURATIONS_44 = [
    ("", 2),    # one default-length note
    ("2", 3),   # double length
    ("/2", 1),  # half length
    ("3", 1),   # triple (dotted feel)
]

_DURATIONS_34 = [
    ("", 3),
    ("2", 2),
    ("/2", 1),
]


# ── Internal helpers ───────────────────────────────────────────────────

def _pick_duration(meter: str) -> str:
    """Return a random ABC duration suffix."""
    pool = _DURATIONS_34 if meter == "3/4" else _DURATIONS_44
    choices, weights = zip(*pool)
    return random.choices(choices, weights=weights, k=1)[0]


def _neighbour_note(note_pool: list[str], current_idx: int) -> int:
    """Return an index that is 1 or 2 steps from *current_idx*."""
    step = random.choice([-2, -1, 1, 2])
    return max(0, min(len(note_pool) - 1, current_idx + step))


def _leap_note(note_pool: list[str], current_idx: int) -> int:
    """Return an index that is 3-5 steps away."""
    step = random.choice([-5, -4, -3, 3, 4, 5])
    return max(0, min(len(note_pool) - 1, current_idx + step))


def _beats_per_bar(meter: str) -> int:
    """Number of default-length units that fill one bar."""
    if meter == "3/4":
        return 3   # 3 quarter notes
    return 8       # 4/4 with 1/8 default = 8 eighth notes


def _duration_units(dur: str) -> int:
    """How many default-length units a duration suffix represents."""
    if dur == "2":
        return 2
    if dur == "3":
        return 3
    if dur == "/2":
        # only valid when default_length is 1/4 (gives eighth)
        return 1
    return 1  # bare note = 1 unit


def _generate_melody(profile: dict) -> str:
    """Generate the melody body (bar lines included)."""
    note_pool = profile["note_pool"]
    meter = profile["meter"]
    rest_w = profile["rest_weight"]
    leap_chance = profile["leap_chance"]
    num_bars = random.randint(*profile["bars"])
    bpb = _beats_per_bar(meter)

    lines: list[str] = []
    current_line: list[str] = []
    idx = len(note_pool) // 2  # start in the middle of the range

    for bar_num in range(num_bars):
        bar_tokens: list[str] = []
        beats_left = bpb

        while beats_left > 0:
            dur = _pick_duration(meter)
            units = _duration_units(dur)
            if units > beats_left:
                # Fill remainder with single-unit notes
                dur = ""
                units = 1

            if random.random() < rest_w:
                bar_tokens.append(f"z{dur}")
            else:
                # Decide stepwise vs leap
                if random.random() < leap_chance:
                    idx = _leap_note(note_pool, idx)
                else:
                    idx = _neighbour_note(note_pool, idx)

                note = note_pool[idx]
                bar_tokens.append(f"{note}{dur}")

            beats_left -= units

        current_line.append(" ".join(bar_tokens))

        # Line break every 4 bars for readability
        if (bar_num + 1) % 4 == 0:
            lines.append(" | ".join(current_line) + " |")
            current_line = []

    # Final partial line
    if current_line:
        lines.append(" | ".join(current_line) + " |]")
    elif lines:
        # Replace trailing | with |] on last line
        lines[-1] = lines[-1].rstrip("|").rstrip() + " |]"

    return "\n".join(lines)


def _mode_annotation(mode: str) -> str:
    """Return the ABC mode suffix for the K: header."""
    if mode == "mixolydian":
        return " Mixolydian"
    if mode == "dorian":
        return " Dorian"
    return ""  # major is the default


def _make_title(mood: str, context: str) -> str:
    """Create a short human-readable title."""
    adjectives = {
        "happy": ["Sunny", "Bright", "Joyful", "Bouncy"],
        "chill": ["Mellow", "Easy", "Breezy", "Calm"],
        "sleepy": ["Dreamy", "Gentle", "Quiet", "Soft"],
        "curious": ["Wondering", "Playful", "Searching", "Quirky"],
        "celebrate": ["Triumphant", "Grand", "Festive", "Glorious"],
    }
    nouns = ["Tune", "Melody", "Song", "Theme", "Air"]
    adj = random.choice(adjectives.get(mood, ["Little"]))
    noun = random.choice(nouns)
    base = f"{adj} {noun}"
    if context:
        # Incorporate first few words of context
        snippet = " ".join(context.split()[:3]).rstrip(".,!?")
        return f"{base} ({snippet})"
    return base


# ── Public API ─────────────────────────────────────────────────────────

class MusicComposer:
    """Generates short original melodies in ABC notation."""

    def compose(self, mood: str, context: str = "") -> dict:
        """Return ``{"abc": str, "title": str}`` for the given *mood*.

        The ABC string includes full headers and is ready for ABCJS rendering.
        Unrecognised moods fall back to ``"happy"``.
        """
        mood = mood.lower().strip()
        if mood not in _MOOD_PROFILES:
            logger.warning("Unknown mood %r — falling back to 'happy'", mood)
            mood = "happy"

        profile = _MOOD_PROFILES[mood]
        key = random.choice(profile["keys"])
        tempo = random.randint(*profile["tempo_range"])
        title = _make_title(mood, context)
        mode_suffix = _mode_annotation(profile["mode"])

        melody = _generate_melody(profile)

        abc = (
            f"X:1\n"
            f"T:{title}\n"
            f"M:{profile['meter']}\n"
            f"L:{profile['default_length']}\n"
            f"Q:{profile['meter'].split('/')[0]}={tempo}\n"
            f"K:{key}{mode_suffix}\n"
            f"{melody}\n"
        )

        return {"abc": abc, "title": title}
