"""Project configuration for desk-buddy.

Loads settings from environment variables with sensible defaults.
Optionally reads a .env file from the project root if present.
"""

from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader. No external dependency needed.

    Reads KEY=VALUE lines, ignoring comments and blank lines.
    Does NOT override variables already set in the environment.
    """
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


class Config:
    """Central configuration loaded from env vars + optional .env file."""

    def __init__(self, env_file: str | Path | None = None) -> None:
        # Try to load .env from project root or a custom path
        if env_file:
            _load_dotenv(Path(env_file))
        else:
            _load_dotenv(Path(__file__).parent / ".env")

        # ElevenLabs
        self.elevenlabs_api_key: str = os.getenv("ELEVENLABS_API_KEY", "")
        self.elevenlabs_voice_id: str = os.getenv("ELEVENLABS_VOICE_ID", "")
        self.elevenlabs_model: str = os.getenv(
            "ELEVENLABS_MODEL", "eleven_multilingual_v2"
        )

        # Pixoo
        self.pixoo_ip: str = os.getenv("PIXOO_IP", "")

        # Buddy identity
        self.buddy_name: str = os.getenv("BUDDY_NAME", "Buddy")
        self.buddy_species: str = os.getenv("BUDDY_SPECIES", "golden")

        # Network
        self.web_port: int = int(os.getenv("BUDDY_WEB_PORT", "3456"))
        self.ws_port: int = int(os.getenv("BUDDY_WS_PORT", "3457"))

        # Data directory
        self.data_dir: Path = Path(
            os.getenv("DATA_DIR", str(Path.home() / ".desk-buddy"))
        )

    @property
    def pixoo_enabled(self) -> bool:
        """True if a Pixoo IP address is configured."""
        return bool(self.pixoo_ip)

    @property
    def voice_enabled(self) -> bool:
        """True if ElevenLabs API key is configured."""
        return bool(self.elevenlabs_api_key)

    def ensure_data_dir(self) -> Path:
        """Create the data directory if it does not exist and return it."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir
