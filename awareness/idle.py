"""Keyboard idle detection for desk-buddy.

Uses pynput to track the last keypress. Falls back gracefully
if pynput is not installed (idle_seconds always returns 0).
"""

from __future__ import annotations

import threading
import time


class IdleTracker:
    """Thread-safe tracker for keyboard idle time.

    Call ``start()`` to begin listening and ``stop()`` to tear down
    the listener. ``idle_seconds()`` returns how long since the last
    keypress (or 0 if pynput is unavailable).
    """

    def __init__(self) -> None:
        self._last_keypress: float = time.monotonic()
        self._lock = threading.Lock()
        self._listener: object | None = None
        self._available: bool = True

        # Probe for pynput at init time
        try:
            import pynput  # noqa: F401
        except ImportError:
            self._available = False

    def _on_press(self, _key: object) -> None:
        """Callback fired on every keypress."""
        with self._lock:
            self._last_keypress = time.monotonic()

    def start(self) -> None:
        """Start listening for keypresses in a background thread."""
        if not self._available:
            return

        from pynput import keyboard  # type: ignore[import-untyped]

        self._listener = keyboard.Listener(on_press=self._on_press)
        self._listener.start()  # type: ignore[union-attr]

    def stop(self) -> None:
        """Stop the keyboard listener."""
        if self._listener is not None:
            self._listener.stop()  # type: ignore[union-attr]
            self._listener = None

    def idle_seconds(self) -> float:
        """Return seconds since the last detected keypress.

        Returns 0.0 if pynput is not available.
        """
        if not self._available:
            return 0.0
        with self._lock:
            return time.monotonic() - self._last_keypress
