"""Win32 cursor nudge via ctypes."""

from __future__ import annotations

import ctypes
import math
import random
import sys
import time
from ctypes import wintypes

from . import nudge_logic
from .cursor_nudge import MotionPattern, nudge_natural, nudge_trajectory

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
else:
    user32 = None
    kernel32 = None


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


if IS_WINDOWS:
    user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
    user32.GetCursorPos.restype = wintypes.BOOL
    user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
    user32.SetCursorPos.restype = wintypes.BOOL
    user32.GetLastInputInfo.argtypes = [ctypes.POINTER(LASTINPUTINFO)]
    user32.GetLastInputInfo.restype = wintypes.BOOL
    user32.mouse_event.argtypes = [
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_ulong,
    ]
    user32.mouse_event.restype = wintypes.BOOL
    kernel32.GetTickCount.argtypes = []
    kernel32.GetTickCount.restype = wintypes.DWORD


def _require_windows() -> None:
    if not IS_WINDOWS:
        raise OSError("win32_mouse is only available on Windows")

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_WHEEL = 0x0800


def get_seconds_since_last_user_input() -> float:
    """
    Seconds since last keyboard, mouse, or other user input, per ``GetLastInputInfo``.

    If the call fails, returns ``0.0`` (treated as active) so a bad state does not fire nudges
    in a loop.
    """
    if not IS_WINDOWS:
        return 0.0
    li = LASTINPUTINFO()
    li.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not user32.GetLastInputInfo(ctypes.byref(li)):
        return 0.0
    tick = int(kernel32.GetTickCount()) & 0xFFFFFFFF
    last = int(li.dwTime) & 0xFFFFFFFF
    delta_ms = (tick - last) & 0xFFFFFFFF
    return float(delta_ms) / 1000.0


def _get_cursor_xy() -> tuple[int, int] | None:
    _require_windows()
    pt = POINT()
    if not user32.GetCursorPos(ctypes.byref(pt)):
        return None
    return int(pt.x), int(pt.y)


def _mouse_click_left() -> None:
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.012)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def _mouse_wheel(delta: int) -> None:
    user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, ctypes.c_uint(int(delta)), 0)


def _motion_duration_mult(percent: int) -> float:
    lo = float(nudge_logic.MIN_MOTION_DURATION_PERCENT)
    hi = float(nudge_logic.MAX_MOTION_DURATION_PERCENT)
    p = float(percent)
    if not math.isfinite(p):
        return 1.0
    p = max(lo, min(hi, p))
    return p / 100.0


def jiggle_mouse(
    delta_pixels: int,
    pattern: MotionPattern = "horizontal",
    *,
    path_speed: int = 5,
    motion_duration_percent: int = nudge_logic.DEFAULT_MOTION_DURATION_PERCENT,
) -> None:
    """
    Nudge the cursor along a path. ``path_speed`` (1–10) controls how fast the path runs;
    ``motion_duration_percent`` scales every step delay (100 = default).
    """
    _require_windows()
    nudge_trajectory(
        pattern,
        delta_pixels,
        path_speed,
        motion_duration_mult=_motion_duration_mult(motion_duration_percent),
        get_pos=_get_cursor_xy,
        set_pos=lambda x, y: user32.SetCursorPos(int(x), int(y)),
        sleep=time.sleep,
    )


def jiggle_natural(
    delta_pixels: int,
    *,
    path_speed: int = 5,
    motion_duration_percent: int = nudge_logic.DEFAULT_MOTION_DURATION_PERCENT,
    rare_click: bool = False,
    rare_scroll: bool = False,
) -> None:
    """
    Irregular micro-moves within ``delta_pixels`` of the start, then optional low-rate
    left click and/or wheel delta at the restored position.
    """
    rng = random.Random()
    nudge_natural(
        delta_pixels,
        path_speed,
        motion_duration_mult=_motion_duration_mult(motion_duration_percent),
        get_pos=_get_cursor_xy,
        set_pos=lambda x, y: user32.SetCursorPos(int(x), int(y)),
        sleep=time.sleep,
        rng=rng,
    )
    if rare_click and rng.random() < 0.12:
        _mouse_click_left()
    if rare_scroll and rng.random() < 0.14:
        _mouse_wheel(int(rng.choice((120, -120, 240, -240))))
