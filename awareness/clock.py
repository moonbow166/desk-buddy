"""Time-of-day awareness for desk-buddy.

Provides simple helpers to determine the current time period
and suggest a mood based on the hour.
"""

from __future__ import annotations

from datetime import datetime


def get_time_period() -> str:
    """Return the current time period.

    Returns one of: 'morning', 'daytime', 'evening', 'night'.
    """
    hour = datetime.now().hour

    if 6 <= hour < 12:
        return "morning"
    elif 12 <= hour < 18:
        return "daytime"
    elif 18 <= hour < 22:
        return "evening"
    else:
        return "night"


def get_mood_for_time() -> str:
    """Map the current time period to a suggested mood.

    Returns a mood string suitable for MoodMachine.
    """
    period = get_time_period()
    mapping = {
        "morning": "sleepy",
        "daytime": "chill",
        "evening": "chill",
        "night": "sleepy",
    }
    return mapping[period]
