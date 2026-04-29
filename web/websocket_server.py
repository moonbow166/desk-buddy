"""WebSocket server for Desk Buddy web UI."""

import asyncio
import base64
import json
import logging
import threading
from typing import Optional

import websockets
from websockets.server import WebSocketServerProtocol

logger = logging.getLogger(__name__)


class BuddyWebSocket:
    """WebSocket server that broadcasts buddy state to connected browser clients."""

    def __init__(self, host: str = "localhost", port: int = 3457):
        self.host = host
        self.port = port
        self._clients: set[WebSocketServerProtocol] = set()
        self._server = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._on_connect_callback = None
        self._on_message_callback = None

    # ---- Server lifecycle ----

    def start(self):
        """Start the WebSocket server in a background thread."""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("WebSocket server starting on ws://%s:%s", self.host, self.port)

    def _run(self):
        """Entry point for the background thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._serve())

    async def _serve(self):
        """Run the server until stopped."""
        self._server = await websockets.serve(
            self._handler,
            self.host,
            self.port,
        )
        await self._server.wait_closed()

    def stop(self):
        """Stop the server and clean up."""
        if self._server is not None:
            self._server.close()
        if self._loop is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("WebSocket server stopped")

    # ---- Connection handling ----

    def set_on_connect(self, callback):
        """Register a callback to run when a new client connects.

        The callback receives no arguments and should call broadcast/send
        methods to push the current state to all clients.
        """
        self._on_connect_callback = callback

    def set_on_message(self, callback):
        """Register a callback for incoming browser messages.

        The callback receives a parsed dict (the JSON message).
        It runs in the asyncio thread — keep it fast or spawn a thread.
        """
        self._on_message_callback = callback

    async def _handler(self, websocket: WebSocketServerProtocol):
        """Handle a single client connection."""
        self._clients.add(websocket)
        remote = websocket.remote_address
        logger.info("Client connected: %s", remote)
        # Push current state to the newly connected client
        if self._on_connect_callback:
            try:
                self._on_connect_callback()
            except Exception:
                logger.exception("Error in on_connect callback")
        try:
            async for raw in websocket:
                if self._on_message_callback:
                    try:
                        msg = json.loads(raw)
                        # Run callback in a thread so it can do blocking work
                        threading.Thread(
                            target=self._on_message_callback,
                            args=(msg,),
                            daemon=True,
                        ).start()
                    except Exception:
                        logger.exception("Error handling browser message")
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self._clients.discard(websocket)
            logger.info("Client disconnected: %s", remote)

    # ---- Broadcasting ----

    def broadcast(self, message: dict):
        """Send a JSON message to every connected client."""
        if not self._clients or self._loop is None:
            return
        data = json.dumps(message)
        asyncio.run_coroutine_threadsafe(self._broadcast_async(data), self._loop)

    async def _broadcast_async(self, data: str):
        """Internal async broadcast to all clients."""
        if not self._clients:
            return
        stale: list[WebSocketServerProtocol] = []
        for client in list(self._clients):
            try:
                await client.send(data)
            except websockets.exceptions.ConnectionClosed:
                stale.append(client)
        for client in stale:
            self._clients.discard(client)

    # ---- Convenience methods ----

    def send_mood(self, mood: str, sprite_data: list):
        """Send a mood update with sprite pixel data.

        Args:
            mood: Current mood name (e.g. "happy", "sleepy").
            sprite_data: Flat list of [r, g, b] values for each 64x64 pixel.
        """
        self.broadcast({
            "type": "mood",
            "mood": mood,
            "sprite": sprite_data,
        })

    def send_animation(self, frames: list, speed: int = 500):
        """Send an animation sequence.

        Args:
            frames: List of sprite frames, each a flat list of [r, g, b] pixels.
            speed: Milliseconds between frames.
        """
        self.broadcast({
            "type": "animation",
            "frames": frames,
            "speed": speed,
        })

    def send_voice(self, audio_bytes: bytes):
        """Send voice audio to the browser for playback.

        Args:
            audio_bytes: Raw MP3 bytes.
        """
        audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
        self.broadcast({
            "type": "voice",
            "audio_b64": audio_b64,
        })

    def send_music(self, abc: str):
        """Send ABC notation to be rendered and played.

        Args:
            abc: ABC music notation string.
        """
        self.broadcast({
            "type": "music",
            "abc": abc,
        })

    def send_say(self, text: str):
        """Send text to display in the speech bubble.

        Args:
            text: Message the buddy wants to say.
        """
        self.broadcast({
            "type": "say",
            "text": text,
        })

    def send_status(self, mood: str, period: str, idle: float):
        """Send a status update for the status bar.

        Args:
            mood: Current mood name.
            period: Time period (e.g. "morning", "daytime", "evening").
            idle: Seconds the user has been idle.
        """
        self.broadcast({
            "type": "status",
            "mood": mood,
            "period": period,
            "idle": idle,
        })

    def send_pomo(self, active: bool, phase: str = "", remaining: int = 0, total: int = 0):
        """Send pomodoro timer state to the browser.

        Args:
            active: Whether the timer is running.
            phase: "focus" or "break".
            remaining: Seconds remaining in current phase.
            total: Total seconds for current phase.
        """
        self.broadcast({
            "type": "pomo",
            "active": active,
            "phase": phase,
            "remaining": remaining,
            "total": total,
        })
