"""Tests for local JSON config load/save."""

from __future__ import annotations

import json
from pathlib import Path

from mouse_jiggler import local_config


def test_load_missing_file_returns_defaults(tmp_path: Path) -> None:
    p = tmp_path / "nope.json"
    cfg = local_config.load_config(p)
    assert cfg["lang"] == "en"
    assert cfg["interval_text"] == "5"
    assert cfg["pixels_text"] == "100"
    assert cfg["path_speed_text"] == "5"
    assert cfg["motion_pattern"] == "horizontal"
    assert cfg["ui_theme"] == "dark"
    assert cfg["close_to_tray"] is False
    assert cfg["intro_acknowledged"] is False


def test_round_trip(tmp_path: Path) -> None:
    p = tmp_path / "config.json"
    local_config.save_config(
        {
            "lang": "en",
            "ui_theme": "light",
            "interval_text": "0.5",
            "pixels_text": "50",
            "path_speed_text": "8",
            "motion_pattern": "circle",
            "close_to_tray": True,
        },
        path=p,
    )
    cfg = local_config.load_config(p)
    assert cfg["lang"] == "en"
    assert cfg["ui_theme"] == "light"
    assert cfg["interval_text"] == "0.5"
    assert cfg["pixels_text"] == "50"
    assert cfg["path_speed_text"] == "8"
    assert cfg["motion_pattern"] == "circle"
    assert cfg["close_to_tray"] is True
    assert cfg["intro_acknowledged"] is False


def test_invalid_json_ignored(tmp_path: Path) -> None:
    p = tmp_path / "config.json"
    p.write_text("{not json", encoding="utf-8")
    cfg = local_config.load_config(p)
    assert cfg["lang"] == "en"


def test_invalid_values_fallback(tmp_path: Path) -> None:
    p = tmp_path / "config.json"
    p.write_text(
        json.dumps(
            {
                "lang": "xx",
                "interval_text": "0.01",
                "pixels_text": "9999",
                "path_speed_text": "99",
                "motion_pattern": "triangle",
                "close_to_tray": "yes",
                "ui_theme": "sepia",
            }
        ),
        encoding="utf-8",
    )
    cfg = local_config.load_config(p)
    assert cfg["lang"] == "en"
    assert cfg["ui_theme"] == "dark"
    assert cfg["interval_text"] == "5"
    assert cfg["pixels_text"] == "100"
    assert cfg["path_speed_text"] == "5"
    assert cfg["motion_pattern"] == "horizontal"
    assert cfg["close_to_tray"] is False
    assert cfg["intro_acknowledged"] is True
