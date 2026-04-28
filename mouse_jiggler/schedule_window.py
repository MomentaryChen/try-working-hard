"""Local-time scheduling helpers with multi-window and cron-like support."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta

_CRON_MAX_LOOKAHEAD_MINUTES = 366 * 24 * 60

DEFAULT_WORK_START = time(9, 0, 0)
DEFAULT_WORK_END = time(18, 0, 0)


@dataclass(frozen=True)
class CronSchedule:
    """A parsed 5-field cron-like expression."""

    minutes: set[int]
    hours: set[int]
    days: set[int]
    months: set[int]
    weekdays: set[int]  # Python weekday: Monday=0 ... Sunday=6
    source: str


@dataclass(frozen=True)
class WindowSchedule:
    """Weekly schedule with weekday filters and daily time segments."""

    weekdays: set[int]  # Python weekday: Monday=0 ... Sunday=6
    segments: tuple[tuple[time, time], ...]


@dataclass(frozen=True)
class ScheduleSpec:
    """Unified schedule spec used by runtime checks."""

    windows: WindowSchedule | None
    cron_rules: tuple[CronSchedule, ...]


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


def parse_time_segments(text: str) -> tuple[tuple[time, time], ...] | None:
    """Parse comma-separated ``HH:MM-HH:MM`` segments."""
    parts = [p.strip() for p in str(text).split(",") if p.strip()]
    if not parts:
        return None
    out: list[tuple[time, time]] = []
    for seg in parts:
        if "-" not in seg:
            return None
        a_raw, b_raw = seg.split("-", 1)
        a = parse_hhmm(a_raw)
        b = parse_hhmm(b_raw)
        if a is None or b is None or a >= b:
            return None
        out.append((a, b))
    out.sort(key=lambda x: (x[0].hour, x[0].minute, x[1].hour, x[1].minute))
    for i in range(1, len(out)):
        if out[i - 1][1] > out[i][0]:
            return None
    return tuple(out)


def parse_weekdays(text: str, *, include_weekends: bool = False) -> set[int] | None:
    """Parse weekday text into Python weekday numbers."""
    if include_weekends:
        return set(range(7))
    raw = str(text).strip().lower()
    if not raw:
        return {0, 1, 2, 3, 4}
    if raw in {"weekday", "weekdays", "mon-fri", "monday-friday"}:
        return {0, 1, 2, 3, 4}
    if raw in {"weekend", "weekends", "sat-sun", "saturday-sunday"}:
        return {5, 6}
    if raw in {"all", "everyday", "daily", "mon-sun"}:
        return set(range(7))
    token_map = {
        "mon": 0,
        "monday": 0,
        "tue": 1,
        "tues": 1,
        "tuesday": 1,
        "wed": 2,
        "wednesday": 2,
        "thu": 3,
        "thur": 3,
        "thurs": 3,
        "thursday": 3,
        "fri": 4,
        "friday": 4,
        "sat": 5,
        "saturday": 5,
        "sun": 6,
        "sunday": 6,
    }
    out: set[int] = set()
    for token in [t.strip() for t in raw.split(",") if t.strip()]:
        if "-" in token:
            a_raw, b_raw = token.split("-", 1)
            a = token_map.get(a_raw.strip())
            b = token_map.get(b_raw.strip())
            if a is None or b is None:
                return None
            i = a
            while True:
                out.add(i)
                if i == b:
                    break
                i = (i + 1) % 7
        else:
            v = token_map.get(token)
            if v is None:
                return None
            out.add(v)
    return out or None


def _expand_cron_part(
    part: str,
    lo: int,
    hi: int,
    *,
    names: dict[str, int] | None = None,
    sunday_alias_to_0: bool = False,
) -> set[int] | None:
    vals: set[int] = set()
    for item in [x.strip() for x in part.split(",") if x.strip()]:
        if "/" in item:
            base, step_raw = item.split("/", 1)
            if not step_raw.isdigit():
                return None
            step = int(step_raw)
            if step <= 0:
                return None
        else:
            base, step = item, 1
        if base == "*":
            start, end = lo, hi
        elif "-" in base:
            a_raw, b_raw = base.split("-", 1)
            a = _parse_cron_token(a_raw, names=names, sunday_alias_to_0=sunday_alias_to_0)
            b = _parse_cron_token(b_raw, names=names, sunday_alias_to_0=sunday_alias_to_0)
            if a is None or b is None:
                return None
            if a <= b:
                start, end = a, b
            else:
                return None
        else:
            v = _parse_cron_token(base, names=names, sunday_alias_to_0=sunday_alias_to_0)
            if v is None:
                return None
            start, end = v, v
        if start < lo or end > hi:
            return None
        vals.update(range(start, end + 1, step))
    return vals or None


def _parse_cron_token(
    token: str,
    *,
    names: dict[str, int] | None = None,
    sunday_alias_to_0: bool = False,
) -> int | None:
    s = token.strip().lower()
    if names and s in names:
        return names[s]
    if not s.isdigit():
        return None
    v = int(s)
    if sunday_alias_to_0 and v == 7:
        return 0
    return v


def parse_cron_like(expr: str) -> CronSchedule | None:
    """Parse a standard-ish 5-field cron expression."""
    fields = [f for f in str(expr).strip().split() if f]
    if len(fields) != 5:
        return None
    dow_names = {
        "sun": 0,
        "mon": 1,
        "tue": 2,
        "wed": 3,
        "thu": 4,
        "fri": 5,
        "sat": 6,
    }
    minutes = _expand_cron_part(fields[0], 0, 59)
    hours = _expand_cron_part(fields[1], 0, 23)
    days = _expand_cron_part(fields[2], 1, 31)
    months = _expand_cron_part(fields[3], 1, 12)
    dows = _expand_cron_part(
        fields[4], 0, 6, names=dow_names, sunday_alias_to_0=True
    )
    if None in (minutes, hours, days, months, dows):
        return None
    assert minutes is not None
    assert hours is not None
    assert days is not None
    assert months is not None
    assert dows is not None
    py_weekdays = {((d + 6) % 7) for d in dows}  # cron 0=Sun -> python 6
    return CronSchedule(
        minutes=minutes,
        hours=hours,
        days=days,
        months=months,
        weekdays=py_weekdays,
        source=str(expr).strip(),
    )


def build_schedule_spec(
    *,
    window_segments_text: str,
    include_weekends: bool,
    cron_text: str,
    weekday_text: str = "mon-fri",
) -> ScheduleSpec | None:
    """Build an executable schedule from user/config text."""
    cron_rules: list[CronSchedule] = []
    cron_clean = str(cron_text).strip()
    if cron_clean:
        for expr in [p.strip() for p in cron_clean.split(";") if p.strip()]:
            c = parse_cron_like(expr)
            if c is None:
                return None
            cron_rules.append(c)
    segments = parse_time_segments(window_segments_text)
    if segments is None:
        return None
    weekdays = parse_weekdays(weekday_text, include_weekends=include_weekends)
    if weekdays is None:
        return None
    return ScheduleSpec(
        windows=WindowSchedule(weekdays=weekdays, segments=segments),
        cron_rules=tuple(cron_rules),
    )


def _cron_matches(now: datetime, rule: CronSchedule) -> bool:
    return (
        now.minute in rule.minutes
        and now.hour in rule.hours
        and now.day in rule.days
        and now.month in rule.months
        and now.weekday() in rule.weekdays
    )


def is_within_schedule(now: datetime, spec: ScheduleSpec) -> bool:
    """Return True when ``now`` is inside any allowed window/cron minute."""
    if spec.windows is not None:
        if now.weekday() in spec.windows.weekdays:
            t = now.time()
            for a, b in spec.windows.segments:
                if a <= t < b:
                    return True
    for rule in spec.cron_rules:
        if _cron_matches(now, rule):
            return True
    return False


def next_schedule_start(after: datetime, spec: ScheduleSpec) -> datetime:
    """Find the next schedule hit at/after ``after``."""
    if is_within_schedule(after, spec):
        return after
    candidate = after + timedelta(minutes=1)
    candidate = candidate.replace(second=0, microsecond=0)
    for _ in range(_CRON_MAX_LOOKAHEAD_MINUTES):
        if is_within_schedule(candidate, spec):
            return candidate
        candidate += timedelta(minutes=1)
    return candidate


def is_within_work_window(
    now: datetime, work_start: time, work_end: time
) -> bool:
    """True on a weekday when ``work_start <= now.time() < work_end``."""
    ws, we = (
        (DEFAULT_WORK_START, DEFAULT_WORK_END)
        if work_start >= work_end
        else (work_start, work_end)
    )
    spec = ScheduleSpec(
        windows=WindowSchedule(weekdays={0, 1, 2, 3, 4}, segments=((ws, we),)),
        cron_rules=(),
    )
    return is_within_schedule(now, spec)


def next_window_start(
    after: datetime, work_start: time, work_end: time
) -> datetime:
    """Earliest time at or after ``after`` inside the Mon–Fri work window.

    If ``work_start >= work_end``, uses ``09:00`` / ``18:00`` as a fallback.
    """
    ws = work_start if work_start < work_end else DEFAULT_WORK_START
    we = work_end if work_start < work_end else DEFAULT_WORK_END
    spec = ScheduleSpec(
        windows=WindowSchedule(weekdays={0, 1, 2, 3, 4}, segments=((ws, we),)),
        cron_rules=(),
    )
    return next_schedule_start(after, spec)
