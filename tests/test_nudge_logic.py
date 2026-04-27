"""Tests for ``mouse_jiggler.nudge_logic`` (parsing, countdown, log trim)."""

from __future__ import annotations

import pytest

from mouse_jiggler import nudge_logic


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("5", 5.0),
        ("0.1", 0.1),
        ("1,5", 1.5),
        ("  10  ", 10.0),
    ],
)
def test_parse_minutes_valid(raw: str, expected: float) -> None:
    assert nudge_logic.parse_minutes_string(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["", "  ", "abc", "0.09", "-1", "nan", "inf"],
)
def test_parse_minutes_invalid(raw: str) -> None:
    assert nudge_logic.parse_minutes_string(raw) is None


def test_parse_minutes_custom_floor() -> None:
    assert nudge_logic.parse_minutes_string("2", min_minutes=2.0) == 2.0
    assert nudge_logic.parse_minutes_string("1.9", min_minutes=2.0) is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("6", 6.0),
        ("60", 60.0),
        ("6,5", 6.5),
        ("  300  ", 300.0),
    ],
)
def test_parse_seconds_valid(raw: str, expected: float) -> None:
    assert nudge_logic.parse_seconds_string(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["", "  ", "abc", "5.9", "-1", "nan", "inf"],
)
def test_parse_seconds_invalid(raw: str) -> None:
    assert nudge_logic.parse_seconds_string(raw) is None


def test_parse_interval_to_seconds() -> None:
    assert nudge_logic.parse_interval_to_seconds("2", "min") == 120.0
    assert nudge_logic.parse_interval_to_seconds("30", "sec") == 30.0
    assert nudge_logic.parse_interval_to_seconds("0.05", "min") is None
    assert nudge_logic.parse_interval_to_seconds("3", "sec") is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0", 0),
        ("100", 100),
        ("500", 500),
        (" 42 ", 42),
        ("3.0", 3),
    ],
)
def test_parse_pixels_valid(raw: str, expected: int) -> None:
    assert nudge_logic.parse_pixels_string(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["", "abc", "-1", "501", "1000", "nan", "inf"],
)
def test_parse_pixels_invalid(raw: str) -> None:
    assert nudge_logic.parse_pixels_string(raw) is None


def test_parse_pixels_custom_bounds() -> None:
    assert nudge_logic.parse_pixels_string("5", min_px=5, max_px=5) == 5
    assert nudge_logic.parse_pixels_string("4", min_px=5, max_px=10) is None


@pytest.mark.parametrize(
    ("total_sec", "expected"),
    [
        (0, "0:00"),
        (59, "0:59"),
        (60, "1:00"),
        (3599, "59:59"),
        (3600, "1:00:00"),
        (3661, "1:01:01"),
    ],
)
def test_format_countdown_display(total_sec: int, expected: str) -> None:
    assert nudge_logic.format_countdown_display(total_sec) == expected


def test_format_countdown_clamps_negative() -> None:
    assert nudge_logic.format_countdown_display(-5) == "0:00"


@pytest.mark.parametrize(
    ("remaining", "expected"),
    [
        (0.0, "0:00"),
        (0.4, "0:00"),
        (0.5, "0:01"),  # int(0.5 + 0.5) == 1
        (59.4, "0:59"),
        (59.5, "1:00"),
    ],
)
def test_remaining_seconds_to_countdown_display(remaining: float, expected: str) -> None:
    assert nudge_logic.remaining_seconds_to_countdown_display(remaining) == expected


def test_remaining_negative_treated_as_zero() -> None:
    assert nudge_logic.remaining_seconds_to_countdown_display(-10.0) == "0:00"


@pytest.mark.parametrize(
    ("total", "max_lines", "drop"),
    [
        (10, 48, 0),
        (49, 48, 1),
        (50, 48, 2),
    ],
)
def test_log_lines_to_delete_from_top(total: int, max_lines: int, drop: int) -> None:
    assert nudge_logic.log_lines_to_delete_from_top(total, max_lines) == drop
