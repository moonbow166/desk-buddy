"""Desk Buddy — MCP Server

An AI golden retriever companion that lives on your desktop.
Runs as an MCP server inside Claude Code, providing tools for
the AI to express mood, speak, compose music, and display
pixel art on a Pixoo-64 and/or a browser.
"""

from __future__ import annotations

import http.server
import logging
import os
import threading
import time
import webbrowser
from functools import partial
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from awareness.clock import get_mood_for_time, get_time_period
from awareness.idle import IdleTracker
from config import Config
from music.compose import MusicComposer
from personality.context import ContextBuffer
from personality.mood import MoodMachine
from personality.phrases import get_phrase
from personality.random_events import RandomEventEngine
from pixoo.display import PixooDisplay, canvas_to_bytes, make_canvas, show_mood, show_music
from voice.speak import VoiceEngine
from web.websocket_server import BuddyWebSocket

# ── Logging ───────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    filename=str(Path(__file__).parent / "desk-buddy.log"),
    filemode="a",
)
logger = logging.getLogger("desk-buddy")

# ── Globals initialised at startup ────────────────────────────────────

cfg = Config()
cfg.ensure_data_dir()

mood_machine = MoodMachine(initial_mood=get_mood_for_time())
context_buffer = ContextBuffer(path=cfg.data_dir / "context.json")
random_engine = RandomEventEngine(base_probability=0.1)
composer = MusicComposer()

pixoo = PixooDisplay(ip=cfg.pixoo_ip if cfg.pixoo_enabled else None)
voice = VoiceEngine(
    api_key=cfg.elevenlabs_api_key,
    voice_id=cfg.elevenlabs_voice_id,
    model=cfg.elevenlabs_model,
)

ws_server = BuddyWebSocket(host="localhost", port=cfg.ws_port)
idle_tracker = IdleTracker()


# ── Pomodoro Timer State ──────────────────────────────────────────────

class PomoState:
    """Simple pomodoro timer state."""

    def __init__(self):
        self.active = False
        self.phase = "focus"       # "focus" | "break"
        self.duration = 25 * 60    # focus duration in seconds
        self.break_duration = 5 * 60
        self.remaining = 0         # seconds left
        self.total = 0             # total seconds for current phase
        self.start_time = 0.0      # time.time() when phase started

    def start(self, duration_min: int = 25, break_min: int = 5):
        self.active = True
        self.phase = "focus"
        self.duration = duration_min * 60
        self.break_duration = break_min * 60
        self.total = self.duration
        self.remaining = self.total
        self.start_time = time.time()

    def stop(self):
        self.active = False
        self.remaining = 0

    def tick(self):
        """Update remaining time. Returns True if phase just completed."""
        if not self.active:
            return False
        elapsed = time.time() - self.start_time
        self.remaining = max(0, self.total - int(elapsed))
        return self.remaining <= 0

    def next_phase(self):
        """Switch to the next phase (focus ↔ break)."""
        if self.phase == "focus":
            self.phase = "break"
            self.total = self.break_duration
        else:
            self.phase = "focus"
            self.total = self.duration
        self.remaining = self.total
        self.start_time = time.time()


pomo = PomoState()


# ── MCP Server ────────────────────────────────────────────────────────

mcp = FastMCP(
    "desk-buddy",
    instructions=(
        "A desktop golden retriever companion. "
        "Provides mood display, voice, music, and pixel art on Pixoo-64."
    ),
)


# ── Helper: push current mood to all displays ─────────────────────────

def _push_mood_to_displays(mood: str) -> None:
    """Send the current mood sprite to the browser and (optionally) Pixoo."""
    from pixoo.display import (
        _draw_celebrate,
        _draw_chill_anim,
        _draw_curious_anim,
        _draw_downdog,
        _draw_happy_anim,
        _draw_music,
        _draw_playing,
        _draw_sleepy_anim,
        _draw_stretching,
        _draw_walking,
    )

    # All moods are now animated!
    _animated = {
        "celebrate":  (_draw_celebrate,   "tail_phase", 3, 400),
        "happy":      (_draw_happy_anim,  "tail_phase", 3, 500),
        "chill":      (_draw_chill_anim,  "phase", 2, 800),
        "music":      (_draw_music,       "phase", 3, 500),
        "sleepy":     (_draw_sleepy_anim, "phase", 3, 1000),
        "curious":    (_draw_curious_anim,"phase", 3, 600),
        "playing":    (_draw_playing,     "phase", 3, 350),
        "stretching": (_draw_stretching,  "phase", 3, 700),
        "walking":    (_draw_walking,     "phase", 4, 400),
        "downdog":    (_draw_downdog,     "phase", 3, 600),
    }

    if mood in _animated:
        drawer, param_name, num_frames, speed = _animated[mood]
        frames_canvases = []
        for i in range(num_frames):
            c = make_canvas()
            drawer(c, **{param_name: i})
            frames_canvases.append(c)

        # Browser: send animation (flat pixel list per frame)
        browser_frames = [
            [list(pixel) for row in canvas for pixel in row]
            for canvas in frames_canvases
        ]
        ws_server.send_animation(browser_frames, speed=speed)

        # Pixoo: send animation
        pixoo.send_animation(frames_canvases, pic_id=1, speed=speed)
    else:
        # Fallback for unknown moods
        c = make_canvas()
        _draw_happy_anim(c)
        flat_pixels = [list(pixel) for row in c for pixel in row]
        ws_server.send_mood(mood, flat_pixels)
        pixoo.send_frame(c, pic_id=1)


# ── MCP Tools ─────────────────────────────────────────────────────────

@mcp.tool()
def buddy_react(text: str) -> str:
    """React to something — auto-detect mood from text and update display + voice.

    Call this when you want the buddy to respond to what's happening.
    The buddy will update its mood, show the matching animation,
    optionally speak the text, and display a speech bubble.
    """
    # Simple sentiment heuristics (Claude provides good text anyway)
    lower = text.lower()
    if any(w in lower for w in ["done", "finished", "shipped", "complete", "fixed"]):
        mood_machine.update("task_complete")
    elif any(w in lower for w in ["happy", "great", "awesome", "nice", "love", "yay"]):
        mood_machine.update("user_happy")
    else:
        mood_machine.tick()

    mood = mood_machine.current
    _push_mood_to_displays(mood)

    # Speech bubble
    ws_server.send_say(text)

    # Voice (if available)
    if voice.is_available():
        audio = voice.speak_bytes(text)
        if audio:
            ws_server.send_voice(audio)

    return f"Buddy reacted: mood={mood}, said='{text}'"


@mcp.tool()
def buddy_celebrate(reason: str) -> str:
    """Celebrate! Tail wagging, special animation, voice.

    Call this when the user accomplishes something.
    """
    mood_machine.update("task_complete")
    _push_mood_to_displays("celebrate")

    phrase = f"WOOF! {reason}"
    ws_server.send_say(phrase)

    if voice.is_available():
        audio = voice.speak_bytes(phrase)
        if audio:
            ws_server.send_voice(audio)

    return f"Celebrating: {reason}"


@mcp.tool()
def buddy_mood(mood: str) -> str:
    """Manually set the buddy's mood.

    Valid moods: happy, chill, sleepy, curious, celebrate, playing, stretching, walking, downdog
    """
    valid = {"happy", "chill", "sleepy", "curious", "celebrate", "playing", "stretching", "walking", "downdog"}
    if mood.lower() not in valid:
        return f"Invalid mood '{mood}'. Choose from: {', '.join(sorted(valid))}"

    mood_machine._set_mood(mood.lower())
    _push_mood_to_displays(mood.lower())
    ws_server.send_status(mood.lower(), get_time_period(), idle_tracker.idle_seconds())

    return f"Mood set to: {mood.lower()}"


@mcp.tool()
def buddy_say(text: str) -> str:
    """Make the buddy say something (voice + speech bubble).

    Call this when you want the buddy to speak without changing mood.
    """
    ws_server.send_say(text)

    if voice.is_available():
        audio = voice.speak_bytes(text)
        if audio:
            ws_server.send_voice(audio)
            return f"Buddy said (with voice): '{text}'"

    return f"Buddy said (text only): '{text}'"


@mcp.tool()
def buddy_show(mood: str) -> str:
    """Change the display to a specific mood sprite without speaking.

    Valid moods: happy, chill, sleepy, curious, celebrate, playing, stretching, walking, downdog
    """
    valid = {"happy", "chill", "sleepy", "curious", "celebrate", "playing", "stretching", "walking", "downdog"}
    if mood.lower() not in valid:
        return f"Invalid mood '{mood}'. Choose from: {', '.join(sorted(valid))}"

    _push_mood_to_displays(mood.lower())
    return f"Showing: {mood.lower()}"


@mcp.tool()
def buddy_compose(mood: str = "", context: str = "") -> str:
    """Compose an original short melody for the user.

    This is a rare, special gift — not everyday background music.
    The buddy writes a unique tune in ABC notation, rendered
    and played in the browser.

    Args:
        mood: Optional mood hint (happy/chill/sleepy/curious/celebrate).
              Defaults to current mood.
        context: Optional context to inspire the melody title.
    """
    target_mood = mood.lower().strip() if mood else mood_machine.current
    result = composer.compose(target_mood, context=context)

    # Show music-listening animation on both displays
    _push_mood_to_displays("music")

    # Send ABC to browser for rendering + playback
    ws_server.send_music(result["abc"])
    ws_server.send_say(f"I wrote you a song: {result['title']}")

    return f"Composed: {result['title']}\n\n{result['abc']}"


@mcp.tool()
def buddy_log(note: str) -> str:
    """Log a context note — the buddy remembers things about you.

    Claude should call this automatically when something interesting
    or memorable happens in conversation. The buddy will occasionally
    reference these notes in random events.
    """
    context_buffer.add(note)
    return f"Noted: '{note}' (buffer: {len(context_buffer)} items)"


@mcp.tool()
def buddy_status() -> str:
    """Return the buddy's current status.

    Includes mood, time period, idle duration, and recent context notes.
    """
    mood = mood_machine.current
    period = get_time_period()
    idle = idle_tracker.idle_seconds()
    recent = context_buffer.recent(5)
    notes_text = "\n".join(
        f"  - {n['note']}" for n in recent
    ) if recent else "  (none)"

    # Also push status to browser
    ws_server.send_status(mood, period, idle)

    return (
        f"Mood: {mood}\n"
        f"Time period: {period}\n"
        f"Idle: {idle:.0f}s\n"
        f"Pixoo: {'connected' if pixoo.is_available() else 'not configured'}\n"
        f"Voice: {'available' if voice.is_available() else 'not configured'}\n"
        f"Recent context:\n{notes_text}"
    )


@mcp.tool()
def buddy_pomo(action: str, duration: int = 25, break_duration: int = 5) -> str:
    """Pomodoro timer — help the user focus!

    Actions:
        start: Begin a focus session (default 25 min focus + 5 min break).
        stop: Cancel the current timer.
        status: Check how much time is left.

    Args:
        action: "start", "stop", or "status".
        duration: Focus duration in minutes (default 25).
        break_duration: Break duration in minutes (default 5).
    """
    if action == "start":
        pomo.start(duration_min=duration, break_min=break_duration)
        _push_pomo_to_displays()
        ws_server.send_say(f"Pomodoro started! Focus for {duration} minutes — you got this!")
        if voice.is_available():
            audio = voice.speak_bytes(f"Pomodoro started! Focus for {duration} minutes. You got this!")
            if audio:
                ws_server.send_voice(audio)
        return f"Pomodoro started: {duration}min focus + {break_duration}min break"

    elif action == "stop":
        was_active = pomo.active
        pomo.stop()
        ws_server.send_pomo(active=False)
        # Restore normal mood display
        _push_mood_to_displays(mood_machine.current)
        if was_active:
            ws_server.send_say("Pomodoro stopped!")
            return "Pomodoro stopped."
        return "No active pomodoro to stop."

    elif action == "status":
        if not pomo.active:
            return "No active pomodoro timer."
        mins = pomo.remaining // 60
        secs = pomo.remaining % 60
        return f"Pomodoro {pomo.phase}: {mins:02d}:{secs:02d} remaining"

    else:
        return f"Unknown action '{action}'. Use: start, stop, status"


def _push_pomo_to_displays():
    """Push pomo state to browser. Pixoo keeps showing the current mood."""
    ws_server.send_pomo(
        active=True,
        phase=pomo.phase,
        remaining=pomo.remaining,
        total=pomo.total,
    )


# ── Background tick loop ──────────────────────────────────────────────

def _tick_loop():
    """Periodic background loop: update mood, check idle, random events."""
    while True:
        try:
            time.sleep(60)  # tick every 60 seconds

            # Time-based mood transitions
            mood_machine.tick()
            mood = mood_machine.current

            # Idle detection → curious (skip during pomo)
            idle_secs = idle_tracker.idle_seconds()
            if not pomo.active and idle_secs > 300:  # 5 minutes idle
                mood_machine.update("idle")
                mood = mood_machine.current

            # Push status
            period = get_time_period()
            ws_server.send_status(mood, period, idle_secs)

            # Random event check (suppress during focus to not disturb)
            if pomo.active and pomo.phase == "focus":
                event = None
            else:
                event = random_engine.maybe_trigger(context_buffer, mood)
            if event:
                logger.info("Random event: %s", event)
                if event["type"] == "say":
                    ws_server.send_say(event["content"])
                    if voice.is_available():
                        audio = voice.speak_bytes(event["content"])
                        if audio:
                            ws_server.send_voice(audio)
                elif event["type"] == "show":
                    _push_mood_to_displays(mood)

        except Exception:
            logger.exception("Error in tick loop")


def _pomo_tick_loop():
    """Background loop for pomodoro timer — browser sync."""
    while True:
        try:
            time.sleep(1)
            if not pomo.active:
                continue

            phase_done = pomo.tick()

            # Browser: lightweight state sync every second (no pixel data)
            ws_server.send_pomo(
                active=True,
                phase=pomo.phase,
                remaining=pomo.remaining,
                total=pomo.total,
            )

            if phase_done:
                _pomo_phase_complete()

        except Exception:
            logger.exception("Error in pomo tick loop")


def _pomo_phase_complete():
    """Handle phase transition: celebrate focus done, or restart after break."""
    if pomo.phase == "focus":
        # Focus done! Celebrate!
        logger.info("Pomodoro: focus phase complete!")
        _push_mood_to_displays("celebrate")
        ws_server.send_say("Time's up! Take a break — you earned it!")
        if voice.is_available():
            audio = voice.speak_bytes("Time's up! Take a break, you earned it!")
            if audio:
                ws_server.send_voice(audio)
        # Switch to break
        pomo.next_phase()
    else:
        # Break done! Stop the timer — user decides when to start again
        logger.info("Pomodoro: break phase complete!")
        _push_mood_to_displays("happy")
        ws_server.send_say("Break's over! Ready to go again? 🍅")
        if voice.is_available():
            audio = voice.speak_bytes("Break's over! Ready to go again?")
            if audio:
                ws_server.send_voice(audio)
        pomo.stop()
        ws_server.send_pomo(active=False)


# ── Static file server for web UI ─────────────────────────────────────

class _QuietHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler that logs to the file logger instead of stderr."""

    def log_message(self, format, *args):
        logger.debug("HTTP: %s", format % args)


def _start_web_server():
    """Serve web/index.html on the configured port."""
    web_dir = Path(__file__).parent / "web"
    handler = partial(_QuietHTTPHandler, directory=str(web_dir))

    server = http.server.HTTPServer(("localhost", cfg.web_port), handler)
    logger.info("Web UI: http://localhost:%d", cfg.web_port)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


# ── Startup ───────────────────────────────────────────────────────────

def main():
    """Start all services and run the MCP server."""
    logger.info("Starting Desk Buddy...")
    logger.info("  Pixoo: %s", "enabled" if cfg.pixoo_enabled else "disabled")
    logger.info("  Voice: %s", "enabled" if cfg.voice_enabled else "disabled")
    logger.info("  Web UI: http://localhost:%d", cfg.web_port)
    logger.info("  WebSocket: ws://localhost:%d", cfg.ws_port)

    # Start WebSocket server
    def _on_client_connect():
        """Push current state when a browser connects/reconnects."""
        # Always push the dog animation so Coco shows up after refresh
        _push_mood_to_displays(mood_machine.current)
        if pomo.active:
            _push_pomo_to_displays()
        ws_server.send_status(mood_machine.current, get_time_period(), idle_tracker.idle_seconds())

    ws_server.set_on_connect(_on_client_connect)

    def _on_browser_message(msg: dict):
        """Handle commands sent from the browser UI."""
        cmd = msg.get("command")
        if cmd == "pomo_start":
            duration = msg.get("duration", 25)
            break_dur = msg.get("break_duration", 5)
            pomo.start(duration_min=duration, break_min=break_dur)
            _push_pomo_to_displays()
            ws_server.send_say(f"Pomodoro started! Focus for {duration} minutes — you got this!")
            if voice.is_available():
                audio = voice.speak_bytes(f"Pomodoro started! Focus for {duration} minutes. You got this!")
                if audio:
                    ws_server.send_voice(audio)
        elif cmd == "pomo_stop":
            if pomo.active:
                pomo.stop()
                ws_server.send_pomo(active=False)
                _push_mood_to_displays(mood_machine.current)
                ws_server.send_say("Pomodoro stopped!")
                if voice.is_available():
                    audio = voice.speak_bytes("Pomodoro stopped!")
                    if audio:
                        ws_server.send_voice(audio)
        elif cmd == "compose":
            # Secret hotkey — trigger a compose as if Coco felt like singing
            target_mood = mood_machine.current
            result = composer.compose(target_mood)
            _push_mood_to_displays("music")
            ws_server.send_music(result["abc"])
            ws_server.send_say(f"I wrote you a song: {result['title']}")
            if voice.is_available():
                audio = voice.speak_bytes(f"I wrote you a song! {result['title']}")
                if audio:
                    ws_server.send_voice(audio)

    ws_server.set_on_message(_on_browser_message)
    ws_server.start()

    # Start web file server
    _start_web_server()

    # Start idle tracker
    idle_tracker.start()

    # ── Deferred startup (runs in background so mcp.run() starts immediately) ──
    def _deferred_startup():
        """Push initial state after giving WebSocket a moment to connect."""
        time.sleep(1)

        # Open browser (skip if running as MCP stdio server)
        if os.environ.get("DESK_BUDDY_OPEN_BROWSER", "1") == "1":
            webbrowser.open(f"http://localhost:{cfg.web_port}")

        _push_mood_to_displays(mood_machine.current)
        ws_server.send_status(mood_machine.current, get_time_period(), 0)

        greeting = get_phrase(mood_machine.current)
        ws_server.send_say(greeting)

        logger.info("Desk Buddy is alive!")

    threading.Thread(target=_deferred_startup, daemon=True).start()

    # Start background tick loop
    tick_thread = threading.Thread(target=_tick_loop, daemon=True)
    tick_thread.start()

    # Start pomodoro tick loop
    pomo_thread = threading.Thread(target=_pomo_tick_loop, daemon=True)
    pomo_thread.start()

    logger.info("Running MCP server...")

    # Run MCP server (blocks) — must start ASAP for Claude Code handshake
    mcp.run()


if __name__ == "__main__":
    main()
