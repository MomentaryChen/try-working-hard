"""Pure validation and countdown formatting (no GUI / Win32)."""

from __future__ import annotations

import math
import random
from typing import Literal

MIN_MINUTES = 0.1
DEFAULT_MINUTES = 5.0
# Minimum interval in seconds (matches 0.1 min) so the floor is the same in both unit modes.
MIN_SECONDS = MIN_MINUTES * 60.0
MIN_PIXELS = 0
MAX_PIXELS = 500
# Natural mode may use a larger wander radius than geometric patterns.
MAX_NATURAL_PIXELS = 1000
DEFAULT_PIXELS = 100
# Scales every cursor step delay (100 = app default timing; higher = longer motion).
MIN_MOTION_DURATION_PERCENT = 10
MAX_MOTION_DURATION_PERCENT = 500
DEFAULT_MOTION_DURATION_PERCENT = 100
# Path trace speed 1–10: higher = faster along line / circle / square.
MIN_PATH_SPEED = 1
MAX_PATH_SPEED = 10
DEFAULT_PATH_SPEED = 5
LOG_TRIM_LINES = 48
# Upper bound for ± jitter (seconds) in the UI and config.
MAX_INTERVAL_JITTER_SEC = 3600.0


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


def parse_path_speed_string(
    raw: str,
    *,
    min_sp: int = MIN_PATH_SPEED,
    max_sp: int = MAX_PATH_SPEED,
) -> int | None:
    """Parse path speed as integer ``min_sp``–``max_sp``; ``None`` if invalid."""
    s = raw.strip().replace(",", ".")
    try:
        f = float(s)
        if not math.isfinite(f):
            return None
        p = int(f)
    except (ValueError, OverflowError):
        return None
    if p < min_sp or p > max_sp:
        return None
    return p


def parse_motion_duration_percent_string(
    raw: str,
    *,
    min_pct: int = MIN_MOTION_DURATION_PERCENT,
    max_pct: int = MAX_MOTION_DURATION_PERCENT,
) -> int | None:
    """Parse motion duration scale as integer percent ``min_pct``–``max_pct``; ``None`` if invalid."""
    s = raw.strip().replace(",", ".")
    try:
        f = float(s)
        if not math.isfinite(f):
            return None
        p = int(f)
    except (ValueError, OverflowError):
        return None
    if p < min_pct or p > max_pct:
        return None
    return p


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


def eta_seconds_until_idle_nudge(
    interval_sec: float,
    idle_sec: float,
    *,
    now: float,
    last_nudge_monotonic: float | None,
) -> float:
    """
    Time until a nudge may fire, given required idle time ``interval_sec`` and optional
    spacing (no closer than ``interval_sec`` after ``last_nudge_monotonic``).
    """
    need_idle = max(0.0, interval_sec - idle_sec)
    if last_nudge_monotonic is None:
        return need_idle
    need_gap = max(0.0, interval_sec - (now - last_nudge_monotonic))
    return max(need_idle, need_gap)


def log_lines_to_delete_from_top(total_lines: int, max_lines: int) -> int:
    """How many lines to remove from the head so at most ``max_lines`` remain."""
    excess = total_lines - max_lines
    return excess if excess > 0 else 0


def parse_interval_jitter_seconds_string(
    raw: str,
    *,
    max_jitter: float = MAX_INTERVAL_JITTER_SEC,
) -> float | None:
    """Parse non-negative jitter in seconds; ``None`` if out of range or invalid."""
    s = raw.strip().replace(",", ".")
    try:
        v = float(s)
    except ValueError:
        return None
    if not math.isfinite(v) or v < 0.0 or v > max_jitter:
        return None
    return v


def next_wait_seconds(base_sec: float, jitter_sec: float) -> float:
    """
    Draw the next sleep duration: uniform in ``[base - j, base + j]``, floored at
    ``MIN_SECONDS``. When ``jitter_sec`` is zero or negative, returns ``base_sec``
    (caller should already enforce ``base_sec >= MIN_SECONDS``).
    """
    if not math.isfinite(base_sec):
        return MIN_SECONDS
    base = max(MIN_SECONDS, base_sec)
    if jitter_sec <= 0.0 or not math.isfinite(jitter_sec):
        return base
    j = min(max(0.0, jitter_sec), MAX_INTERVAL_JITTER_SEC)
    low = base - j
    high = base + j
    w = random.uniform(low, high)
    return max(MIN_SECONDS, w)
