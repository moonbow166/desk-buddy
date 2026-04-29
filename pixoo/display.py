"""Pixoo 64 display adapter for desk-buddy.

Sends RGB pixel data to a Divoom Pixoo-64 via its local HTTP API.
If no IP is configured, all methods degrade gracefully to no-ops.
"""

from __future__ import annotations

import base64
import json
import logging
import urllib.request

logger = logging.getLogger(__name__)

W = 64

# ── Palette ────────────────────────────────────────────────────────────
GOLDEN = (218, 165, 80)
GOLDEN_DARK = (180, 130, 55)
GOLDEN_LIGHT = (235, 195, 120)
NOSE = (40, 35, 30)
TONGUE = (220, 100, 100)
EYE = (50, 40, 30)
BG = (25, 25, 35)


# ── Canvas helpers ─────────────────────────────────────────────────────

def make_canvas(w: int = 64) -> list[list[tuple]]:
    """Return a w x w canvas filled with BG colour."""
    return [[BG for _ in range(w)] for _ in range(w)]


def set_pixel(canvas: list, x: int, y: int, color: tuple) -> None:
    """Set a single pixel; out-of-bounds writes are silently ignored."""
    w = len(canvas)
    if 0 <= x < w and 0 <= y < w:
        canvas[y][x] = color


def canvas_to_bytes(canvas: list) -> bytes:
    """Flatten canvas to raw RGB byte sequence."""
    data = bytearray()
    for row in canvas:
        for r, g, b in row:
            data.append(r)
            data.append(g)
            data.append(b)
    return bytes(data)


# ── Convenience drawing primitives ─────────────────────────────────────

def _fill_rect(canvas, x1, y1, x2, y2, color):
    for y in range(y1, y2 + 1):
        for x in range(x1, x2 + 1):
            set_pixel(canvas, x, y, color)


def _hline(canvas, x1, x2, y, color):
    for x in range(x1, x2 + 1):
        set_pixel(canvas, x, y, color)


# ── PixooDisplay class ─────────────────────────────────────────────────

class PixooDisplay:
    """Thin wrapper around the Pixoo-64 local HTTP API."""

    def __init__(self, ip: str | None = None):
        self._ip = ip.strip() if ip else None
        self._channel_set = False
        if not self._ip:
            logger.info("PixooDisplay: no IP provided — running in no-op mode")

    # ── public API ──

    def is_available(self) -> bool:
        """Return True when an IP is configured (does not probe the network)."""
        return self._ip is not None

    def _ensure_custom_channel(self) -> None:
        """Switch Pixoo to the custom channel (index 3) for SendHttpGif."""
        if self._channel_set:
            return
        self._post({"Command": "Draw/ResetHttpGifId"})
        self._post({"Command": "Channel/SetIndex", "SelectIndex": 3})
        self._channel_set = True
        logger.info("Pixoo: switched to custom channel")

    def reset_gif(self):
        """Clear the GIF buffer so the next frame starts fresh.

        Call this before switching from a multi-frame animation to a
        single static frame — otherwise Pixoo may keep cycling the old
        animation instead of showing the new image.
        """
        if self._ip:
            self._post({"Command": "Draw/ResetHttpGifId"})

    def send_frame(self, canvas: list[list[tuple]], pic_id: int = 1) -> bool:
        """Send a single static frame. Returns True on success."""
        if not self._ip:
            return False
        self._ensure_custom_channel()
        b64 = base64.b64encode(canvas_to_bytes(canvas)).decode()
        payload = {
            "Command": "Draw/SendHttpGif",
            "PicNum": 1,
            "PicWidth": W,
            "PicOffset": 0,
            "PicID": pic_id,
            "PicSpeed": 1000,
            "PicData": b64,
        }
        return self._post(payload)

    def send_animation(
        self,
        frames: list[list[list[tuple]]],
        pic_id: int = 1,
        speed: int = 500,
    ) -> bool:
        """Send a multi-frame animation. Returns True when all frames succeed."""
        if not self._ip:
            return False
        self._ensure_custom_channel()
        # Reset GIF buffer before sending new animation so Pixoo doesn't
        # keep showing stale frames from the previous animation.
        self._post({"Command": "Draw/ResetHttpGifId"})
        total = len(frames)
        for i, canvas in enumerate(frames):
            b64 = base64.b64encode(canvas_to_bytes(canvas)).decode()
            payload = {
                "Command": "Draw/SendHttpGif",
                "PicNum": total,
                "PicWidth": W,
                "PicOffset": i,
                "PicID": pic_id,
                "PicSpeed": speed,
                "PicData": b64,
            }
            if not self._post(payload):
                return False
        return True

    # ── internal ──

    def _post(self, payload: dict) -> bool:
        try:
            req = urllib.request.Request(
                f"http://{self._ip}/post",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            resp = urllib.request.urlopen(req, timeout=10)
            result = json.loads(resp.read())
            if result.get("error_code", -1) != 0:
                logger.warning("Pixoo error: %s", result)
                return False
            return True
        except Exception:
            logger.exception("Failed to send to Pixoo at %s", self._ip)
            return False


# ── Sprite drawing: golden retriever moods ─────────────────────────────

def _draw_bg(canvas):
    """Fill entire canvas with BG colour (already done by make_canvas)."""
    pass  # canvas is pre-filled


def _draw_ground(canvas):
    """Simple ground line."""
    for x in range(W):
        set_pixel(canvas, x, 52, (45, 42, 35))
        _fill_rect(canvas, 0, 53, 63, 63, (35, 33, 28))


def _draw_chill(canvas):
    """Lying-down golden retriever, relaxed."""
    _draw_ground(canvas)

    # Body — long horizontal oval lying on ground
    _fill_rect(canvas, 18, 42, 46, 50, GOLDEN)
    _fill_rect(canvas, 19, 41, 45, 51, GOLDEN)
    # Darker underside
    _fill_rect(canvas, 20, 49, 44, 51, GOLDEN_DARK)

    # Head resting on paws — round blob to the right
    _fill_rect(canvas, 40, 37, 50, 46, GOLDEN)
    _fill_rect(canvas, 39, 38, 51, 45, GOLDEN)
    _fill_rect(canvas, 41, 36, 49, 37, GOLDEN_LIGHT)

    # Ear (drooping down right side)
    _fill_rect(canvas, 49, 38, 52, 44, GOLDEN_DARK)
    _fill_rect(canvas, 50, 37, 53, 43, GOLDEN_DARK)

    # Eye — relaxed (half-closed line)
    _hline(canvas, 44, 46, 40, EYE)
    set_pixel(canvas, 44, 39, EYE)

    # Nose
    _fill_rect(canvas, 50, 42, 52, 43, NOSE)

    # Front paws (stretched forward)
    _fill_rect(canvas, 46, 48, 50, 51, GOLDEN_LIGHT)
    _fill_rect(canvas, 51, 49, 53, 51, GOLDEN_LIGHT)

    # Tail — relaxed, lying flat behind body
    _fill_rect(canvas, 12, 43, 19, 45, GOLDEN_DARK)
    _fill_rect(canvas, 10, 44, 13, 46, GOLDEN_DARK)

    # Hind legs tucked
    _fill_rect(canvas, 20, 49, 24, 51, GOLDEN_LIGHT)


def _draw_happy(canvas):
    """Sitting up, tongue out, bright and cheerful."""
    _draw_ground(canvas)

    # Body — sitting upright, wider at bottom
    _fill_rect(canvas, 24, 35, 40, 51, GOLDEN)
    _fill_rect(canvas, 23, 38, 41, 49, GOLDEN)
    # Chest highlight
    _fill_rect(canvas, 28, 40, 36, 48, GOLDEN_LIGHT)

    # Head
    _fill_rect(canvas, 25, 22, 39, 34, GOLDEN)
    _fill_rect(canvas, 24, 24, 40, 32, GOLDEN)
    # Top of head lighter
    _fill_rect(canvas, 27, 22, 37, 25, GOLDEN_LIGHT)

    # Ears — floppy, hanging down on sides
    _fill_rect(canvas, 20, 25, 24, 33, GOLDEN_DARK)
    _fill_rect(canvas, 40, 25, 44, 33, GOLDEN_DARK)

    # Eyes — wide open, happy
    _fill_rect(canvas, 28, 27, 30, 29, EYE)
    _fill_rect(canvas, 34, 27, 36, 29, EYE)
    # Eye highlights
    set_pixel(canvas, 29, 27, (200, 200, 210))
    set_pixel(canvas, 35, 27, (200, 200, 210))

    # Nose
    _fill_rect(canvas, 30, 31, 34, 32, NOSE)

    # Mouth / tongue sticking out
    set_pixel(canvas, 31, 33, NOSE)
    set_pixel(canvas, 33, 33, NOSE)
    _fill_rect(canvas, 31, 34, 33, 37, TONGUE)
    _fill_rect(canvas, 30, 34, 34, 35, TONGUE)

    # Front paws
    _fill_rect(canvas, 24, 49, 28, 51, GOLDEN_LIGHT)
    _fill_rect(canvas, 36, 49, 40, 51, GOLDEN_LIGHT)

    # Tail — wagging up to the right
    _fill_rect(canvas, 40, 36, 42, 38, GOLDEN_DARK)
    _fill_rect(canvas, 42, 33, 44, 36, GOLDEN_DARK)
    _fill_rect(canvas, 44, 31, 46, 34, GOLDEN_DARK)


def _draw_sleepy(canvas):
    """Curled up, eyes closed — cozy and dozing."""
    _draw_ground(canvas)

    # Body — round curled-up blob
    _fill_rect(canvas, 20, 39, 44, 50, GOLDEN)
    _fill_rect(canvas, 22, 38, 42, 51, GOLDEN)
    _fill_rect(canvas, 18, 41, 46, 48, GOLDEN)

    # Darker inner curl
    _fill_rect(canvas, 24, 42, 38, 48, GOLDEN_DARK)

    # Head resting on body, tucked in
    _fill_rect(canvas, 36, 35, 47, 43, GOLDEN)
    _fill_rect(canvas, 38, 34, 46, 44, GOLDEN)

    # Ear draped over
    _fill_rect(canvas, 44, 35, 48, 41, GOLDEN_DARK)

    # Eyes — closed (simple lines)
    _hline(canvas, 40, 42, 38, EYE)
    _hline(canvas, 40, 42, 39, (80, 70, 60))  # softer shadow

    # Nose
    _fill_rect(canvas, 46, 40, 48, 41, NOSE)

    # Tail curled around body
    _fill_rect(canvas, 17, 42, 21, 44, GOLDEN_DARK)
    _fill_rect(canvas, 15, 40, 18, 43, GOLDEN_DARK)
    _fill_rect(canvas, 14, 38, 16, 41, GOLDEN_DARK)

    # Tiny Zzz
    set_pixel(canvas, 44, 31, (180, 180, 200))
    set_pixel(canvas, 45, 31, (180, 180, 200))
    set_pixel(canvas, 45, 30, (180, 180, 200))
    set_pixel(canvas, 46, 30, (180, 180, 200))
    set_pixel(canvas, 48, 28, (160, 160, 185))
    set_pixel(canvas, 49, 28, (160, 160, 185))
    set_pixel(canvas, 50, 28, (160, 160, 185))
    set_pixel(canvas, 50, 27, (160, 160, 185))
    set_pixel(canvas, 49, 27, (160, 160, 185))
    set_pixel(canvas, 48, 27, (160, 160, 185))


def _draw_curious(canvas):
    """Head tilted, one ear up — inquisitive look."""
    _draw_ground(canvas)

    # Body — standing / sitting, slight lean
    _fill_rect(canvas, 24, 35, 40, 51, GOLDEN)
    _fill_rect(canvas, 23, 38, 41, 49, GOLDEN)
    _fill_rect(canvas, 28, 40, 36, 48, GOLDEN_LIGHT)

    # Head — tilted slightly (offset)
    _fill_rect(canvas, 26, 20, 41, 33, GOLDEN)
    _fill_rect(canvas, 25, 22, 42, 31, GOLDEN)

    # One ear up (left ear perked), right ear normal
    _fill_rect(canvas, 22, 15, 26, 24, GOLDEN_DARK)
    _fill_rect(canvas, 23, 13, 25, 16, GOLDEN_DARK)
    # Right ear — floppy, hanging
    _fill_rect(canvas, 40, 23, 44, 32, GOLDEN_DARK)

    # Eyes — wide, curious, slightly asymmetric for tilt
    _fill_rect(canvas, 29, 25, 31, 27, EYE)
    _fill_rect(canvas, 36, 24, 38, 26, EYE)
    # Highlights
    set_pixel(canvas, 30, 25, (200, 200, 210))
    set_pixel(canvas, 37, 24, (200, 200, 210))

    # Nose
    _fill_rect(canvas, 32, 29, 35, 30, NOSE)

    # Small open mouth (curious panting)
    set_pixel(canvas, 33, 31, NOSE)
    set_pixel(canvas, 34, 31, NOSE)

    # Front paws
    _fill_rect(canvas, 24, 49, 28, 51, GOLDEN_LIGHT)
    _fill_rect(canvas, 36, 49, 40, 51, GOLDEN_LIGHT)

    # Tail — mid-height, slightly raised
    _fill_rect(canvas, 40, 38, 42, 40, GOLDEN_DARK)
    _fill_rect(canvas, 42, 36, 44, 39, GOLDEN_DARK)
    _fill_rect(canvas, 44, 35, 46, 37, GOLDEN_DARK)

    # Question mark above head
    set_pixel(canvas, 44, 12, (200, 200, 220))
    set_pixel(canvas, 45, 11, (200, 200, 220))
    set_pixel(canvas, 46, 11, (200, 200, 220))
    set_pixel(canvas, 47, 12, (200, 200, 220))
    set_pixel(canvas, 46, 13, (200, 200, 220))
    set_pixel(canvas, 45, 14, (200, 200, 220))
    set_pixel(canvas, 45, 16, (200, 200, 220))


def _draw_celebrate(canvas, tail_phase: int = 0):
    """Standing, tail wagging — tail_phase 0/1/2 for animation."""
    _draw_ground(canvas)

    # Body — standing upright, proud
    _fill_rect(canvas, 22, 30, 38, 47, GOLDEN)
    _fill_rect(canvas, 21, 33, 39, 45, GOLDEN)
    _fill_rect(canvas, 26, 35, 34, 44, GOLDEN_LIGHT)

    # Head — held high
    _fill_rect(canvas, 23, 16, 37, 29, GOLDEN)
    _fill_rect(canvas, 22, 18, 38, 27, GOLDEN)
    _fill_rect(canvas, 25, 15, 35, 18, GOLDEN_LIGHT)

    # Ears — perky, slightly up
    _fill_rect(canvas, 19, 18, 23, 27, GOLDEN_DARK)
    _fill_rect(canvas, 37, 18, 41, 27, GOLDEN_DARK)

    # Eyes — bright, wide open
    _fill_rect(canvas, 26, 21, 28, 23, EYE)
    _fill_rect(canvas, 32, 21, 34, 23, EYE)
    set_pixel(canvas, 27, 21, (220, 220, 230))
    set_pixel(canvas, 33, 21, (220, 220, 230))

    # Nose
    _fill_rect(canvas, 28, 25, 32, 26, NOSE)

    # Big happy open mouth
    set_pixel(canvas, 29, 27, NOSE)
    set_pixel(canvas, 31, 27, NOSE)
    _fill_rect(canvas, 29, 28, 31, 30, TONGUE)

    # Legs — standing
    _fill_rect(canvas, 22, 47, 26, 51, GOLDEN_LIGHT)
    _fill_rect(canvas, 34, 47, 38, 51, GOLDEN_LIGHT)

    # Tail — animated wagging (3 positions)
    if tail_phase == 0:
        # Tail up-right
        _fill_rect(canvas, 38, 32, 40, 34, GOLDEN_DARK)
        _fill_rect(canvas, 40, 29, 42, 32, GOLDEN_DARK)
        _fill_rect(canvas, 42, 26, 44, 30, GOLDEN_DARK)
        _fill_rect(canvas, 44, 24, 46, 27, GOLDEN_DARK)
    elif tail_phase == 1:
        # Tail straight up
        _fill_rect(canvas, 38, 31, 40, 33, GOLDEN_DARK)
        _fill_rect(canvas, 39, 27, 41, 31, GOLDEN_DARK)
        _fill_rect(canvas, 40, 23, 42, 28, GOLDEN_DARK)
        _fill_rect(canvas, 41, 20, 43, 24, GOLDEN_DARK)
    else:
        # Tail up-left (wagging back)
        _fill_rect(canvas, 38, 32, 40, 34, GOLDEN_DARK)
        _fill_rect(canvas, 40, 29, 42, 32, GOLDEN_DARK)
        _fill_rect(canvas, 41, 27, 43, 30, GOLDEN_DARK)
        _fill_rect(canvas, 40, 25, 42, 28, GOLDEN_DARK)

    # Sparkles around (celebration)
    sparkle = (255, 230, 100)
    sparkle_positions = [
        (12, 14), (50, 10), (8, 28), (54, 24),
        (14, 8), (48, 16), (10, 38), (52, 36),
    ]
    for sx, sy in sparkle_positions:
        set_pixel(canvas, sx, sy, sparkle)
        set_pixel(canvas, sx + 1, sy, sparkle)
        set_pixel(canvas, sx, sy + 1, sparkle)


def _draw_happy_anim(canvas, tail_phase: int = 0):
    """Happy with animated tail wagging — tail_phase 0/1/2."""
    _draw_ground(canvas)

    # Body — sitting upright
    _fill_rect(canvas, 24, 35, 40, 51, GOLDEN)
    _fill_rect(canvas, 23, 38, 41, 49, GOLDEN)
    _fill_rect(canvas, 28, 40, 36, 48, GOLDEN_LIGHT)

    # Head
    _fill_rect(canvas, 25, 22, 39, 34, GOLDEN)
    _fill_rect(canvas, 24, 24, 40, 32, GOLDEN)
    _fill_rect(canvas, 27, 22, 37, 25, GOLDEN_LIGHT)

    # Ears
    _fill_rect(canvas, 20, 25, 24, 33, GOLDEN_DARK)
    _fill_rect(canvas, 40, 25, 44, 33, GOLDEN_DARK)

    # Eyes
    _fill_rect(canvas, 28, 27, 30, 29, EYE)
    _fill_rect(canvas, 34, 27, 36, 29, EYE)
    set_pixel(canvas, 29, 27, (200, 200, 210))
    set_pixel(canvas, 35, 27, (200, 200, 210))

    # Nose
    _fill_rect(canvas, 30, 31, 34, 32, NOSE)

    # Tongue
    set_pixel(canvas, 31, 33, NOSE)
    set_pixel(canvas, 33, 33, NOSE)
    _fill_rect(canvas, 31, 34, 33, 37, TONGUE)
    _fill_rect(canvas, 30, 34, 34, 35, TONGUE)

    # Front paws
    _fill_rect(canvas, 24, 49, 28, 51, GOLDEN_LIGHT)
    _fill_rect(canvas, 36, 49, 40, 51, GOLDEN_LIGHT)

    # Tail — animated wagging
    if tail_phase == 0:
        _fill_rect(canvas, 40, 36, 42, 38, GOLDEN_DARK)
        _fill_rect(canvas, 42, 33, 44, 36, GOLDEN_DARK)
        _fill_rect(canvas, 44, 31, 46, 34, GOLDEN_DARK)
    elif tail_phase == 1:
        _fill_rect(canvas, 40, 35, 42, 37, GOLDEN_DARK)
        _fill_rect(canvas, 42, 32, 44, 35, GOLDEN_DARK)
        _fill_rect(canvas, 43, 29, 45, 33, GOLDEN_DARK)
    else:
        _fill_rect(canvas, 40, 36, 42, 38, GOLDEN_DARK)
        _fill_rect(canvas, 42, 34, 44, 37, GOLDEN_DARK)
        _fill_rect(canvas, 43, 36, 45, 38, GOLDEN_DARK)


def _draw_music(canvas, phase: int = 0):
    """Listening to music — head bobbing side to side, music notes floating.

    phase 0: head center, phase 1: head tilted left, phase 2: head tilted right.
    """
    _draw_ground(canvas)

    # Body — sitting
    _fill_rect(canvas, 24, 35, 40, 51, GOLDEN)
    _fill_rect(canvas, 23, 38, 41, 49, GOLDEN)
    _fill_rect(canvas, 28, 40, 36, 48, GOLDEN_LIGHT)

    # Head position shifts per phase
    hx = 0  # head x offset
    if phase == 1:
        hx = -2
    elif phase == 2:
        hx = 2

    # Head
    _fill_rect(canvas, 25 + hx, 22, 39 + hx, 34, GOLDEN)
    _fill_rect(canvas, 24 + hx, 24, 40 + hx, 32, GOLDEN)
    _fill_rect(canvas, 27 + hx, 22, 37 + hx, 25, GOLDEN_LIGHT)

    # Ears
    _fill_rect(canvas, 20 + hx, 25, 24 + hx, 33, GOLDEN_DARK)
    _fill_rect(canvas, 40 + hx, 25, 44 + hx, 33, GOLDEN_DARK)

    # Eyes — happy closed (enjoying music)
    _hline(canvas, 28 + hx, 30 + hx, 28, EYE)
    set_pixel(canvas, 28 + hx, 27, EYE)
    set_pixel(canvas, 30 + hx, 27, EYE)
    _hline(canvas, 34 + hx, 36 + hx, 28, EYE)
    set_pixel(canvas, 34 + hx, 27, EYE)
    set_pixel(canvas, 36 + hx, 27, EYE)

    # Nose
    _fill_rect(canvas, 30 + hx, 31, 34 + hx, 32, NOSE)

    # Small smile
    set_pixel(canvas, 30 + hx, 33, NOSE)
    set_pixel(canvas, 34 + hx, 33, NOSE)

    # Front paws
    _fill_rect(canvas, 24, 49, 28, 51, GOLDEN_LIGHT)
    _fill_rect(canvas, 36, 49, 40, 51, GOLDEN_LIGHT)

    # Tail — gently raised
    _fill_rect(canvas, 40, 37, 42, 39, GOLDEN_DARK)
    _fill_rect(canvas, 42, 34, 44, 37, GOLDEN_DARK)
    _fill_rect(canvas, 44, 32, 46, 35, GOLDEN_DARK)

    # Floating music notes — different positions per phase
    note_color = (180, 160, 255)
    note_color2 = (255, 200, 120)
    if phase == 0:
        # ♪ top right
        set_pixel(canvas, 50, 14, note_color)
        set_pixel(canvas, 50, 15, note_color)
        set_pixel(canvas, 50, 16, note_color)
        set_pixel(canvas, 49, 16, note_color)
        set_pixel(canvas, 48, 16, note_color)
        set_pixel(canvas, 50, 14, note_color)
        set_pixel(canvas, 51, 13, note_color)
        # ♪ top left
        set_pixel(canvas, 14, 18, note_color2)
        set_pixel(canvas, 14, 19, note_color2)
        set_pixel(canvas, 14, 20, note_color2)
        set_pixel(canvas, 13, 20, note_color2)
        set_pixel(canvas, 14, 18, note_color2)
        set_pixel(canvas, 15, 17, note_color2)
    elif phase == 1:
        # Notes float up
        set_pixel(canvas, 50, 12, note_color)
        set_pixel(canvas, 50, 13, note_color)
        set_pixel(canvas, 50, 14, note_color)
        set_pixel(canvas, 49, 14, note_color)
        set_pixel(canvas, 48, 14, note_color)
        set_pixel(canvas, 51, 11, note_color)
        set_pixel(canvas, 12, 16, note_color2)
        set_pixel(canvas, 12, 17, note_color2)
        set_pixel(canvas, 12, 18, note_color2)
        set_pixel(canvas, 11, 18, note_color2)
        set_pixel(canvas, 13, 15, note_color2)
    else:
        # Notes at different spot
        set_pixel(canvas, 52, 16, note_color)
        set_pixel(canvas, 52, 17, note_color)
        set_pixel(canvas, 52, 18, note_color)
        set_pixel(canvas, 51, 18, note_color)
        set_pixel(canvas, 53, 15, note_color)
        set_pixel(canvas, 16, 14, note_color2)
        set_pixel(canvas, 16, 15, note_color2)
        set_pixel(canvas, 16, 16, note_color2)
        set_pixel(canvas, 15, 16, note_color2)
        set_pixel(canvas, 17, 13, note_color2)


def _draw_chill_anim(canvas, phase: int = 0):
    """Chill with gentle breathing — body rises/falls slightly."""
    _draw_ground(canvas)

    # Breathing offset: phase 0 = normal, phase 1 = inhale (up 1px)
    by = -1 if phase == 1 else 0

    # Body
    _fill_rect(canvas, 18, 42 + by, 46, 50, GOLDEN)
    _fill_rect(canvas, 19, 41 + by, 45, 51, GOLDEN)
    _fill_rect(canvas, 20, 49, 44, 51, GOLDEN_DARK)

    # Head resting on paws
    _fill_rect(canvas, 40, 37 + by, 50, 46 + by, GOLDEN)
    _fill_rect(canvas, 39, 38 + by, 51, 45 + by, GOLDEN)
    _fill_rect(canvas, 41, 36 + by, 49, 37 + by, GOLDEN_LIGHT)

    # Ear
    _fill_rect(canvas, 49, 38 + by, 52, 44 + by, GOLDEN_DARK)
    _fill_rect(canvas, 50, 37 + by, 53, 43 + by, GOLDEN_DARK)

    # Eye — relaxed
    _hline(canvas, 44, 46, 40 + by, EYE)
    set_pixel(canvas, 44, 39 + by, EYE)

    # Nose
    _fill_rect(canvas, 50, 42 + by, 52, 43 + by, NOSE)

    # Front paws
    _fill_rect(canvas, 46, 48, 50, 51, GOLDEN_LIGHT)
    _fill_rect(canvas, 51, 49, 53, 51, GOLDEN_LIGHT)

    # Tail
    _fill_rect(canvas, 12, 43, 19, 45, GOLDEN_DARK)
    _fill_rect(canvas, 10, 44, 13, 46, GOLDEN_DARK)

    # Hind legs
    _fill_rect(canvas, 20, 49, 24, 51, GOLDEN_LIGHT)


def _draw_sleepy_anim(canvas, phase: int = 0):
    """Sleeping with Zzz floating upward — phase 0/1/2."""
    _draw_ground(canvas)

    # Body — round curled-up blob
    _fill_rect(canvas, 20, 39, 44, 50, GOLDEN)
    _fill_rect(canvas, 22, 38, 42, 51, GOLDEN)
    _fill_rect(canvas, 18, 41, 46, 48, GOLDEN)
    _fill_rect(canvas, 24, 42, 38, 48, GOLDEN_DARK)

    # Head resting on body
    _fill_rect(canvas, 36, 35, 47, 43, GOLDEN)
    _fill_rect(canvas, 38, 34, 46, 44, GOLDEN)

    # Ear draped over
    _fill_rect(canvas, 44, 35, 48, 41, GOLDEN_DARK)

    # Eyes — closed
    _hline(canvas, 40, 42, 38, EYE)
    _hline(canvas, 40, 42, 39, (80, 70, 60))

    # Nose
    _fill_rect(canvas, 46, 40, 48, 41, NOSE)

    # Tail curled around body
    _fill_rect(canvas, 17, 42, 21, 44, GOLDEN_DARK)
    _fill_rect(canvas, 15, 40, 18, 43, GOLDEN_DARK)
    _fill_rect(canvas, 14, 38, 16, 41, GOLDEN_DARK)

    # Animated Zzz — float upward across phases
    z_color_1 = (180, 180, 200)
    z_color_2 = (160, 160, 185)
    z_color_3 = (140, 140, 170)

    if phase == 0:
        # Small z close to head
        _draw_z(canvas, 46, 30, z_color_1, size=2)
    elif phase == 1:
        # Small z moved up, medium z appears
        _draw_z(canvas, 47, 26, z_color_2, size=2)
        _draw_z(canvas, 50, 32, z_color_1, size=2)
    else:
        # All three z's floating
        _draw_z(canvas, 48, 22, z_color_3, size=3)
        _draw_z(canvas, 51, 28, z_color_2, size=2)
        _draw_z(canvas, 46, 32, z_color_1, size=2)


def _draw_z(canvas, x, y, color, size=2):
    """Draw a tiny Z character at (x, y)."""
    if size == 3:
        _hline(canvas, x, x + 3, y, color)
        set_pixel(canvas, x + 2, y + 1, color)
        set_pixel(canvas, x + 1, y + 2, color)
        _hline(canvas, x, x + 3, y + 3, color)
    else:
        _hline(canvas, x, x + 2, y, color)
        set_pixel(canvas, x + 1, y + 1, color)
        _hline(canvas, x, x + 2, y + 2, color)


def _draw_curious_anim(canvas, phase: int = 0):
    """Head tilting side to side with blinking question mark — phase 0/1/2."""
    _draw_ground(canvas)

    # Body
    _fill_rect(canvas, 24, 35, 40, 51, GOLDEN)
    _fill_rect(canvas, 23, 38, 41, 49, GOLDEN)
    _fill_rect(canvas, 28, 40, 36, 48, GOLDEN_LIGHT)

    # Head tilt per phase
    tilt = 0
    if phase == 1:
        tilt = -1
    elif phase == 2:
        tilt = 1

    # Head — tilted
    _fill_rect(canvas, 26, 20 + tilt, 41, 33 + tilt, GOLDEN)
    _fill_rect(canvas, 25, 22 + tilt, 42, 31 + tilt, GOLDEN)

    # Left ear perked
    _fill_rect(canvas, 22, 15 + tilt, 26, 24 + tilt, GOLDEN_DARK)
    _fill_rect(canvas, 23, 13 + tilt, 25, 16 + tilt, GOLDEN_DARK)
    # Right ear floppy
    _fill_rect(canvas, 40, 23 + tilt, 44, 32 + tilt, GOLDEN_DARK)

    # Eyes
    _fill_rect(canvas, 29, 25 + tilt, 31, 27 + tilt, EYE)
    _fill_rect(canvas, 36, 24 + tilt, 38, 26 + tilt, EYE)
    set_pixel(canvas, 30, 25 + tilt, (200, 200, 210))
    set_pixel(canvas, 37, 24 + tilt, (200, 200, 210))

    # Nose
    _fill_rect(canvas, 32, 29 + tilt, 35, 30 + tilt, NOSE)

    # Mouth
    set_pixel(canvas, 33, 31 + tilt, NOSE)
    set_pixel(canvas, 34, 31 + tilt, NOSE)

    # Front paws
    _fill_rect(canvas, 24, 49, 28, 51, GOLDEN_LIGHT)
    _fill_rect(canvas, 36, 49, 40, 51, GOLDEN_LIGHT)

    # Tail
    _fill_rect(canvas, 40, 38, 42, 40, GOLDEN_DARK)
    _fill_rect(canvas, 42, 36, 44, 39, GOLDEN_DARK)
    _fill_rect(canvas, 44, 35, 46, 37, GOLDEN_DARK)

    # Question mark — blinks on phase 0 and 2, off on phase 1
    if phase != 1:
        qm = (200, 200, 220)
        set_pixel(canvas, 44, 12, qm)
        set_pixel(canvas, 45, 11, qm)
        set_pixel(canvas, 46, 11, qm)
        set_pixel(canvas, 47, 12, qm)
        set_pixel(canvas, 46, 13, qm)
        set_pixel(canvas, 45, 14, qm)
        set_pixel(canvas, 45, 16, qm)


def _draw_playing(canvas, phase: int = 0):
    """Chasing a ball! Bouncing up and down — phase 0/1/2."""
    _draw_ground(canvas)

    # Bounce offset
    by = 0
    if phase == 1:
        by = -3
    elif phase == 2:
        by = -1

    # Body — running pose, stretched
    _fill_rect(canvas, 18, 36 + by, 38, 48 + by, GOLDEN)
    _fill_rect(canvas, 17, 39 + by, 39, 46 + by, GOLDEN)
    _fill_rect(canvas, 22, 40 + by, 34, 45 + by, GOLDEN_LIGHT)

    # Head — forward, eager
    _fill_rect(canvas, 35, 28 + by, 47, 40 + by, GOLDEN)
    _fill_rect(canvas, 34, 30 + by, 48, 38 + by, GOLDEN)
    _fill_rect(canvas, 37, 27 + by, 45, 30 + by, GOLDEN_LIGHT)

    # Ears — flying back
    _fill_rect(canvas, 32, 29 + by, 36, 34 + by, GOLDEN_DARK)
    _fill_rect(canvas, 30, 30 + by, 33, 32 + by, GOLDEN_DARK)

    # Eyes — excited
    _fill_rect(canvas, 39, 32 + by, 41, 34 + by, EYE)
    _fill_rect(canvas, 44, 32 + by, 46, 34 + by, EYE)
    set_pixel(canvas, 40, 32 + by, (220, 220, 230))
    set_pixel(canvas, 45, 32 + by, (220, 220, 230))

    # Nose
    _fill_rect(canvas, 47, 35 + by, 49, 36 + by, NOSE)

    # Tongue flapping
    if phase == 1:
        _fill_rect(canvas, 47, 37 + by, 49, 40 + by, TONGUE)
    else:
        _fill_rect(canvas, 47, 37 + by, 48, 39 + by, TONGUE)

    # Legs — running animation
    if phase == 0:
        # Front legs forward, back legs back
        _fill_rect(canvas, 34, 46 + by, 37, 51, GOLDEN_LIGHT)
        _fill_rect(canvas, 38, 48 + by, 41, 51, GOLDEN_LIGHT)
        _fill_rect(canvas, 18, 46 + by, 21, 51, GOLDEN_LIGHT)
        _fill_rect(canvas, 23, 48 + by, 26, 51, GOLDEN_LIGHT)
    elif phase == 1:
        # Legs tucked (in air)
        _fill_rect(canvas, 32, 46 + by, 35, 49 + by, GOLDEN_LIGHT)
        _fill_rect(canvas, 22, 46 + by, 25, 49 + by, GOLDEN_LIGHT)
    else:
        # Opposite leg positions
        _fill_rect(canvas, 34, 48 + by, 37, 51, GOLDEN_LIGHT)
        _fill_rect(canvas, 38, 46 + by, 41, 51, GOLDEN_LIGHT)
        _fill_rect(canvas, 18, 48 + by, 21, 51, GOLDEN_LIGHT)
        _fill_rect(canvas, 23, 46 + by, 26, 51, GOLDEN_LIGHT)

    # Tail — high and wagging
    _fill_rect(canvas, 14, 34 + by, 17, 36 + by, GOLDEN_DARK)
    _fill_rect(canvas, 12, 31 + by, 15, 34 + by, GOLDEN_DARK)
    if phase == 1:
        _fill_rect(canvas, 10, 29 + by, 13, 32 + by, GOLDEN_DARK)
    else:
        _fill_rect(canvas, 11, 30 + by, 14, 33 + by, GOLDEN_DARK)

    # Ball!
    ball_color = (230, 80, 80)
    ball_highlight = (255, 140, 140)
    bx = 52
    ball_by = -2 if phase == 1 else 0
    _fill_rect(canvas, bx, 44 + ball_by, bx + 4, 48 + ball_by, ball_color)
    _fill_rect(canvas, bx + 1, 43 + ball_by, bx + 3, 49 + ball_by, ball_color)
    set_pixel(canvas, bx + 1, 44 + ball_by, ball_highlight)
    set_pixel(canvas, bx + 2, 44 + ball_by, ball_highlight)


def _draw_stretching(canvas, phase: int = 0):
    """Stretching / play bow — front down, butt up, then yawn. Phase 0/1/2."""
    _draw_ground(canvas)

    if phase == 0:
        # Starting to stretch — normal standing
        _fill_rect(canvas, 20, 34, 44, 48, GOLDEN)
        _fill_rect(canvas, 19, 37, 45, 46, GOLDEN)
        _fill_rect(canvas, 24, 38, 40, 44, GOLDEN_LIGHT)

        # Head — normal height
        _fill_rect(canvas, 38, 22, 50, 34, GOLDEN)
        _fill_rect(canvas, 37, 24, 51, 32, GOLDEN)
        _fill_rect(canvas, 40, 21, 48, 24, GOLDEN_LIGHT)

        # Ears
        _fill_rect(canvas, 34, 24, 38, 31, GOLDEN_DARK)
        _fill_rect(canvas, 50, 24, 54, 31, GOLDEN_DARK)

        # Eyes — sleepy, about to yawn
        _hline(canvas, 41, 43, 27, EYE)
        _hline(canvas, 46, 48, 27, EYE)

        # Nose
        _fill_rect(canvas, 43, 30, 46, 31, NOSE)

        # Legs
        _fill_rect(canvas, 38, 46, 42, 51, GOLDEN_LIGHT)
        _fill_rect(canvas, 22, 46, 26, 51, GOLDEN_LIGHT)

        # Tail — low
        _fill_rect(canvas, 16, 36, 21, 38, GOLDEN_DARK)

    elif phase == 1:
        # Play bow — front paws forward, chest down, butt up
        # Back body — high
        _fill_rect(canvas, 16, 30, 30, 44, GOLDEN)
        _fill_rect(canvas, 15, 33, 31, 42, GOLDEN)
        # Front body — low, stretched forward
        _fill_rect(canvas, 28, 40, 46, 50, GOLDEN)
        _fill_rect(canvas, 30, 38, 44, 51, GOLDEN)
        _fill_rect(canvas, 32, 42, 42, 48, GOLDEN_LIGHT)

        # Head — down low, mouth open (yawning)
        _fill_rect(canvas, 40, 36, 52, 46, GOLDEN)
        _fill_rect(canvas, 39, 38, 53, 44, GOLDEN)

        # Ears flopping
        _fill_rect(canvas, 36, 37, 40, 43, GOLDEN_DARK)
        _fill_rect(canvas, 52, 37, 56, 43, GOLDEN_DARK)

        # Eyes — squeezed shut (big yawn)
        _hline(canvas, 43, 45, 39, EYE)
        set_pixel(canvas, 42, 38, EYE)
        set_pixel(canvas, 46, 38, EYE)
        _hline(canvas, 48, 50, 39, EYE)
        set_pixel(canvas, 47, 38, EYE)
        set_pixel(canvas, 51, 38, EYE)

        # Nose
        _fill_rect(canvas, 46, 41, 48, 42, NOSE)

        # Big yawn mouth
        _fill_rect(canvas, 44, 43, 50, 46, TONGUE)
        _fill_rect(canvas, 43, 44, 51, 45, TONGUE)
        set_pixel(canvas, 44, 43, NOSE)
        set_pixel(canvas, 50, 43, NOSE)

        # Back legs — standing
        _fill_rect(canvas, 17, 43, 21, 51, GOLDEN_LIGHT)
        _fill_rect(canvas, 25, 43, 29, 51, GOLDEN_LIGHT)
        # Front paws — stretched forward
        _fill_rect(canvas, 38, 48, 42, 51, GOLDEN_LIGHT)
        _fill_rect(canvas, 44, 49, 47, 51, GOLDEN_LIGHT)

        # Tail — high up!
        _fill_rect(canvas, 13, 30, 16, 32, GOLDEN_DARK)
        _fill_rect(canvas, 11, 27, 14, 30, GOLDEN_DARK)
        _fill_rect(canvas, 10, 24, 13, 28, GOLDEN_DARK)

    else:
        # Coming back up — shake it off
        _fill_rect(canvas, 20, 34, 44, 48, GOLDEN)
        _fill_rect(canvas, 19, 37, 45, 46, GOLDEN)
        _fill_rect(canvas, 24, 38, 40, 44, GOLDEN_LIGHT)

        # Head — shaking (offset right)
        _fill_rect(canvas, 40, 22, 52, 34, GOLDEN)
        _fill_rect(canvas, 39, 24, 53, 32, GOLDEN)

        # Ears — flying out from shake
        _fill_rect(canvas, 35, 23, 40, 28, GOLDEN_DARK)
        _fill_rect(canvas, 52, 23, 57, 28, GOLDEN_DARK)

        # Eyes — refreshed, wide open
        _fill_rect(canvas, 43, 26, 45, 28, EYE)
        _fill_rect(canvas, 48, 26, 50, 28, EYE)
        set_pixel(canvas, 44, 26, (200, 200, 210))
        set_pixel(canvas, 49, 26, (200, 200, 210))

        # Nose
        _fill_rect(canvas, 46, 30, 49, 31, NOSE)

        # Happy mouth after stretch
        set_pixel(canvas, 46, 32, NOSE)
        set_pixel(canvas, 49, 32, NOSE)
        _fill_rect(canvas, 46, 33, 49, 34, TONGUE)

        # Legs
        _fill_rect(canvas, 38, 46, 42, 51, GOLDEN_LIGHT)
        _fill_rect(canvas, 22, 46, 26, 51, GOLDEN_LIGHT)

        # Tail — wagging
        _fill_rect(canvas, 16, 33, 20, 35, GOLDEN_DARK)
        _fill_rect(canvas, 14, 30, 17, 33, GOLDEN_DARK)

        # Shake lines
        shake = (200, 200, 220)
        set_pixel(canvas, 55, 24, shake)
        set_pixel(canvas, 56, 25, shake)
        set_pixel(canvas, 57, 24, shake)
        set_pixel(canvas, 34, 22, shake)
        set_pixel(canvas, 33, 23, shake)
        set_pixel(canvas, 34, 24, shake)


def _draw_downdog(canvas, phase: int = 0):
    """Downward dog — front paws forward, butt way up, tail wagging! Phase 0/1/2."""
    _draw_ground(canvas)

    if phase == 0:
        # Getting into position — starting to bow down
        # Back body — rising
        _fill_rect(canvas, 16, 32, 30, 46, GOLDEN)
        _fill_rect(canvas, 15, 35, 31, 44, GOLDEN)
        _fill_rect(canvas, 20, 36, 28, 42, GOLDEN_LIGHT)

        # Front body — lowering
        _fill_rect(canvas, 28, 38, 46, 50, GOLDEN)
        _fill_rect(canvas, 30, 36, 44, 48, GOLDEN)

        # Head — going down
        _fill_rect(canvas, 40, 34, 52, 44, GOLDEN)
        _fill_rect(canvas, 39, 36, 53, 42, GOLDEN)

        # Ears
        _fill_rect(canvas, 36, 35, 40, 41, GOLDEN_DARK)
        _fill_rect(canvas, 52, 35, 56, 41, GOLDEN_DARK)

        # Eyes — focused, determined
        _fill_rect(canvas, 43, 37, 45, 39, EYE)
        _fill_rect(canvas, 48, 37, 50, 39, EYE)

        # Nose
        _fill_rect(canvas, 46, 41, 48, 42, NOSE)

        # Back legs
        _fill_rect(canvas, 17, 44, 21, 51, GOLDEN_LIGHT)
        _fill_rect(canvas, 25, 44, 29, 51, GOLDEN_LIGHT)
        # Front legs — stepping forward
        _fill_rect(canvas, 40, 46, 44, 51, GOLDEN_LIGHT)
        _fill_rect(canvas, 46, 47, 49, 51, GOLDEN_LIGHT)

        # Tail — starting to rise
        _fill_rect(canvas, 13, 32, 16, 34, GOLDEN_DARK)
        _fill_rect(canvas, 11, 29, 14, 32, GOLDEN_DARK)

    elif phase == 1:
        # Full downward dog!! Front paws way forward, chest low, butt HIGH
        # Back body — butt way up
        _fill_rect(canvas, 14, 24, 26, 38, GOLDEN)
        _fill_rect(canvas, 13, 27, 27, 36, GOLDEN)
        _fill_rect(canvas, 18, 28, 24, 34, GOLDEN_LIGHT)

        # Slope from butt down to chest
        _fill_rect(canvas, 24, 34, 36, 44, GOLDEN)
        _fill_rect(canvas, 26, 32, 34, 42, GOLDEN)

        # Front body — low to ground
        _fill_rect(canvas, 34, 42, 48, 50, GOLDEN)
        _fill_rect(canvas, 36, 40, 46, 48, GOLDEN)

        # Head — between front paws, looking forward, happy!
        _fill_rect(canvas, 42, 36, 54, 46, GOLDEN)
        _fill_rect(canvas, 41, 38, 55, 44, GOLDEN)

        # Ears — flopping down
        _fill_rect(canvas, 38, 38, 42, 44, GOLDEN_DARK)
        _fill_rect(canvas, 54, 38, 58, 44, GOLDEN_DARK)

        # Eyes — happy squinty
        _hline(canvas, 45, 47, 40, EYE)
        set_pixel(canvas, 44, 39, EYE)
        set_pixel(canvas, 48, 39, EYE)
        _hline(canvas, 50, 52, 40, EYE)
        set_pixel(canvas, 49, 39, EYE)
        set_pixel(canvas, 53, 39, EYE)

        # Nose
        _fill_rect(canvas, 48, 42, 50, 43, NOSE)

        # Little smile
        set_pixel(canvas, 48, 44, NOSE)
        set_pixel(canvas, 51, 44, NOSE)
        _fill_rect(canvas, 48, 45, 51, 45, TONGUE)

        # Back legs — straight, pushing butt up
        _fill_rect(canvas, 15, 36, 19, 51, GOLDEN_LIGHT)
        _fill_rect(canvas, 23, 36, 27, 51, GOLDEN_LIGHT)
        # Front paws — stretched way forward, flat on ground
        _fill_rect(canvas, 38, 48, 42, 51, GOLDEN_LIGHT)
        _fill_rect(canvas, 44, 49, 48, 51, GOLDEN_LIGHT)

        # Tail — way up high, wagging left!
        _fill_rect(canvas, 11, 24, 14, 26, GOLDEN_DARK)
        _fill_rect(canvas, 9, 20, 12, 24, GOLDEN_DARK)
        _fill_rect(canvas, 7, 17, 10, 21, GOLDEN_DARK)

    else:
        # Still in downward dog, tail wagging the other way!
        # Back body — butt way up (same pose)
        _fill_rect(canvas, 14, 24, 26, 38, GOLDEN)
        _fill_rect(canvas, 13, 27, 27, 36, GOLDEN)
        _fill_rect(canvas, 18, 28, 24, 34, GOLDEN_LIGHT)

        # Slope
        _fill_rect(canvas, 24, 34, 36, 44, GOLDEN)
        _fill_rect(canvas, 26, 32, 34, 42, GOLDEN)

        # Front body — low
        _fill_rect(canvas, 34, 42, 48, 50, GOLDEN)
        _fill_rect(canvas, 36, 40, 46, 48, GOLDEN)

        # Head — looking up a tiny bit (checking if human is watching)
        _fill_rect(canvas, 42, 34, 54, 44, GOLDEN)
        _fill_rect(canvas, 41, 36, 55, 42, GOLDEN)

        # Ears — perked up a bit
        _fill_rect(canvas, 38, 34, 42, 40, GOLDEN_DARK)
        _fill_rect(canvas, 54, 34, 58, 40, GOLDEN_DARK)

        # Eyes — wide open looking at you!
        _fill_rect(canvas, 45, 36, 47, 38, EYE)
        _fill_rect(canvas, 50, 36, 52, 38, EYE)
        set_pixel(canvas, 46, 36, (200, 200, 210))
        set_pixel(canvas, 51, 36, (200, 200, 210))

        # Nose
        _fill_rect(canvas, 48, 40, 50, 41, NOSE)

        # Tongue out!
        _fill_rect(canvas, 48, 42, 51, 44, TONGUE)

        # Back legs — same
        _fill_rect(canvas, 15, 36, 19, 51, GOLDEN_LIGHT)
        _fill_rect(canvas, 23, 36, 27, 51, GOLDEN_LIGHT)
        # Front paws
        _fill_rect(canvas, 38, 48, 42, 51, GOLDEN_LIGHT)
        _fill_rect(canvas, 44, 49, 48, 51, GOLDEN_LIGHT)

        # Tail — way up high, wagging RIGHT!
        _fill_rect(canvas, 11, 24, 14, 26, GOLDEN_DARK)
        _fill_rect(canvas, 9, 20, 12, 24, GOLDEN_DARK)
        _fill_rect(canvas, 12, 17, 15, 21, GOLDEN_DARK)

        # Happy sparkles — yoga feels good!
        sparkle = (255, 255, 200)
        set_pixel(canvas, 5, 15, sparkle)
        set_pixel(canvas, 58, 30, sparkle)
        set_pixel(canvas, 3, 25, sparkle)


def _draw_walking(canvas, phase: int = 0):
    """Walking / trotting — legs alternate. Phase 0/1/2/3."""
    _draw_ground(canvas)

    # Body — horizontal, walking pose
    _fill_rect(canvas, 18, 34, 42, 46, GOLDEN)
    _fill_rect(canvas, 17, 37, 43, 44, GOLDEN)
    _fill_rect(canvas, 22, 38, 38, 43, GOLDEN_LIGHT)

    # Head — forward
    _fill_rect(canvas, 38, 22, 50, 34, GOLDEN)
    _fill_rect(canvas, 37, 24, 51, 32, GOLDEN)
    _fill_rect(canvas, 40, 21, 48, 24, GOLDEN_LIGHT)

    # Ears — gentle bounce
    ear_y = 0 if phase % 2 == 0 else 1
    _fill_rect(canvas, 35, 24 + ear_y, 39, 31 + ear_y, GOLDEN_DARK)
    _fill_rect(canvas, 50, 24 + ear_y, 54, 31 + ear_y, GOLDEN_DARK)

    # Eyes — relaxed happy
    _fill_rect(canvas, 41, 26, 43, 28, EYE)
    _fill_rect(canvas, 46, 26, 48, 28, EYE)
    set_pixel(canvas, 42, 26, (200, 200, 210))
    set_pixel(canvas, 47, 26, (200, 200, 210))

    # Nose
    _fill_rect(canvas, 49, 29, 51, 30, NOSE)

    # Tongue — bouncing slightly
    if phase % 2 == 0:
        _fill_rect(canvas, 49, 31, 50, 33, TONGUE)
    else:
        _fill_rect(canvas, 49, 31, 50, 34, TONGUE)

    # Legs — four-beat walk cycle
    if phase == 0:
        # Right front forward, left back forward
        _fill_rect(canvas, 38, 44, 41, 51, GOLDEN_LIGHT)
        _fill_rect(canvas, 34, 46, 37, 51, GOLDEN_LIGHT)
        _fill_rect(canvas, 20, 44, 23, 51, GOLDEN_LIGHT)
        _fill_rect(canvas, 24, 46, 27, 51, GOLDEN_LIGHT)
    elif phase == 1:
        # Both sides mid
        _fill_rect(canvas, 36, 45, 39, 51, GOLDEN_LIGHT)
        _fill_rect(canvas, 40, 45, 43, 51, GOLDEN_LIGHT)
        _fill_rect(canvas, 20, 45, 23, 51, GOLDEN_LIGHT)
        _fill_rect(canvas, 24, 45, 27, 51, GOLDEN_LIGHT)
    elif phase == 2:
        # Left front forward, right back forward
        _fill_rect(canvas, 34, 44, 37, 51, GOLDEN_LIGHT)
        _fill_rect(canvas, 38, 46, 41, 51, GOLDEN_LIGHT)
        _fill_rect(canvas, 24, 44, 27, 51, GOLDEN_LIGHT)
        _fill_rect(canvas, 20, 46, 23, 51, GOLDEN_LIGHT)
    else:
        # Both sides mid (other direction)
        _fill_rect(canvas, 36, 45, 39, 51, GOLDEN_LIGHT)
        _fill_rect(canvas, 40, 45, 43, 51, GOLDEN_LIGHT)
        _fill_rect(canvas, 22, 45, 25, 51, GOLDEN_LIGHT)
        _fill_rect(canvas, 26, 45, 29, 51, GOLDEN_LIGHT)

    # Tail — gentle sway
    if phase <= 1:
        _fill_rect(canvas, 14, 34, 18, 36, GOLDEN_DARK)
        _fill_rect(canvas, 12, 31, 15, 34, GOLDEN_DARK)
        _fill_rect(canvas, 10, 29, 13, 32, GOLDEN_DARK)
    else:
        _fill_rect(canvas, 14, 35, 18, 37, GOLDEN_DARK)
        _fill_rect(canvas, 12, 32, 15, 35, GOLDEN_DARK)
        _fill_rect(canvas, 11, 30, 14, 33, GOLDEN_DARK)


# ── Pomodoro timer display ─────────────────────────────────────────────

# 5x7 pixel font for digits 0-9 and colon
_DIGIT_FONT = {
    0: [[0,1,1,1,0],[1,0,0,0,1],[1,0,0,1,1],[1,0,1,0,1],[1,1,0,0,1],[1,0,0,0,1],[0,1,1,1,0]],
    1: [[0,0,1,0,0],[0,1,1,0,0],[0,0,1,0,0],[0,0,1,0,0],[0,0,1,0,0],[0,0,1,0,0],[0,1,1,1,0]],
    2: [[0,1,1,1,0],[1,0,0,0,1],[0,0,0,0,1],[0,0,0,1,0],[0,0,1,0,0],[0,1,0,0,0],[1,1,1,1,1]],
    3: [[0,1,1,1,0],[1,0,0,0,1],[0,0,0,0,1],[0,0,1,1,0],[0,0,0,0,1],[1,0,0,0,1],[0,1,1,1,0]],
    4: [[0,0,0,1,0],[0,0,1,1,0],[0,1,0,1,0],[1,0,0,1,0],[1,1,1,1,1],[0,0,0,1,0],[0,0,0,1,0]],
    5: [[1,1,1,1,1],[1,0,0,0,0],[1,1,1,1,0],[0,0,0,0,1],[0,0,0,0,1],[1,0,0,0,1],[0,1,1,1,0]],
    6: [[0,1,1,1,0],[1,0,0,0,0],[1,0,0,0,0],[1,1,1,1,0],[1,0,0,0,1],[1,0,0,0,1],[0,1,1,1,0]],
    7: [[1,1,1,1,1],[0,0,0,0,1],[0,0,0,1,0],[0,0,1,0,0],[0,0,1,0,0],[0,0,1,0,0],[0,0,1,0,0]],
    8: [[0,1,1,1,0],[1,0,0,0,1],[1,0,0,0,1],[0,1,1,1,0],[1,0,0,0,1],[1,0,0,0,1],[0,1,1,1,0]],
    9: [[0,1,1,1,0],[1,0,0,0,1],[1,0,0,0,1],[0,1,1,1,1],[0,0,0,0,1],[0,0,0,0,1],[0,1,1,1,0]],
    ':': [[0],[0],[1],[0],[1],[0],[0]],
}


def _draw_char(canvas, x, y, bitmap, color):
    """Draw a single character from bitmap at position (x, y)."""
    for row_i, row in enumerate(bitmap):
        for col_i, val in enumerate(row):
            if val:
                set_pixel(canvas, x + col_i, y + row_i, color)


def _draw_number(canvas, x, y, minutes, seconds, color):
    """Draw MM:SS at position (x, y). Returns total width drawn."""
    digits = [minutes // 10, minutes % 10, ':', seconds // 10, seconds % 10]
    cx = x
    for d in digits:
        bitmap = _DIGIT_FONT[d]
        _draw_char(canvas, cx, y, bitmap, color)
        cx += len(bitmap[0]) + 1  # character width + 1px gap


def _draw_pomo_coco(canvas, phase: str):
    """Draw a small Coco (16x16 area) in the bottom-right for pomo screen."""
    ox, oy = 45, 42  # offset — bottom right corner

    # Body
    _fill_rect(canvas, ox, oy + 6, ox + 10, oy + 14, GOLDEN)
    _fill_rect(canvas, ox + 1, oy + 8, ox + 9, oy + 12, GOLDEN_LIGHT)

    # Head
    _fill_rect(canvas, ox + 2, oy + 1, ox + 9, oy + 7, GOLDEN)

    # Ears
    _fill_rect(canvas, ox, oy + 2, ox + 2, oy + 5, GOLDEN_DARK)
    _fill_rect(canvas, ox + 9, oy + 2, ox + 11, oy + 5, GOLDEN_DARK)

    if phase == "focus":
        # Eyes — alert, focused
        set_pixel(canvas, ox + 4, oy + 4, EYE)
        set_pixel(canvas, ox + 7, oy + 4, EYE)
    else:
        # Eyes — relaxed, happy squint
        _hline(canvas, ox + 3, ox + 5, oy + 4, EYE)
        _hline(canvas, ox + 6, ox + 8, oy + 4, EYE)

    # Nose
    set_pixel(canvas, ox + 5, oy + 6, NOSE)
    set_pixel(canvas, ox + 6, oy + 6, NOSE)

    # Front legs
    _fill_rect(canvas, ox + 2, oy + 14, ox + 4, oy + 17, GOLDEN_LIGHT)
    _fill_rect(canvas, ox + 7, oy + 14, ox + 9, oy + 17, GOLDEN_LIGHT)

    # Tail
    if phase == "focus":
        set_pixel(canvas, ox - 1, oy + 7, GOLDEN_DARK)
        set_pixel(canvas, ox - 2, oy + 6, GOLDEN_DARK)
    else:
        # Wagging during break!
        set_pixel(canvas, ox - 1, oy + 6, GOLDEN_DARK)
        set_pixel(canvas, ox - 2, oy + 5, GOLDEN_DARK)
        set_pixel(canvas, ox - 3, oy + 4, GOLDEN_DARK)


def draw_pomo_screen(canvas, phase: str, remaining: int, total: int):
    """Draw the full Pomodoro timer screen on a 64x64 canvas.

    Args:
        canvas: 64x64 canvas from make_canvas().
        phase: "focus" or "break".
        remaining: Seconds remaining.
        total: Total seconds for this phase.
    """
    # Colors
    TOMATO = (220, 80, 60)
    GREEN = (80, 200, 120)
    DARK_BAR = (50, 50, 55)
    color = TOMATO if phase == "focus" else GREEN
    dim_color = (color[0] // 3, color[1] // 3, color[2] // 3)

    # Phase label — "FOCUS" or "BREAK" in small text at top
    label_color = (color[0] // 2, color[1] // 2, color[2] // 2)
    if phase == "focus":
        # F
        _fill_rect(canvas, 8, 3, 8, 7, label_color)
        set_pixel(canvas, 9, 3, label_color)
        set_pixel(canvas, 10, 3, label_color)
        set_pixel(canvas, 9, 5, label_color)
    else:
        # B
        _fill_rect(canvas, 8, 3, 8, 7, label_color)
        set_pixel(canvas, 9, 3, label_color)
        set_pixel(canvas, 10, 3, label_color)
        set_pixel(canvas, 9, 5, label_color)
        set_pixel(canvas, 10, 5, label_color)
        set_pixel(canvas, 9, 7, label_color)
        set_pixel(canvas, 10, 7, label_color)
        set_pixel(canvas, 10, 4, label_color)
        set_pixel(canvas, 10, 6, label_color)

    # Big countdown digits — centered
    minutes = remaining // 60
    seconds = remaining % 60
    # "MM:SS" is about 23px wide (5+1+5+1+1+1+5+1+5), center at x=20
    _draw_number(canvas, 14, 14, minutes, seconds, color)

    # Progress bar — y=28..30, x=6..57
    bar_left = 6
    bar_right = 57
    bar_width = bar_right - bar_left
    _fill_rect(canvas, bar_left, 28, bar_right, 30, DARK_BAR)

    if total > 0:
        progress = 1.0 - (remaining / total)
        fill_right = bar_left + int(progress * bar_width)
        if fill_right > bar_left:
            _fill_rect(canvas, bar_left, 28, fill_right, 30, color)

    # Small decorative dots on progress bar edges
    set_pixel(canvas, bar_left, 28, dim_color)
    set_pixel(canvas, bar_right, 30, dim_color)

    # Ground
    _fill_rect(canvas, 0, 60, 63, 63, (35, 33, 28))
    _hline(canvas, 0, 63, 59, (45, 42, 35))

    # Small Coco in corner
    _draw_pomo_coco(canvas, phase)


# ── Mood dispatcher ────────────────────────────────────────────────────

_MOOD_DRAWERS = {
    "chill": _draw_chill,
    "happy": _draw_happy,
    "sleepy": _draw_sleepy,
    "curious": _draw_curious,
}


def show_mood(display: PixooDisplay, mood: str) -> bool:
    """Draw the golden retriever in the given mood on *display*.

    Animated moods: celebrate, happy, chill.
    Static moods: sleepy, curious.
    Returns True on success (or if display is unavailable — not an error).
    """
    mood = mood.lower().strip()

    if mood == "celebrate":
        frames = []
        for phase in range(3):
            c = make_canvas()
            _draw_celebrate(c, tail_phase=phase)
            frames.append(c)
        return display.send_animation(frames, pic_id=1, speed=400)

    if mood == "happy":
        frames = []
        for phase in range(3):
            c = make_canvas()
            _draw_happy_anim(c, tail_phase=phase)
            frames.append(c)
        return display.send_animation(frames, pic_id=1, speed=500)

    if mood == "chill":
        frames = []
        for phase in range(2):
            c = make_canvas()
            _draw_chill_anim(c, phase=phase)
            frames.append(c)
        return display.send_animation(frames, pic_id=1, speed=800)

    drawer = _MOOD_DRAWERS.get(mood)
    if drawer is None:
        logger.warning("Unknown mood %r — falling back to 'happy'", mood)
        drawer = _draw_happy

    c = make_canvas()
    drawer(c)
    return display.send_frame(c, pic_id=1)


def show_music(display: PixooDisplay) -> bool:
    """Show the music-listening animation — head bobbing with floating notes."""
    frames = []
    for phase in range(3):
        c = make_canvas()
        _draw_music(c, phase=phase)
        frames.append(c)
    return display.send_animation(frames, pic_id=1, speed=500)
