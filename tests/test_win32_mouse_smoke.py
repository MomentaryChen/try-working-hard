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


def test_get_seconds_since_last_user_input_finite() -> None:
    from mouse_jiggler.win32_mouse import get_seconds_since_last_user_input

    s = get_seconds_since_last_user_input()
    assert isinstance(s, float)
    assert s >= 0.0
    assert s < 1e7
