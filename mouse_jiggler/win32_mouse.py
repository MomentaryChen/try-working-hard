"""Win32 cursor nudge via ctypes."""

from __future__ import annotations

import ctypes
import random
import sys
import time
from ctypes import wintypes

from . import nudge_logic
from .cursor_nudge import MotionInterrupted, MotionPattern, NaturalIntensity, nudge_natural, nudge_trajectory

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


# ``ULONG_PTR`` is pointer-sized (8 bytes on 64-bit), so ``c_size_t`` keeps INPUT at 40 bytes there.
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUTUNION(ctypes.Union):
    # Keyboard and hardware members are only here so the union has the size Windows expects.
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_WHEEL = 0x0800

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002


if IS_WINDOWS:
    user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
    user32.GetCursorPos.restype = wintypes.BOOL
    user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
    user32.SetCursorPos.restype = wintypes.BOOL
    user32.GetLastInputInfo.argtypes = [ctypes.POINTER(LASTINPUTINFO)]
    user32.GetLastInputInfo.restype = wintypes.BOOL
    user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    user32.SendInput.restype = wintypes.UINT
    kernel32.GetTickCount.argtypes = []
    kernel32.GetTickCount.restype = wintypes.DWORD
    kernel32.SetThreadExecutionState.argtypes = [wintypes.DWORD]
    kernel32.SetThreadExecutionState.restype = wintypes.DWORD


def _require_windows() -> None:
    if not IS_WINDOWS:
        raise OSError("win32_mouse is only available on Windows")


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


def _mouse_input(flags: int, *, dx: int = 0, dy: int = 0, data: int = 0) -> INPUT:
    inp = INPUT(type=INPUT_MOUSE)
    # ``mouseData`` is a DWORD; negative wheel deltas are passed as their two's complement.
    inp.mi = MOUSEINPUT(int(dx), int(dy), int(data) & 0xFFFFFFFF, int(flags), 0, 0)
    return inp


def _send_inputs(*inputs: INPUT) -> int:
    """Send mouse events with ``SendInput``; returns how many events were injected."""
    _require_windows()
    arr = (INPUT * len(inputs))(*inputs)
    return int(user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT)))


def _mouse_click_left() -> None:
    _send_inputs(_mouse_input(MOUSEEVENTF_LEFTDOWN))
    time.sleep(0.012)
    _send_inputs(_mouse_input(MOUSEEVENTF_LEFTUP))


def _mouse_wheel(delta: int) -> None:
    _send_inputs(_mouse_input(MOUSEEVENTF_WHEEL, data=int(delta)))


def reset_idle_timer() -> bool:
    """
    Reset the system idle timer with a 1 px relative move and back (``SendInput``).

    ``SetCursorPos`` alone does not update ``GetLastInputInfo``, so screen lock and
    "Away" presence would still trigger. The cursor is put back on its original pixel
    afterwards in case the relative move was clipped at a screen edge.
    """
    if not IS_WINDOWS:
        return False
    start = _get_cursor_xy()
    sent = _send_inputs(
        _mouse_input(MOUSEEVENTF_MOVE, dx=1),
        _mouse_input(MOUSEEVENTF_MOVE, dx=-1),
    )
    if start is not None:
        user32.SetCursorPos(int(start[0]), int(start[1]))
    return sent == 2


def set_keep_awake(enabled: bool) -> bool:
    """
    Ask Windows to keep the system and display awake (``enabled=True``) or clear that request.

    ``SetThreadExecutionState`` is per thread, so call both directions from the same thread.
    It does not stop the screen saver or idle lock on its own; :func:`reset_idle_timer` does.
    Returns ``True`` on success; always ``False`` off Windows.
    """
    if not IS_WINDOWS:
        return False
    flags = ES_CONTINUOUS
    if enabled:
        flags |= ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
    return int(kernel32.SetThreadExecutionState(flags)) != 0


def jiggle_mouse(
    delta_pixels: int,
    pattern: MotionPattern = "horizontal",
    *,
    path_speed: int = 5,
    motion_duration_seconds: int = nudge_logic.DEFAULT_MOTION_DURATION_SECONDS,
    propagate_interrupt: bool = False,
) -> bool:
    """
    Nudge the cursor along a path. ``path_speed`` (0–30) controls how fast the path runs
    (circle and square repeat laps to fill the duration); ``motion_duration_seconds`` is the
    approximate total time for one movement cycle.

    A completed nudge ends with :func:`reset_idle_timer`. When the user moves the mouse
    mid-motion this returns ``False``, or raises :class:`MotionInterrupted` if
    ``propagate_interrupt`` is set.
    """
    _require_windows()
    try:
        completed = nudge_trajectory(
            pattern,
            delta_pixels,
            path_speed,
            motion_duration_seconds=float(motion_duration_seconds),
            get_pos=_get_cursor_xy,
            set_pos=lambda x, y: user32.SetCursorPos(int(x), int(y)),
            sleep=time.sleep,
            clock=time.monotonic,
        )
    except MotionInterrupted:
        if propagate_interrupt:
            raise
        return False
    if completed:
        reset_idle_timer()
    return completed


def jiggle_natural(
    delta_pixels: int,
    *,
    path_speed: int = 5,
    motion_duration_seconds: int = nudge_logic.DEFAULT_MOTION_DURATION_SECONDS,
    intensity: NaturalIntensity = "standard",
    rare_click: bool = False,
    rare_scroll: bool = False,
    propagate_interrupt: bool = False,
) -> bool:
    """
    Irregular micro-moves within ``delta_pixels`` of the start, then optional low-rate
    left click and/or wheel delta at the restored position.

    ``rare_click`` sends a real left click at the current cursor position, which can press
    whatever is under it. Interruption handling matches :func:`jiggle_mouse`.
    """
    rng = random.Random()
    try:
        completed = nudge_natural(
            delta_pixels,
            path_speed,
            motion_duration_seconds=float(motion_duration_seconds),
            intensity=intensity,
            get_pos=_get_cursor_xy,
            set_pos=lambda x, y: user32.SetCursorPos(int(x), int(y)),
            sleep=time.sleep,
            rng=rng,
            clock=time.monotonic,
        )
    except MotionInterrupted:
        if propagate_interrupt:
            raise
        return False
    if not completed:
        return False
    reset_idle_timer()
    if rare_click and rng.random() < 0.12:
        _mouse_click_left()
    if rare_scroll and rng.random() < 0.14:
        _mouse_wheel(int(rng.choice((120, -120, 240, -240))))
    return completed
