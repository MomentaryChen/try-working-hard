"""Load and save app preferences to a local JSON file (Windows: %APPDATA%\\try-working-hard)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

from . import nudge_logic, schedule_window
from .cursor_nudge import MotionPattern

Lang = Literal["zh", "en"]

CONFIG_VERSION = 1


def default_config_path() -> Path:
    """User config file path; prefers ``APPDATA`` on Windows."""
    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / "try-working-hard" / "config.json"
    return Path.home() / ".try-working-hard" / "config.json"


def _defaults() -> dict[str, Any]:
    return {
        "version": CONFIG_VERSION,
        "lang": "en",
        "ui_theme": "dark",
        "interval_text": str(int(nudge_logic.DEFAULT_MINUTES)),
        "interval_unit": "min",
        "interval_jitter_text": "0",
        "pixels_text": str(nudge_logic.DEFAULT_PIXELS),
        "path_speed_text": str(nudge_logic.DEFAULT_PATH_SPEED),
        "motion_pattern": "horizontal",
        "close_to_tray": False,
        "intro_acknowledged": False,
        "schedule_window": False,
        "schedule_window_start_text": "09:00",
        "schedule_window_end_text": "18:00",
        "auto_check_updates": True,
    }


def _sanitize_lang(raw: object) -> Lang | None:
    if raw in ("zh", "en"):
        return raw  # type: ignore[return-value]
    return None


def _sanitize_ui_theme(raw: object) -> str | None:
    if raw in ("dark", "light"):
        return raw  # type: ignore[return-value]
    return None


def _sanitize_interval_unit(raw: object) -> str | None:
    if raw in ("min", "sec"):
        return raw  # type: ignore[return-value]
    return None


def _sanitize_interval_jitter_text(raw: object, *, fallback: str) -> str:
    if not isinstance(raw, str):
        return fallback
    s = raw.strip()[:32]
    if nudge_logic.parse_interval_jitter_seconds_string(s) is None:
        return fallback
    return s


def _sanitize_interval_text(
    raw: object, unit: str, *, fallback: str
) -> str:
    if not isinstance(raw, str):
        return fallback
    s = raw.strip()[:64]
    u: nudge_logic.IntervalUnit = "min" if unit == "min" else "sec"
    if nudge_logic.parse_interval_to_seconds(s, u) is None:
        return fallback
    return s


def _sanitize_pixels_text(raw: object, *, fallback: str) -> str:
    if not isinstance(raw, str):
        return fallback
    s = raw.strip()[:32]
    if nudge_logic.parse_pixels_string(
        s, min_px=nudge_logic.MIN_PIXELS, max_px=nudge_logic.MAX_PIXELS
    ) is None:
        return fallback
    return s


def _sanitize_motion_pattern(raw: object) -> MotionPattern | None:
    if raw in ("horizontal", "circle", "square"):
        return raw  # type: ignore[return-value]
    return None


def _sanitize_path_speed_text(raw: object, *, fallback: str) -> str:
    if not isinstance(raw, str):
        return fallback
    s = raw.strip()[:32]
    if nudge_logic.parse_path_speed_string(
        s,
        min_sp=nudge_logic.MIN_PATH_SPEED,
        max_sp=nudge_logic.MAX_PATH_SPEED,
    ) is None:
        return fallback
    return s


def _sanitize_close_to_tray(raw: object) -> bool | None:
    if isinstance(raw, bool):
        return raw
    return None


def _sanitize_intro_acknowledged(raw: object) -> bool | None:
    if isinstance(raw, bool):
        return raw
    return None


def _sanitize_schedule_window(raw: object) -> bool | None:
    if isinstance(raw, bool):
        return raw
    return None


def _sanitize_auto_check_updates(raw: object) -> bool | None:
    if isinstance(raw, bool):
        return raw
    return None


def _sanitize_hhmm_text(raw: object, *, fallback: str) -> str:
    if not isinstance(raw, str):
        return fallback
    s = raw.strip()[:8]
    if schedule_window.parse_hhmm(s) is None:
        return fallback
    return s


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Return merged config dict; missing or invalid file yields defaults."""
    p = path or default_config_path()
    out = _defaults()
    if not p.is_file():
        return out
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return out
    if not isinstance(raw, dict):
        return out

    lang = _sanitize_lang(raw.get("lang"))
    if lang is not None:
        out["lang"] = lang

    ut = _sanitize_ui_theme(raw.get("ui_theme"))
    if ut is not None:
        out["ui_theme"] = ut

    u = _sanitize_interval_unit(raw.get("interval_unit"))
    if u is not None:
        out["interval_unit"] = u

    fb_interval = out["interval_text"]
    out["interval_text"] = _sanitize_interval_text(
        raw.get("interval_text"), out["interval_unit"], fallback=fb_interval
    )

    fb_jitter = out["interval_jitter_text"]
    out["interval_jitter_text"] = _sanitize_interval_jitter_text(
        raw.get("interval_jitter_text"), fallback=fb_jitter
    )

    fb_pixels = out["pixels_text"]
    out["pixels_text"] = _sanitize_pixels_text(raw.get("pixels_text"), fallback=fb_pixels)

    fb_ps = out["path_speed_text"]
    if "path_speed_text" in raw:
        out["path_speed_text"] = _sanitize_path_speed_text(
            raw.get("path_speed_text"), fallback=fb_ps
        )
    elif "motion_burst_text" in raw:
        out["path_speed_text"] = fb_ps
    else:
        out["path_speed_text"] = fb_ps

    mp = _sanitize_motion_pattern(raw.get("motion_pattern"))
    if mp is not None:
        out["motion_pattern"] = mp

    ctt = _sanitize_close_to_tray(raw.get("close_to_tray"))
    if ctt is not None:
        out["close_to_tray"] = ctt

    if "intro_acknowledged" in raw:
        ia = _sanitize_intro_acknowledged(raw.get("intro_acknowledged"))
        out["intro_acknowledged"] = ia if ia is not None else True
    else:
        out["intro_acknowledged"] = True

    sw = _sanitize_schedule_window(raw.get("schedule_window"))
    if sw is not None:
        out["schedule_window"] = sw
    fb_start = out["schedule_window_start_text"]
    out["schedule_window_start_text"] = _sanitize_hhmm_text(
        raw.get("schedule_window_start_text"), fallback=fb_start
    )
    fb_end = out["schedule_window_end_text"]
    out["schedule_window_end_text"] = _sanitize_hhmm_text(
        raw.get("schedule_window_end_text"), fallback=fb_end
    )
    acu = _sanitize_auto_check_updates(raw.get("auto_check_updates"))
    if acu is not None:
        out["auto_check_updates"] = acu

    out["version"] = CONFIG_VERSION
    return out


def save_config(data: dict[str, Any], path: Path | None = None) -> None:
    """Write known keys to JSON; creates parent directory if needed."""
    p = path or default_config_path()
    base = _defaults()
    ctt = _sanitize_close_to_tray(data.get("close_to_tray"))
    ia = _sanitize_intro_acknowledged(data.get("intro_acknowledged"))
    sw = _sanitize_schedule_window(data.get("schedule_window"))
    acu = _sanitize_auto_check_updates(data.get("auto_check_updates"))
    unit = _sanitize_interval_unit(data.get("interval_unit")) or base["interval_unit"]
    fb_start = base["schedule_window_start_text"]
    fb_end = base["schedule_window_end_text"]
    payload = {
        "version": CONFIG_VERSION,
        "lang": _sanitize_lang(data.get("lang")) or base["lang"],
        "ui_theme": _sanitize_ui_theme(data.get("ui_theme")) or base["ui_theme"],
        "interval_text": _sanitize_interval_text(
            data.get("interval_text"), unit, fallback=base["interval_text"]
        ),
        "interval_unit": unit,
        "interval_jitter_text": _sanitize_interval_jitter_text(
            data.get("interval_jitter_text"), fallback=base["interval_jitter_text"]
        ),
        "pixels_text": _sanitize_pixels_text(
            data.get("pixels_text"), fallback=base["pixels_text"]
        ),
        "path_speed_text": _sanitize_path_speed_text(
            data.get("path_speed_text"), fallback=base["path_speed_text"]
        ),
        "motion_pattern": _sanitize_motion_pattern(data.get("motion_pattern"))
        or base["motion_pattern"],
        "close_to_tray": ctt if ctt is not None else base["close_to_tray"],
        "intro_acknowledged": ia if ia is not None else base["intro_acknowledged"],
        "schedule_window": sw if sw is not None else base["schedule_window"],
        "schedule_window_start_text": _sanitize_hhmm_text(
            data.get("schedule_window_start_text"), fallback=fb_start
        ),
        "schedule_window_end_text": _sanitize_hhmm_text(
            data.get("schedule_window_end_text"), fallback=fb_end
        ),
        "auto_check_updates": acu if acu is not None else base["auto_check_updates"],
    }
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass
