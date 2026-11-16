"""Single-instance guard for Windows (named mutex + named "show window" event).

The first process owns a named mutex for its whole lifetime. A second process finds
the mutex already exists, signals a named auto-reset event and exits. The running
instance polls that event from a Tk ``after`` loop and shows its own window.

This is more robust than ``FindWindowW`` + ``ShowWindow`` from the second process:
the window title is localized and versioned, and calling ``ShowWindow`` on a
withdrawn Tk root from outside would leave Tk's state (and the tray) out of sync.

Nothing here touches Windows APIs at import time, and every function is a no-op on
other platforms.
"""

from __future__ import annotations

import sys
from typing import Any

MUTEX_NAME = "Local\\try-working-hard-single-instance"
SHOW_EVENT_NAME = "Local\\try-working-hard-show-window"
ERROR_ALREADY_EXISTS = 183
WAIT_OBJECT_0 = 0
ASFW_ANY = -1
SW_RESTORE = 9


class InstanceGuard:
    """Handles owned by the primary instance; keep a reference for the process lifetime."""

    def __init__(self, kernel32: Any = None, mutex: Any = None, show_event: Any = None) -> None:
        self._kernel32 = kernel32
        self._mutex = mutex
        self._show_event = show_event

    def show_requested(self) -> bool:
        """Return True (once) if another launch asked this instance to show its window."""
        if self._kernel32 is None or not self._show_event:
            return False
        try:
            return self._kernel32.WaitForSingleObject(self._show_event, 0) == WAIT_OBJECT_0
        except OSError:
            return False


def _kernel32() -> Any:
    import ctypes
    from ctypes import wintypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    k32.CreateMutexW.restype = wintypes.HANDLE
    k32.CreateEventW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
    k32.CreateEventW.restype = wintypes.HANDLE
    k32.SetEvent.argtypes = [wintypes.HANDLE]
    k32.SetEvent.restype = wintypes.BOOL
    k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    k32.WaitForSingleObject.restype = wintypes.DWORD
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    k32.CloseHandle.restype = wintypes.BOOL
    return k32


def acquire() -> InstanceGuard | None:
    """Claim the single-instance mutex.

    Returns an :class:`InstanceGuard` when this process should run (it is the first
    instance, the platform is not Windows, or the mutex could not be created, in
    which case we fail open). Returns ``None`` when another instance is already
    running; that instance has then been asked to show its window and the caller
    should exit.
    """
    if sys.platform != "win32":
        return InstanceGuard()
    import ctypes

    try:
        k32 = _kernel32()
        # Auto-reset event, created (or opened) by both sides so neither depends on
        # the other having started first.
        show_event = k32.CreateEventW(None, False, False, SHOW_EVENT_NAME)
        mutex = k32.CreateMutexW(None, False, MUTEX_NAME)
        already_running = ctypes.get_last_error() == ERROR_ALREADY_EXISTS
    except (AttributeError, OSError):
        return InstanceGuard()
    if not mutex:
        return InstanceGuard(k32, None, show_event)
    if not already_running:
        return InstanceGuard(k32, mutex, show_event)

    # Another instance owns the mutex: let it take the foreground, then ask it to show.
    try:
        ctypes.windll.user32.AllowSetForegroundWindow(ASFW_ANY)
    except (AttributeError, OSError):
        pass
    if show_event:
        k32.SetEvent(show_event)
        k32.CloseHandle(show_event)
    k32.CloseHandle(mutex)
    return None


def bring_to_front(hwnd: int) -> None:
    """Restore and foreground a top-level window (best effort, Windows only)."""
    if sys.platform != "win32" or not hwnd:
        return
    import ctypes
    from ctypes import wintypes

    try:
        user32 = ctypes.windll.user32
        h = wintypes.HWND(hwnd)
        # Only restore a minimized window: SW_RESTORE would also un-maximize a
        # maximized one, and the app starts maximized.
        if user32.IsIconic(h):
            user32.ShowWindow(h, SW_RESTORE)
        user32.SetForegroundWindow(h)
    except (AttributeError, OSError):
        pass
