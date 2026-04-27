"""Tests for Mon–Fri 09:00–18:00 local-time window helpers."""

from __future__ import annotations

from datetime import datetime

import pytest

from mouse_jiggler.schedule_window import is_within_work_window, next_window_start


def test_monday_morning_outside() -> None:
    now = datetime(2026, 4, 27, 8, 30, 0)  # Monday
    assert not is_within_work_window(now)
    n = next_window_start(now)
    assert n == datetime(2026, 4, 27, 9, 0, 0)


def test_monday_during_work() -> None:
    now = datetime(2026, 4, 27, 12, 0, 0)  # Monday
    assert is_within_work_window(now)
    assert next_window_start(now) == now


def test_monday_after_18() -> None:
    now = datetime(2026, 4, 27, 18, 0, 0)  # Monday, end hour boundary (exclusive)
    assert not is_within_work_window(now)
    n = next_window_start(now)
    assert n == datetime(2026, 4, 28, 9, 0, 0)


def test_friday_after_hours_to_monday() -> None:
    now = datetime(2026, 4, 24, 19, 0, 0)  # Friday
    assert not is_within_work_window(now)
    n = next_window_start(now)
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
    assert not is_within_work_window(now)
    n = next_window_start(now)
    assert n == datetime(2026, 4, 27, 9, 0, 0)
