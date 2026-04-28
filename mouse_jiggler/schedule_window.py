"""Local-time work window: Mon–Fri [work_start, work_end), end exclusive."""

from __future__ import annotations

from datetime import datetime, time, timedelta

DEFAULT_WORK_START = time(9, 0, 0)
DEFAULT_WORK_END = time(18, 0, 0)


def parse_hhmm(s: str) -> time | None:
    """Parse ``HH:MM`` (24-hour). Whitespace trimmed; seconds not allowed."""
    parts = str(s).strip().split(":")
    if len(parts) != 2:
        return None
    a, b = parts[0].strip(), parts[1].strip()
    if not a.isdigit() or not b.isdigit():
        return None
    h, m = int(a), int(b)
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return time(h, m, 0)


def format_hhmm(t: time) -> str:
    return f"{t.hour:02d}:{t.minute:02d}"


def is_within_work_window(
    now: datetime, work_start: time, work_end: time
) -> bool:
    """True on a weekday when ``work_start <= now.time() < work_end``."""
    ws, we = (
        (DEFAULT_WORK_START, DEFAULT_WORK_END)
        if work_start >= work_end
        else (work_start, work_end)
    )
    if now.weekday() >= 5:
        return False
    t = now.time()
    return ws <= t < we


def next_window_start(
    after: datetime, work_start: time, work_end: time
) -> datetime:
    """Earliest time at or after ``after`` inside the Mon–Fri work window.

    If ``work_start >= work_end``, uses ``09:00`` / ``18:00`` as a fallback.
    """
    ws = work_start if work_start < work_end else DEFAULT_WORK_START
    we = work_end if work_start < work_end else DEFAULT_WORK_END

    d = after.date()
    w = after.weekday()
    t = after.time()
    if w < 5:
        if t < ws:
            return datetime.combine(d, ws)
        if t < we:
            return after
        if w == 4:
            next_day = d + timedelta(days=3)
        else:
            next_day = d + timedelta(days=1)
        return datetime.combine(next_day, ws)
    if w == 5:
        monday = d + timedelta(days=2)
    else:
        monday = d + timedelta(days=1)
    return datetime.combine(monday, ws)
