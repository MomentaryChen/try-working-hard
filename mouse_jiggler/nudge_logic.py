"""Pure validation and countdown formatting (no GUI / Win32)."""

from __future__ import annotations

import math

MIN_MINUTES = 0.1
DEFAULT_MINUTES = 5.0
MIN_PIXELS = 0
MAX_PIXELS = 500
DEFAULT_PIXELS = 100
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
