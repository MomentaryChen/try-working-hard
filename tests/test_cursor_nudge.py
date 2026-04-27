"""Tests for ``mouse_jiggler.cursor_nudge`` (mocked position IO)."""

from __future__ import annotations

from unittest.mock import MagicMock

from mouse_jiggler.cursor_nudge import nudge_horizontal


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
