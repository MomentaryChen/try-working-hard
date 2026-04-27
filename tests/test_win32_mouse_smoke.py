"""Optional smoke test on Windows (importing ``win32_mouse`` exits immediately on other OSes)."""

from __future__ import annotations

import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="win32_mouse imports only on Windows")


def test_jiggle_mouse_zero_is_noop() -> None:
    from mouse_jiggler.win32_mouse import jiggle_mouse

    jiggle_mouse(0)


def test_get_seconds_since_last_user_input_finite() -> None:
    from mouse_jiggler.win32_mouse import get_seconds_since_last_user_input

    s = get_seconds_since_last_user_input()
    assert isinstance(s, float)
    assert s >= 0.0
    assert s < 1e7
