"""Tests for ``mouse_jiggler.cursor_nudge`` (mocked position IO)."""

from __future__ import annotations

from unittest.mock import MagicMock

from mouse_jiggler.cursor_nudge import nudge_horizontal, nudge_trajectory


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
    get_pos = MagicMock(return_value=(100, 200))
    set_pos = MagicMock()
    sleep = MagicMock()
    nudge_horizontal(7, get_pos=get_pos, set_pos=set_pos, sleep=sleep)
    set_pos.assert_has_calls(
        [
            ((107, 200),),
            ((100, 200),),
        ]
    )
    sleep.assert_called_once_with(0.05)


def test_nudge_trajectory_delegates_horizontal() -> None:
    get_pos = MagicMock(return_value=(100, 200))
    set_pos = MagicMock()
    sleep = MagicMock()
    nudge_trajectory("horizontal", 5, 5, get_pos=get_pos, set_pos=set_pos, sleep=sleep)
    set_pos.assert_has_calls(
        [
            ((105, 200),),
            ((100, 200),),
        ]
    )
    assert sleep.call_count == 1
    assert sleep.call_args[0][0] == 0.05


def test_nudge_circle_restores_start() -> None:
    get_pos = MagicMock(return_value=(100, 100))
    set_pos = MagicMock()
    sleep = MagicMock()
    nudge_trajectory("circle", 10, 5, get_pos=get_pos, set_pos=set_pos, sleep=sleep)
    assert get_pos.call_count == 1
    assert set_pos.call_count >= 2
    set_pos.assert_called_with(100, 100)


def test_nudge_square_restores_start() -> None:
    get_pos = MagicMock(return_value=(50, 60))
    set_pos = MagicMock()
    sleep = MagicMock()
    nudge_trajectory("square", 8, 5, get_pos=get_pos, set_pos=set_pos, sleep=sleep)
    assert get_pos.call_count == 1
    set_pos.assert_called_with(50, 60)


def test_nudge_pattern_zero_or_negative_no_set_pos() -> None:
    get_pos = MagicMock(return_value=(1, 2))
    set_pos = MagicMock()
    sleep = MagicMock()
    nudge_trajectory("circle", 0, 5, get_pos=get_pos, set_pos=set_pos, sleep=sleep)
    get_pos.assert_not_called()
    set_pos.assert_not_called()
    sleep.assert_not_called()
