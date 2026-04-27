"""Local-time work window: Mon–Fri 09:00–18:00 (start inclusive, end exclusive)."""

from __future__ import annotations

from datetime import datetime, time, timedelta

WORK_START = time(9, 0, 0)
WORK_END = time(18, 0, 0)


def is_within_work_window(now: datetime) -> bool:
    """Return True when ``now`` falls on a weekday and in [09:00, 18:00)."""
    if now.weekday() >= 5:
        return False
    t = now.time()
    return WORK_START <= t < WORK_END


def next_window_start(after: datetime) -> datetime:
    """Earliest time at or after ``after`` when :func:`is_within_work_window` is True.

    If ``after`` is already inside the work window, returns ``after`` unchanged.
    """
    d = after.date()
    w = after.weekday()
    t = after.time()
    if w < 5:
        if t < WORK_START:
            return datetime.combine(d, WORK_START)
        if t < WORK_END:
            return after
        next_day = d + (timedelta(days=3) if w == 4 else timedelta(days=1))
        return datetime.combine(next_day, WORK_START)
    if w == 5:
        monday = d + timedelta(days=2)
    else:
        monday = d + timedelta(days=1)
    return datetime.combine(monday, WORK_START)
