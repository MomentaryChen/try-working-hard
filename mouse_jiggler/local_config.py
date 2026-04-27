"""Load and save app preferences to a local JSON file (Windows: %APPDATA%\\try-working-hard)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

from . import nudge_logic

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
        "interval_text": str(int(nudge_logic.DEFAULT_MINUTES)),
        "pixels_text": str(nudge_logic.DEFAULT_PIXELS),
        "close_to_tray": False,
        "intro_acknowledged": False,
    }


def _sanitize_lang(raw: object) -> Lang | None:
    if raw in ("zh", "en"):
        return raw  # type: ignore[return-value]
    return None


def _sanitize_interval_text(raw: object, *, fallback: str) -> str:
    if not isinstance(raw, str):
        return fallback
    s = raw.strip()[:64]
    if nudge_logic.parse_minutes_string(s, min_minutes=nudge_logic.MIN_MINUTES) is None:
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


def _sanitize_close_to_tray(raw: object) -> bool | None:
    if isinstance(raw, bool):
        return raw
    return None


def _sanitize_intro_acknowledged(raw: object) -> bool | None:
    if isinstance(raw, bool):
        return raw
    return None


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

    fb_interval = out["interval_text"]
    out["interval_text"] = _sanitize_interval_text(raw.get("interval_text"), fallback=fb_interval)

    fb_pixels = out["pixels_text"]
    out["pixels_text"] = _sanitize_pixels_text(raw.get("pixels_text"), fallback=fb_pixels)

    ctt = _sanitize_close_to_tray(raw.get("close_to_tray"))
    if ctt is not None:
        out["close_to_tray"] = ctt

    if "intro_acknowledged" in raw:
        ia = _sanitize_intro_acknowledged(raw.get("intro_acknowledged"))
        # Invalid value: treat as already seen so we do not loop popups.
        out["intro_acknowledged"] = ia if ia is not None else True
    else:
        # Older config files without the key: do not show intro on upgrade.
        out["intro_acknowledged"] = True

    out["version"] = CONFIG_VERSION
    return out


def save_config(data: dict[str, Any], path: Path | None = None) -> None:
    """Write known keys to JSON; creates parent directory if needed."""
    p = path or default_config_path()
    base = _defaults()
    ctt = _sanitize_close_to_tray(data.get("close_to_tray"))
    ia = _sanitize_intro_acknowledged(data.get("intro_acknowledged"))
    payload = {
        "version": CONFIG_VERSION,
        "lang": _sanitize_lang(data.get("lang")) or base["lang"],
        "interval_text": _sanitize_interval_text(
            data.get("interval_text"), fallback=base["interval_text"]
        ),
        "pixels_text": _sanitize_pixels_text(
            data.get("pixels_text"), fallback=base["pixels_text"]
        ),
        "close_to_tray": ctt if ctt is not None else base["close_to_tray"],
        "intro_acknowledged": ia if ia is not None else base["intro_acknowledged"],
    }
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass
