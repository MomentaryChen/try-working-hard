"""Smoke tests for cross-platform ``win32_mouse`` import behavior."""

from __future__ import annotations

import sys

import pytest


def test_import_module_never_exits() -> None:
    import mouse_jiggler.win32_mouse as mod

    assert hasattr(mod, "jiggle_mouse")
    assert hasattr(mod, "get_seconds_since_last_user_input")


def test_jiggle_mouse_zero_is_noop() -> None:
    from mouse_jiggler.win32_mouse import jiggle_mouse

    if sys.platform == "win32":
        jiggle_mouse(0)
    else:
        with pytest.raises(OSError):
            jiggle_mouse(0)


@pytest.mark.skipif(sys.platform != "win32", reason="wintypes sizes differ off Windows")
def test_input_struct_matches_win32_layout() -> None:
    import ctypes

    from mouse_jiggler.win32_mouse import INPUT

    # 4-byte type + padding + MOUSEINPUT (largest member) = 40 bytes on 64-bit, 28 on 32-bit.
    expected = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28
    assert ctypes.sizeof(INPUT) == expected


def test_set_keep_awake_round_trip() -> None:
    from mouse_jiggler.win32_mouse import set_keep_awake

    if sys.platform == "win32":
        assert set_keep_awake(True) is True
        assert set_keep_awake(False) is True
    else:
        assert set_keep_awake(True) is False


def test_get_seconds_since_last_user_input_finite() -> None:
    from mouse_jiggler.win32_mouse import get_seconds_since_last_user_input

    s = get_seconds_since_last_user_input()
    assert isinstance(s, float)
    assert s >= 0.0
    assert s < 1e7
