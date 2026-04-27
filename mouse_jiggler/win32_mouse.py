"""Win32 cursor nudge via ctypes."""

from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes

from .cursor_nudge import nudge_horizontal

if sys.platform != "win32":
    print("This application supports Windows only.")
    sys.exit(1)

user32 = ctypes.windll.user32


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
user32.GetCursorPos.restype = wintypes.BOOL
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.SetCursorPos.restype = wintypes.BOOL


def _get_cursor_xy() -> tuple[int, int] | None:
    pt = POINT()
    if not user32.GetCursorPos(ctypes.byref(pt)):
        return None
    return int(pt.x), int(pt.y)


def jiggle_mouse(delta_pixels: int) -> None:
    """Move cursor right by delta_pixels horizontally, then restore. If delta is 0 or less, do nothing."""
    nudge_horizontal(
        delta_pixels,
        get_pos=_get_cursor_xy,
        set_pos=lambda x, y: user32.SetCursorPos(int(x), int(y)),
        sleep=time.sleep,
    )
