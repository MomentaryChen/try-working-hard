"""Persist aggregate analytics (nudge counts, runtime) beside ``config.json``."""

from __future__ import annotations

import json
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from . import local_config
from .cursor_nudge import MotionPattern

ANALYTICS_VERSION = 1
_KEEP_DAYS = 120
_FILE_LOCK = threading.RLock()

_PATTERN_KEYS: tuple[MotionPattern, ...] = ("horizontal", "circle", "square")


def default_analytics_path() -> Path:
    return local_config.default_config_path().parent / "analytics.json"


def _empty_day() -> dict[str, Any]:
    return {
        "hourly_nudges": [0] * 24,
        "runtime_sec": 0.0,
        "pattern": {"horizontal": 0, "circle": 0, "square": 0},
    }


def _parse_day_key(s: str) -> date | None:
    try:
        y, m, d = (int(x) for x in s.split("-", 2))
        return date(y, m, d)
    except (ValueError, TypeError):
        return None


def _load_raw(path: Path | None = None) -> dict[str, Any]:
    p = path or default_analytics_path()
    if not p.is_file():
        return {"version": ANALYTICS_VERSION, "days": {}}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {"version": ANALYTICS_VERSION, "days": {}}
    if not isinstance(raw, dict):
        return {"version": ANALYTICS_VERSION, "days": {}}
    days = raw.get("days")
    if not isinstance(days, dict):
        days = {}
    return {"version": ANALYTICS_VERSION, "days": days}


def _prune(days: dict[str, Any]) -> None:
    cutoff = date.today() - timedelta(days=_KEEP_DAYS)
    stale = [
        k
        for k in list(days.keys())
        if (parsed := _parse_day_key(str(k))) is not None and parsed < cutoff
    ]
    for k in stale:
        del days[k]


def _save(data: dict[str, Any], path: Path | None = None) -> None:
    p = path or default_analytics_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass


def record_nudge(pattern: MotionPattern, at: datetime | None = None) -> None:
    """Record one nudge event (including 0 px ticks). Thread-safe."""
    when = at or datetime.now()
    dk = when.date().isoformat()
    hour = when.hour
    if pattern not in _PATTERN_KEYS:
        return
    with _FILE_LOCK:
        doc = _load_raw()
        days: dict[str, Any] = doc["days"]
        _prune(days)
        day = days.setdefault(dk, _empty_day())
        hrs = day.get("hourly_nudges")
        if not isinstance(hrs, list) or len(hrs) != 24:
            day["hourly_nudges"] = [0] * 24
        pat = day.setdefault("pattern", {"horizontal": 0, "circle": 0, "square": 0})
        for key in _PATTERN_KEYS:
            pat.setdefault(key, 0)
        day["hourly_nudges"][hour] = int(day["hourly_nudges"][hour]) + 1
        pat[pattern] = int(pat[pattern]) + 1
        _save(doc)


def add_runtime_seconds(seconds: float, on_date: date | None = None) -> None:
    """Add scheduled-runtime seconds for a calendar day (session uptime). Thread-safe."""
    if seconds <= 0:
        return
    dk = (on_date or date.today()).isoformat()
    with _FILE_LOCK:
        doc = _load_raw()
        days: dict[str, Any] = doc["days"]
        _prune(days)
        day = days.setdefault(dk, _empty_day())
        day["runtime_sec"] = float(day.get("runtime_sec", 0.0)) + float(seconds)
        _save(doc)


def load_days_copy() -> dict[str, dict[str, Any]]:
    """Return day-keyed aggregates for charting (last ``_KEEP_DAYS`` days)."""
    with _FILE_LOCK:
        doc = _load_raw()
        raw_days = doc.get("days")
        if not isinstance(raw_days, dict):
            return {}
        _prune(raw_days)
        _save(doc)
        out: dict[str, dict[str, Any]] = {}
        for k, v in raw_days.items():
            if isinstance(v, dict):
                out[str(k)] = v
        return out
