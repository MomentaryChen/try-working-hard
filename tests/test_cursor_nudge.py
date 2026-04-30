"""Tests for ``mouse_jiggler.cursor_nudge`` (mocked position IO)."""

from __future__ import annotations

import random
from unittest.mock import MagicMock

from mouse_jiggler.cursor_nudge import nudge_horizontal, nudge_natural, nudge_trajectory


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
