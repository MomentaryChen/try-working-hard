"""Persist aggregate analytics (nudge counts, runtime) beside ``config.json``."""

from __future__ import annotations

import json
import os
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from . import local_config
from .cursor_nudge import MotionPattern

ANALYTICS_VERSION = 1
_KEEP_DAYS = 120
_FILE_LOCK = threading.RLock()

AnalyticsPatternKey = MotionPattern | Literal["natural"]

_PATTERN_KEYS: tuple[AnalyticsPatternKey, ...] = (
    "horizontal",
    "circle",
    "square",
    "natural",
)


def _normalize_pattern_dict(pat: object) -> dict[str, int]:
    out = {"horizontal": 0, "circle": 0, "square": 0, "natural": 0}
    if isinstance(pat, dict):
        for k in _PATTERN_KEYS:
            try:
                out[str(k)] = int(pat.get(k, 0) or 0)
            except (TypeError, ValueError):
                out[str(k)] = 0
    return out


def default_analytics_path() -> Path:
    return local_config.default_config_path().parent / "analytics.json"


def _empty_day() -> dict[str, Any]:
    return {
        "hourly_nudges": [0] * 24,
        "runtime_sec": 0.0,
        "pattern": {"horizontal": 0, "circle": 0, "square": 0, "natural": 0},
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


def _prune(days: dict[str, Any]) -> bool:
    """Drop days older than ``_KEEP_DAYS``; return ``True`` if anything was removed."""
    cutoff = date.today() - timedelta(days=_KEEP_DAYS)
    stale = [
        k
        for k in list(days.keys())
        if (parsed := _parse_day_key(str(k))) is not None and parsed < cutoff
    ]
    for k in stale:
        del days[k]
    return bool(stale)


def _save(data: dict[str, Any], path: Path | None = None) -> None:
    """Write atomically (temp file + replace) so a crash never leaves a truncated file."""
    p = path or default_analytics_path()
    tmp = p.with_name(p.name + ".tmp")
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, p)
    except OSError:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass



def data_signature() -> tuple[int, int] | None:
    """``(mtime_ns, size)`` of the analytics file, or ``None`` if missing.

    Lets the UI skip re-reading and redrawing charts when nothing was written.
    """
    try:
        st = default_analytics_path().stat()
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size)


def record_nudge(pattern: AnalyticsPatternKey, at: datetime | None = None) -> None:
    """Record one nudge event (including 0 px ticks). Thread-safe."""
    when = at or datetime.now()
    dk = when.date().isoformat()
    hour = when.hour
    pk = pattern if pattern in _PATTERN_KEYS else None
    if pk is None:
        return
    with _FILE_LOCK:
        doc = _load_raw()
        days: dict[str, Any] = doc["days"]
        _prune(days)
        day = days.setdefault(dk, _empty_day())
        hrs = day.get("hourly_nudges")
        if not isinstance(hrs, list) or len(hrs) != 24:
            day["hourly_nudges"] = [0] * 24
        pat = day.setdefault("pattern", {})
        norm = _normalize_pattern_dict(pat)
        day["pattern"] = norm
        day["hourly_nudges"][hour] = int(day["hourly_nudges"][hour]) + 1
        k = str(pk)
        norm[k] = int(norm[k]) + 1
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
        # Reads are frequent (chart refresh); rewrite the file only when pruning changed it.
        if _prune(raw_days):
            _save(doc)
        out: dict[str, dict[str, Any]] = {}
        for k, v in raw_days.items():
            if isinstance(v, dict):
                out[str(k)] = v
        return out
