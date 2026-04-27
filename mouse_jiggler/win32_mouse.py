"""Win32 cursor nudge via ctypes."""

from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes

from .cursor_nudge import MotionPattern, nudge_trajectory

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


def jiggle_mouse(
    delta_pixels: int, pattern: MotionPattern = "horizontal", *, path_speed: int = 5
) -> None:
    """
    Nudge the cursor along a path. ``path_speed`` (1–10) controls how fast the path runs.
    """
    nudge_trajectory(
        pattern,
        delta_pixels,
        path_speed,
        get_pos=_get_cursor_xy,
        set_pos=lambda x, y: user32.SetCursorPos(int(x), int(y)),
        sleep=time.sleep,
    )
