"""Tests for local JSON config load/save."""

from __future__ import annotations

import json
from pathlib import Path

from mouse_jiggler import local_config


def test_load_missing_file_returns_defaults(tmp_path: Path) -> None:
    p = tmp_path / "nope.json"
    cfg = local_config.load_config(p)
    assert cfg["lang"] == "en"
    assert cfg["interval_text"] == "300"
    assert cfg["interval_jitter_text"] == "0"
    assert cfg["pixels_text"] == "100"
    assert cfg["path_speed_text"] == "5"
    assert cfg["motion_duration_seconds_text"] == "10"
    assert cfg["motion_pattern"] == "horizontal"
    assert cfg["activity_style"] == "pattern"
    assert cfg["natural_intensity"] == "standard"
    assert cfg["natural_rare_click"] is False
    assert cfg["natural_rare_scroll"] is False
    assert cfg["natural_preset_selected"] == "standard"
    assert cfg["natural_presets"]["conservative"]["interval_text"] == "300"
    assert cfg["natural_presets"]["standard"]["pixels_text"] == "100"
    assert cfg["natural_presets"]["aggressive"]["natural_rare_click"] is True
    assert cfg["ui_theme"] == "dark"
    assert cfg["close_to_tray"] is False
    assert cfg["intro_acknowledged"] is False
    assert cfg["schedule_window"] is False
    assert cfg["schedule_window_start_text"] == "09:00"
    assert cfg["schedule_window_end_text"] == "18:00"
    assert cfg["auto_check_updates"] is True
    assert cfg["schedule_window_segments_text"] == "09:00-18:00"
    assert cfg["schedule_include_weekends"] is False
    assert cfg["schedule_cron_text"] == ""


def test_round_trip(tmp_path: Path) -> None:
    p = tmp_path / "config.json"
    local_config.save_config(
        {
            "lang": "en",
            "ui_theme": "light",
            "interval_text": "30",
            "interval_jitter_text": "45",
            "pixels_text": "50",
            "path_speed_text": "8",
            "motion_pattern": "circle",
            "natural_intensity": "strong",
            "close_to_tray": True,
            "auto_check_updates": False,
            "natural_preset_selected": "aggressive",
            "natural_presets": {
                "aggressive": {
                    "interval_text": "90",
                    "interval_unit": "sec",
                    "interval_jitter_text": "10",
                    "pixels_text": "150",
                    "path_speed_text": "9",
                    "motion_duration_seconds_text": "20",
                    "natural_rare_click": True,
                    "natural_rare_scroll": False,
                }
            },
        },
        path=p,
    )
    cfg = local_config.load_config(p)
    assert cfg["lang"] == "en"
    assert cfg["ui_theme"] == "light"
    assert cfg["interval_text"] == "30"
    assert cfg["interval_jitter_text"] == "45"
    assert cfg["pixels_text"] == "50"
    assert cfg["path_speed_text"] == "8"
    assert cfg["motion_pattern"] == "circle"
    assert cfg["natural_intensity"] == "strong"
    assert cfg["close_to_tray"] is True
    assert cfg["auto_check_updates"] is False
    assert cfg["natural_preset_selected"] == "aggressive"
    assert cfg["natural_presets"]["aggressive"]["pixels_text"] == "150"
    assert cfg["natural_presets"]["aggressive"]["natural_rare_click"] is True
    assert cfg["intro_acknowledged"] is False


def test_round_trip_natural_pixels_above_500(tmp_path: Path) -> None:
    p = tmp_path / "config.json"
    local_config.save_config(
        {
            "interval_text": "30",
            "interval_unit": "sec",
            "activity_style": "natural",
            "pixels_text": "800",
        },
        path=p,
    )
    cfg = local_config.load_config(p)
    assert cfg["activity_style"] == "natural"
    assert cfg["pixels_text"] == "800"
    assert cfg["natural_intensity"] == "standard"


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
                "interval_jitter_text": "99999",
                "pixels_text": "9999",
                "path_speed_text": "99",
                "motion_pattern": "triangle",
                "close_to_tray": "yes",
                "ui_theme": "sepia",
                "auto_check_updates": "sometimes",
                "schedule_window_segments_text": "09:00-12:00,11:00-13:00",
                "schedule_include_weekends": "yes",
                "schedule_cron_text": "bad cron expression",
                "natural_preset_selected": "hyper",
                "natural_presets": {"standard": {"pixels_text": "9999"}},
            }
        ),
        encoding="utf-8",
    )
    cfg = local_config.load_config(p)
    assert cfg["lang"] == "en"
    assert cfg["ui_theme"] == "dark"
    assert cfg["interval_text"] == "300"
    assert cfg["interval_jitter_text"] == "0"
    assert cfg["pixels_text"] == "100"
    assert cfg["path_speed_text"] == "5"
    assert cfg["motion_pattern"] == "horizontal"
    assert cfg["close_to_tray"] is False
    assert cfg["auto_check_updates"] is True
    assert cfg["intro_acknowledged"] is True
    assert cfg["schedule_window_segments_text"] == "09:00-18:00"
    assert cfg["schedule_include_weekends"] is False
    assert cfg["schedule_cron_text"] == ""
    assert cfg["natural_preset_selected"] == "standard"
    assert cfg["natural_presets"]["standard"]["pixels_text"] == "100"
