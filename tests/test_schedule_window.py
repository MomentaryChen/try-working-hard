"""Tests for Mon–Fri local-time work window helpers."""

from __future__ import annotations

from datetime import datetime, time

import pytest

from mouse_jiggler.schedule_window import (
    DEFAULT_WORK_END,
    DEFAULT_WORK_START,
    format_hhmm,
    is_within_work_window,
    next_window_start,
    parse_hhmm,
)


def test_parse_hhmm_basic() -> None:
    assert parse_hhmm("09:00") == time(9, 0, 0)
    assert parse_hhmm("9:00") == time(9, 0, 0)
    assert parse_hhmm(" 23:59 ") == time(23, 59, 0)
    assert parse_hhmm("") is None
    assert parse_hhmm("25:00") is None
    assert parse_hhmm("bad") is None


def test_format_hhmm_round_trip() -> None:
    t = time(10, 30, 0)
    assert parse_hhmm(format_hhmm(t)) == t


def test_defaults_match_legacy_window() -> None:
    assert DEFAULT_WORK_START == time(9, 0, 0)
    assert DEFAULT_WORK_END == time(18, 0, 0)


def test_monday_morning_outside() -> None:
    now = datetime(2026, 4, 27, 8, 30, 0)  # Monday
    assert not is_within_work_window(now, DEFAULT_WORK_START, DEFAULT_WORK_END)
    n = next_window_start(now, DEFAULT_WORK_START, DEFAULT_WORK_END)
    assert n == datetime(2026, 4, 27, 9, 0, 0)


def test_monday_during_work() -> None:
    now = datetime(2026, 4, 27, 12, 0, 0)  # Monday
    assert is_within_work_window(now, DEFAULT_WORK_START, DEFAULT_WORK_END)
    assert next_window_start(now, DEFAULT_WORK_START, DEFAULT_WORK_END) == now


def test_monday_after_18() -> None:
    now = datetime(2026, 4, 27, 18, 0, 0)  # Monday, end hour boundary (exclusive)
    assert not is_within_work_window(now, DEFAULT_WORK_START, DEFAULT_WORK_END)
    n = next_window_start(now, DEFAULT_WORK_START, DEFAULT_WORK_END)
    assert n == datetime(2026, 4, 28, 9, 0, 0)


def test_friday_after_hours_to_monday() -> None:
    now = datetime(2026, 4, 24, 19, 0, 0)  # Friday
    assert not is_within_work_window(now, DEFAULT_WORK_START, DEFAULT_WORK_END)
    n = next_window_start(now, DEFAULT_WORK_START, DEFAULT_WORK_END)
    assert n == datetime(2026, 4, 27, 9, 0, 0)  # Monday


@pytest.mark.parametrize(
    "y,m,d,h",
    [
        (2026, 4, 25, 10),  # Saturday
        (2026, 4, 26, 10),  # Sunday
    ],
)
def test_weekend_to_monday(y: int, m: int, d: int, h: int) -> None:
    now = datetime(y, m, d, h, 0, 0)
    assert not is_within_work_window(now, DEFAULT_WORK_START, DEFAULT_WORK_END)
    n = next_window_start(now, DEFAULT_WORK_START, DEFAULT_WORK_END)
    assert n == datetime(2026, 4, 27, 9, 0, 0)


def test_custom_narrow_window() -> None:
    ws, we = time(10, 0, 0), time(11, 0, 0)
    now = datetime(2026, 4, 27, 10, 30, 0)
    assert is_within_work_window(now, ws, we)
    assert not is_within_work_window(datetime(2026, 4, 27, 9, 59, 59), ws, we)
    assert next_window_start(datetime(2026, 4, 27, 9, 30, 0), ws, we) == datetime(
        2026, 4, 27, 10, 0, 0
    )
