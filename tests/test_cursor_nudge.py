"""Tests for ``mouse_jiggler.cursor_nudge`` (mocked position IO)."""

from __future__ import annotations

import random
from unittest.mock import MagicMock

import pytest

from mouse_jiggler.cursor_nudge import (
    MotionInterrupted,
    nudge_horizontal,
    nudge_natural,
    nudge_trajectory,
)


def _mock_pos_io(x: int, y: int) -> tuple[MagicMock, MagicMock]:
    """``get_pos`` / ``set_pos`` mocks that share state so interrupt checks match tests."""
    state = [x, y]

    def _set(nx: int, ny: int) -> None:
        state[0], state[1] = int(nx), int(ny)

    get_pos = MagicMock(side_effect=lambda: tuple(state))
    set_pos = MagicMock(side_effect=_set)
    return get_pos, set_pos


def test_nudge_horizontal_zero_no_io() -> None:
    get_pos = MagicMock()
    set_pos = MagicMock()
    sleep = MagicMock()
    nudge_horizontal(0, get_pos=get_pos, set_pos=set_pos, sleep=sleep)
    get_pos.assert_not_called()
    set_pos.assert_not_called()
    sleep.assert_not_called()


def test_nudge_horizontal_negative_no_io() -> None:
    get_pos = MagicMock()
    set_pos = MagicMock()
    sleep = MagicMock()
    nudge_horizontal(-5, get_pos=get_pos, set_pos=set_pos, sleep=sleep)
    get_pos.assert_not_called()


def test_nudge_horizontal_failed_get_pos() -> None:
    get_pos = MagicMock(return_value=None)
    set_pos = MagicMock()
    sleep = MagicMock()
    nudge_horizontal(10, get_pos=get_pos, set_pos=set_pos, sleep=sleep)
    get_pos.assert_called_once()
    set_pos.assert_not_called()
    sleep.assert_not_called()


def test_nudge_horizontal_moves_and_restores() -> None:
    get_pos, set_pos = _mock_pos_io(100, 200)
    sleep = MagicMock()
    nudge_horizontal(
        7,
        get_pos=get_pos,
        set_pos=set_pos,
        sleep=sleep,
        motion_duration_seconds=0.05,
    )
    set_pos.assert_has_calls(
        [
            ((107, 200),),
            ((100, 200),),
        ]
    )
    total_sleep = sum(c.args[0] for c in sleep.call_args_list)
    assert abs(float(total_sleep) - 0.05) < 1e-9


def test_nudge_trajectory_delegates_horizontal() -> None:
    get_pos, set_pos = _mock_pos_io(100, 200)
    sleep = MagicMock()
    nudge_trajectory(
        "horizontal",
        5,
        5,
        get_pos=get_pos,
        set_pos=set_pos,
        sleep=sleep,
        motion_duration_seconds=0.05,
    )
    set_pos.assert_has_calls(
        [
            ((105, 200),),
            ((100, 200),),
        ]
    )
    total_sleep = sum(c.args[0] for c in sleep.call_args_list)
    assert abs(float(total_sleep) - 0.05) < 1e-9


def test_nudge_circle_restores_start() -> None:
    get_pos, set_pos = _mock_pos_io(100, 100)
    sleep = MagicMock()
    nudge_trajectory(
        "circle",
        10,
        5,
        get_pos=get_pos,
        set_pos=set_pos,
        sleep=sleep,
        motion_duration_seconds=0.05,
    )
    assert get_pos.call_count >= 1
    assert set_pos.call_count >= 2
    set_pos.assert_called_with(100, 100)


def test_nudge_square_restores_start() -> None:
    get_pos, set_pos = _mock_pos_io(50, 60)
    sleep = MagicMock()
    nudge_trajectory("square", 8, 5, get_pos=get_pos, set_pos=set_pos, sleep=sleep)
    assert get_pos.call_count >= 1
    set_pos.assert_called_with(50, 60)


def test_nudge_pattern_zero_or_negative_no_set_pos() -> None:
    get_pos = MagicMock(return_value=(1, 2))
    set_pos = MagicMock()
    sleep = MagicMock()
    nudge_trajectory("circle", 0, 5, get_pos=get_pos, set_pos=set_pos, sleep=sleep)
    get_pos.assert_not_called()
    set_pos.assert_not_called()
    sleep.assert_not_called()


def test_nudge_natural_restores_start() -> None:
    get_pos, set_pos = _mock_pos_io(100, 200)
    sleep = MagicMock()
    rng = random.Random(42)
    nudge_natural(
        24,
        5,
        get_pos=get_pos,
        set_pos=set_pos,
        sleep=sleep,
        rng=rng,
    )
    set_pos.assert_called_with(100, 200)


class _FakeClock:
    """Fake ``sleep`` that only adds up the requested time."""

    def __init__(self) -> None:
        self.total = 0.0

    def __call__(self, seconds: float) -> None:
        self.total += float(seconds)


def _run_trajectory(pattern: str, size: int, speed: int, duration: float) -> tuple[int, float]:
    get_pos, set_pos = _mock_pos_io(500, 500)
    clock = _FakeClock()
    nudge_trajectory(
        pattern,  # type: ignore[arg-type]
        size,
        speed,
        motion_duration_seconds=duration,
        get_pos=get_pos,
        set_pos=set_pos,
        sleep=clock,
    )
    set_pos.assert_called_with(500, 500)
    return set_pos.call_count, clock.total


@pytest.mark.parametrize("pattern", ["circle", "square"])
def test_path_speed_changes_laps_but_not_duration(pattern: str) -> None:
    slow_calls, slow_total = _run_trajectory(pattern, 10, 1, 10.0)
    fast_calls, fast_total = _run_trajectory(pattern, 10, 20, 10.0)
    # Faster speed traces more laps (more cursor updates) in the same duration.
    assert fast_calls > 3 * slow_calls
    # Whole laps are rounded to fill the duration, so either side lands within half a lap.
    assert abs(slow_total - 10.0) < 1.5
    assert abs(fast_total - 10.0) < 0.5


def test_circle_traces_whole_laps() -> None:
    radius = 10
    points_per_lap = max(24, min(180, radius * 4))
    calls, _total = _run_trajectory("circle", radius, 5, 10.0)
    # n * laps path points plus the final restore to the start.
    assert (calls - 1) % points_per_lap == 0
    assert (calls - 1) // points_per_lap > 1


def test_path_speed_matters_when_one_lap_exceeds_duration() -> None:
    # Large circle + short duration: at least one lap, so a slow speed overruns the duration
    # instead of being silently sped up to match it.
    slow_calls, slow_total = _run_trajectory("circle", 60, 0, 1.0)
    fast_calls, fast_total = _run_trajectory("circle", 60, 30, 1.0)
    assert slow_total > 3 * fast_total
    assert fast_calls >= slow_calls


def test_square_ends_each_lap_at_start() -> None:
    get_pos, set_pos = _mock_pos_io(50, 60)
    nudge_trajectory(
        "square",
        8,
        20,
        motion_duration_seconds=5.0,
        get_pos=get_pos,
        set_pos=set_pos,
        sleep=_FakeClock(),
    )
    points = [c.args for c in set_pos.call_args_list]
    returns_to_start = sum(1 for pt in points if pt == (50, 60))
    assert returns_to_start > 2
    assert all(50 <= x <= 58 and 60 <= y <= 68 for x, y in points)


def test_multi_lap_circle_still_interrupts() -> None:
    state = [100, 100]
    calls = {"n": 0}

    def _set(nx: int, ny: int) -> None:
        state[0], state[1] = int(nx), int(ny)
        calls["n"] += 1

    def _get() -> tuple[int, int]:
        # After a few updates the "user" drags the cursor far away.
        if calls["n"] >= 30:
            return (900, 900)
        return (state[0], state[1])

    with pytest.raises(MotionInterrupted):
        nudge_trajectory(
            "circle",
            10,
            20,
            motion_duration_seconds=10.0,
            get_pos=_get,
            set_pos=_set,
            sleep=_FakeClock(),
        )
    assert calls["n"] < 40


def _run_natural(speed: int, duration: float, seed: int = 7) -> tuple[int, float]:
    get_pos, set_pos = _mock_pos_io(300, 300)
    clock = _FakeClock()
    nudge_natural(
        40,
        speed,
        motion_duration_seconds=duration,
        get_pos=get_pos,
        set_pos=set_pos,
        sleep=clock,
        rng=random.Random(seed),
    )
    set_pos.assert_called_with(300, 300)
    return set_pos.call_count, clock.total


def test_natural_speed_changes_density_not_duration() -> None:
    slow_calls, slow_total = _run_natural(1, 10.0)
    fast_calls, fast_total = _run_natural(20, 10.0)
    assert fast_calls > 3 * slow_calls
    # Step delays are normalised to the duration (small per-sleep floor aside).
    assert abs(slow_total - 10.0) < 0.2
    assert abs(fast_total - 10.0) < 0.2


def test_natural_step_count_is_bounded() -> None:
    calls, total = _run_natural(30, 60.0)
    # Step count is clamped, so a long fast run cannot explode into unbounded updates.
    assert calls <= 4000 * 3 + 1
    assert abs(total - 60.0) < 0.5


def test_clock_deadline_stops_new_laps_when_overhead_accumulates() -> None:
    get_pos, set_pos = _mock_pos_io(500, 500)
    now = [0.0]

    def _sleep(seconds: float) -> None:
        # Simulate a real sleep that overshoots by 2 ms every call.
        now[0] += float(seconds) + 0.002

    nudge_trajectory(
        "circle",
        10,
        30,
        motion_duration_seconds=3.0,
        get_pos=get_pos,
        set_pos=set_pos,
        sleep=_sleep,
        clock=lambda: now[0],
    )
    set_pos.assert_called_with(500, 500)
    # Without the deadline the overshoot would add about 40 % here; stop within one lap.
    lap_seconds = 40 * (0.02 * 6 / 31 + 0.002)
    assert now[0] < 3.0 + lap_seconds + 1e-9


def _mock_pos_io_with_user_move(x: int, y: int) -> tuple[MagicMock, MagicMock, MagicMock]:
    """Like ``_mock_pos_io`` but the user moves the cursor during the first sleep slice."""
    state = [x, y]

    def _set(nx: int, ny: int) -> None:
        state[0], state[1] = int(nx), int(ny)

    def _sleep(_sec: float) -> None:
        if sleep.call_count == 1:
            state[0] += 50
            state[1] += 50

    get_pos = MagicMock(side_effect=lambda: tuple(state))
    set_pos = MagicMock(side_effect=_set)
    sleep = MagicMock(side_effect=_sleep)
    return get_pos, set_pos, sleep


@pytest.mark.parametrize("pattern", ["horizontal", "circle", "square"])
def test_pattern_interrupted_by_user_move_stops_before_next_step(pattern: str) -> None:
    get_pos, set_pos, sleep = _mock_pos_io_with_user_move(100, 100)
    with pytest.raises(MotionInterrupted):
        nudge_trajectory(
            pattern,  # type: ignore[arg-type]
            10,
            5,
            get_pos=get_pos,
            set_pos=set_pos,
            sleep=sleep,
            motion_duration_seconds=0.05,
        )
    # Only the first step was commanded; the move during its sleep aborted the rest.
    assert set_pos.call_count == 1
    assert sleep.call_count == 1


def test_natural_interrupted_by_user_move_stops_before_next_step() -> None:
    get_pos, set_pos, sleep = _mock_pos_io_with_user_move(100, 200)
    with pytest.raises(MotionInterrupted):
        nudge_natural(
            24,
            5,
            get_pos=get_pos,
            set_pos=set_pos,
            sleep=sleep,
            rng=random.Random(42),
        )
    assert set_pos.call_count == 1
    assert sleep.call_count == 1
