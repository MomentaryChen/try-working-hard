"""Persist aggregate analytics (nudge counts, runtime) beside ``config.json``."""

from __future__ import annotations

import copy
import json
import os
import threading
import time
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
    cutoff = _today() - timedelta(days=_KEEP_DAYS)
    stale = [
        k
        for k in list(days.keys())
        if (parsed := _parse_day_key(str(k))) is not None and parsed < cutoff
    ]
    for k in stale:
        del days[k]
    return bool(stale)


def _save(data: dict[str, Any], path: Path | None = None) -> bool:
    """Write atomically (temp file + replace) so a crash never leaves a truncated file.

    Returns ``True`` on success, ``False`` if the write failed.
    """
    p = path or default_analytics_path()
    tmp = p.with_name(p.name + ".tmp")
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, p)
        return True
    except OSError:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return False


# --- In-memory cache -------------------------------------------------------------
# Increments are applied to a cached document and written to disk at most every
# ``FLUSH_INTERVAL_SEC`` (plus forced flushes on Stop and shutdown via ``flush()``).
# All cache state is guarded by ``_FILE_LOCK``.

FLUSH_INTERVAL_SEC = 60.0

_cache_doc: dict[str, Any] | None = None
_cache_path: Path | None = None
_dirty = False
_last_flush_mono = 0.0
_last_prune_day: date | None = None
_revision = 0


def _monotonic() -> float:
    return time.monotonic()


def _today() -> date:
    return date.today()


def _reset_cache() -> None:
    """Drop the in-memory cache without writing it (used by tests)."""
    global _cache_doc, _cache_path, _dirty, _last_flush_mono, _last_prune_day
    with _FILE_LOCK:
        _cache_doc = None
        _cache_path = None
        _dirty = False
        _last_flush_mono = 0.0
        _last_prune_day = None


def _bump_revision() -> None:
    global _revision
    _revision += 1


def _ensure_cache() -> dict[str, Any]:
    """Return the cached document, (re)loading it when missing or the path changed.

    Caller must hold ``_FILE_LOCK``.
    """
    global _cache_doc, _cache_path, _dirty, _last_flush_mono, _last_prune_day
    path = default_analytics_path()
    if _cache_doc is None or _cache_path != path:
        _cache_doc = _load_raw(path)
        _cache_path = path
        _dirty = False
        _last_flush_mono = _monotonic()
        _last_prune_day = None
        _bump_revision()
    _maybe_prune(_cache_doc)
    return _cache_doc


def _maybe_prune(doc: dict[str, Any]) -> None:
    """Prune stale days at most once per calendar day. Caller must hold ``_FILE_LOCK``."""
    global _dirty, _last_prune_day
    today = _today()
    if _last_prune_day == today:
        return
    _last_prune_day = today
    if _prune(doc["days"]):
        _dirty = True
        _bump_revision()
        # Pruning runs at most once a day, so persist it right away.
        _flush_locked()


def _mark_dirty() -> None:
    global _dirty
    _dirty = True
    _bump_revision()


def _flush_locked() -> bool:
    """Write the cache if dirty. Caller must hold ``_FILE_LOCK``."""
    global _dirty, _last_flush_mono
    if _cache_doc is None or not _dirty:
        return True
    ok = _save(_cache_doc, _cache_path)
    if ok:
        _dirty = False
    _last_flush_mono = _monotonic()
    return ok


def _maybe_flush_locked() -> None:
    if _monotonic() - _last_flush_mono >= FLUSH_INTERVAL_SEC:
        _flush_locked()


def flush() -> bool:
    """Write pending increments to disk now (no-op when nothing changed). Thread-safe.

    Returns ``False`` if a write was needed and failed.
    """
    with _FILE_LOCK:
        return _flush_locked()


def data_signature() -> int:
    """In-memory revision of the analytics data (changes on every increment or prune).

    Lets the UI skip re-reading and redrawing charts when nothing changed. Pending
    (not yet flushed) increments are included.
    """
    with _FILE_LOCK:
        _ensure_cache()
        return _revision


def record_nudge(pattern: AnalyticsPatternKey, at: datetime | None = None) -> None:
    """Record one nudge event (including 0 px ticks). Thread-safe."""
    when = at or datetime.now()
    dk = when.date().isoformat()
    hour = when.hour
    pk = pattern if pattern in _PATTERN_KEYS else None
    if pk is None:
        return
    with _FILE_LOCK:
        doc = _ensure_cache()
        days: dict[str, Any] = doc["days"]
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
        _mark_dirty()
        _maybe_flush_locked()


def add_runtime_seconds(seconds: float, on_date: date | None = None) -> None:
    """Add scheduled-runtime seconds for a calendar day (session uptime). Thread-safe."""
    if seconds <= 0:
        return
    dk = (on_date or _today()).isoformat()
    with _FILE_LOCK:
        doc = _ensure_cache()
        days: dict[str, Any] = doc["days"]
        day = days.setdefault(dk, _empty_day())
        day["runtime_sec"] = float(day.get("runtime_sec", 0.0)) + float(seconds)
        _mark_dirty()
        _maybe_flush_locked()


def load_days_copy() -> dict[str, dict[str, Any]]:
    """Return day-keyed aggregates for charting (last ``_KEEP_DAYS`` days).

    Includes increments not yet flushed to disk. The result is a deep copy, so callers
    can read it while the worker keeps recording.
    """
    with _FILE_LOCK:
        doc = _ensure_cache()
        raw_days = doc.get("days")
        if not isinstance(raw_days, dict):
            return {}
        return {str(k): copy.deepcopy(v) for k, v in raw_days.items() if isinstance(v, dict)}
