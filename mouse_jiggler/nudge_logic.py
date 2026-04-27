"""Pure validation and countdown formatting (no GUI / Win32)."""

from __future__ import annotations

import math
from typing import Literal

MIN_MINUTES = 0.1
DEFAULT_MINUTES = 5.0
# Minimum interval in seconds (matches 0.1 min) so the floor is the same in both unit modes.
MIN_SECONDS = MIN_MINUTES * 60.0
MIN_PIXELS = 0
MAX_PIXELS = 500
DEFAULT_PIXELS = 100
# After each interval, repeat nudges for this many seconds before the next idle wait (0 = one nudge only).
MIN_MOTION_BURST_SEC = 0.0
MAX_MOTION_BURST_SEC = 600.0
DEFAULT_MOTION_BURST_SEC = 0.0
# Pause between nudges while a motion burst is active (keeps input rate reasonable).
MOTION_BURST_STEP_SEC = 0.25
LOG_TRIM_LINES = 48


def parse_minutes_string(raw: str, *, min_minutes: float = MIN_MINUTES) -> float | None:
    """Parse interval minutes from user input; ``None`` if invalid or below ``min_minutes``."""
    s = raw.strip().replace(",", ".")
    try:
        m = float(s)
    except ValueError:
        return None
    if not math.isfinite(m) or m < min_minutes:
        return None
    return m


IntervalUnit = Literal["min", "sec"]


def parse_seconds_string(raw: str, *, min_seconds: float = MIN_SECONDS) -> float | None:
    """Parse interval seconds; ``None`` if invalid or below ``min_seconds``."""
    s = raw.strip().replace(",", ".")
    try:
        sec = float(s)
    except ValueError:
        return None
    if not math.isfinite(sec) or sec < min_seconds:
        return None
    return sec


def parse_interval_to_seconds(
    raw: str, unit: IntervalUnit, *, min_minutes: float = MIN_MINUTES, min_seconds: float = MIN_SECONDS
) -> float | None:
    """User-facing interval → seconds, or ``None`` if the value is not allowed for ``unit``."""
    if unit == "min":
        m = parse_minutes_string(raw, min_minutes=min_minutes)
        return None if m is None else m * 60.0
    s = parse_seconds_string(raw, min_seconds=min_seconds)
    return None if s is None else s


def parse_motion_burst_seconds_string(
    raw: str,
    *,
    min_sec: float = MIN_MOTION_BURST_SEC,
    max_sec: float = MAX_MOTION_BURST_SEC,
) -> float | None:
    """Parse active motion duration in seconds; ``None`` if out of range or non-finite."""
    s = raw.strip().replace(",", ".")
    try:
        v = float(s)
    except ValueError:
        return None
    if not math.isfinite(v) or v < min_sec or v > max_sec:
        return None
    return v


def parse_pixels_string(raw: str, *, min_px: int = MIN_PIXELS, max_px: int = MAX_PIXELS) -> int | None:
    """Parse nudge size in pixels; ``None`` if not an integer in ``[min_px, max_px]``."""
    s = raw.strip().replace(",", ".")
    try:
        f = float(s)
        if not math.isfinite(f):
            return None
        p = int(f)
    except (ValueError, OverflowError):
        return None
    if p < min_px or p > max_px:
        return None
    return p


def format_countdown_display(total_sec: int) -> str:
    """
    Format non-negative whole seconds for status text: ``M:SS`` or ``H:MM:SS`` when the
    minute component of the remainder is at least 60 (same rules as the live UI).
    """
    t = max(0, int(total_sec))
    mm, ss = divmod(t, 60)
    if mm >= 60:
        hh, mm = divmod(mm, 60)
        return f"{hh}:{mm:02d}:{ss:02d}"
    return f"{mm}:{ss:02d}"


def remaining_seconds_to_countdown_display(remaining: float) -> str:
    """Round remaining seconds (half-up) and format like the Tk countdown tick."""
    sec = int(max(0.0, remaining) + 0.5)
    return format_countdown_display(sec)


def log_lines_to_delete_from_top(total_lines: int, max_lines: int) -> int:
    """How many lines to remove from the head so at most ``max_lines`` remain."""
    excess = total_lines - max_lines
    return excess if excess > 0 else 0
