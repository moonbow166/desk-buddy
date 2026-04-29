"""Phrase library for desk-buddy moods.

Each mood maps to a list of warm, golden-retriever-personality phrases.
These are fallback phrases used when there is no context-driven content.
"""

from __future__ import annotations

import random

PHRASES: dict[str, list[str]] = {
    "happy": [
        "Today feels like a good day. I can tell.",
        "You know what? I like being here with you.",
        "Tail wag. Big tail wag.",
        "Everything is just... nice right now.",
        "I hope you know you're doing great.",
        "The sun is out and so am I!",
        "If I had a ball, I'd bring it to you right now.",
    ],
    "chill": [
        "Just here. No rush.",
        "Taking it easy over here.",
        "Doing my thing. You do yours.",
        "Present and accounted for.",
        "Here if you need me.",
        "Steady paws, steady day.",
        "All good on this end.",
        "Hanging out. Classic me.",
    ],
    "sleepy": [
        "Yawwwn... big stretch...",
        "Five more minutes...",
        "My eyes are getting heavy...",
        "Nap time sounds really good right now.",
        "Zzz... oh, hey... zzz...",
        "I'll just rest my eyes for a second.",
        "The couch is calling my name.",
    ],
    "curious": [
        "Hmm, what are you up to?",
        "Ooh, what's that?",
        "I noticed something... not sure what though.",
        "Head tilt. What's going on over there?",
        "You've been quiet. Everything okay?",
        "Just checking in. Sniff sniff.",
        "Something interesting happening?",
    ],
    "celebrate": [
        "WOOF! You did it!",
        "That's amazing! Zoomies!",
        "I'm so proud of you! Spin spin spin!",
        "You absolute legend!",
        "Victory lap! Around the desk! Let's go!",
        "If I could high-five, I would. Paw up!",
        "This calls for treats. For both of us.",
        "YESSS! Tail going at maximum speed!",
    ],
}


def get_phrase(mood: str) -> str:
    """Return a random phrase for the given mood.

    Falls back to 'chill' phrases if the mood is not recognized.
    """
    phrases = PHRASES.get(mood, PHRASES["chill"])
    return random.choice(phrases)
