"""ElevenLabs voice adapter for desk-buddy.

Generates speech audio via the ElevenLabs REST API using only urllib
(no third-party HTTP libraries). Gracefully degrades when the API key
is missing or the service is unreachable.
"""

from __future__ import annotations

import json
import logging
import urllib.request

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT = "/tmp/buddy_voice.mp3"
DEFAULT_MODEL = "eleven_multilingual_v2"
API_BASE = "https://api.elevenlabs.io/v1/text-to-speech"


class VoiceEngine:
    """Stateful wrapper around the ElevenLabs text-to-speech API."""

    def __init__(
        self,
        api_key: str | None = None,
        voice_id: str | None = None,
        model: str = DEFAULT_MODEL,
    ):
        self._api_key = api_key.strip() if api_key else None
        self._voice_id = voice_id.strip() if voice_id else None
        self._model = model

        if not self._api_key:
            logger.warning("VoiceEngine: no API key — speech will be unavailable")
        if not self._voice_id:
            logger.warning("VoiceEngine: no voice_id — speech will be unavailable")

    def is_available(self) -> bool:
        """Return True when both api_key and voice_id are configured."""
        return bool(self._api_key and self._voice_id)

    def speak(self, text: str, output_path: str | None = None) -> str | None:
        """Synthesise *text* and write the MP3 to *output_path*.

        Returns the path on success, or ``None`` on failure.
        """
        audio = self.speak_bytes(text)
        if audio is None:
            return None

        path = output_path or DEFAULT_OUTPUT
        try:
            with open(path, "wb") as f:
                f.write(audio)
            logger.info("Wrote %d bytes to %s", len(audio), path)
            return path
        except OSError:
            logger.exception("Failed to write audio to %s", path)
            return None

    def speak_bytes(self, text: str) -> bytes | None:
        """Synthesise *text* and return raw MP3 bytes (or ``None``)."""
        if not self.is_available():
            logger.warning("VoiceEngine not configured — skipping TTS")
            return None

        body = json.dumps({
            "text": text,
            "model_id": self._model,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "speed": 0.9,
            },
        }).encode()

        req = urllib.request.Request(
            f"{API_BASE}/{self._voice_id}",
            data=body,
            headers={
                "xi-api-key": self._api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read()
        except Exception:
            logger.exception("ElevenLabs TTS request failed")
            return None


# ── Module-level convenience functions ─────────────────────────────────

def speak_to_file(
    text: str,
    api_key: str,
    voice_id: str,
    model: str = DEFAULT_MODEL,
    output_path: str = DEFAULT_OUTPUT,
) -> str | None:
    """One-shot helper: synthesise *text* to a file and return its path."""
    engine = VoiceEngine(api_key=api_key, voice_id=voice_id, model=model)
    return engine.speak(text, output_path=output_path)


def speak_to_bytes(
    text: str,
    api_key: str,
    voice_id: str,
    model: str = DEFAULT_MODEL,
) -> bytes | None:
    """One-shot helper: synthesise *text* and return raw MP3 bytes."""
    engine = VoiceEngine(api_key=api_key, voice_id=voice_id, model=model)
    return engine.speak_bytes(text)
