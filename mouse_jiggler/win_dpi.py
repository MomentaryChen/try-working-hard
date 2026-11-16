"""Process DPI awareness for Windows, set before Tk creates any window.

CustomTkinter already makes the process per-monitor DPI aware, but only inside
``ctk.CTk()``, i.e. *after* ``tkinter.Tk()`` has created its root window and measured
the screen while the process was still DPI unaware. Calling
:func:`enable_dpi_awareness` first moves that switch to the very start of ``main``.

Why per-monitor **v1** and not ``DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2``:
CustomTkinter's own ``ScalingTracker.activate_high_dpi_awareness`` documents that
PMv2 makes ``resizable(False, False)`` windows keep growing on a monitor with a
different scale (a Tk bug), and this app has several such dialogs. PMv1 is the
exact level CustomTkinter ends up at today, so its scaling factor (read from
``GetDpiForMonitor``) is unchanged and nothing is scaled twice.

Side effect handled by :func:`keep_legacy_tk_scaling`: when Tk starts in an already
DPI-aware process it sees the real DPI and sets ``tk scaling`` to e.g. 2.0 at 150 %
instead of 1.333. That would enlarge everything Tk sizes in points (plain ``tk``
widgets with point fonts, matplotlib's device pixel ratio) on top of CustomTkinter's
own scaling, so the previous 96-DPI value is restored right after the root exists.
"""

from __future__ import annotations

import sys
from typing import Any

PROCESS_PER_MONITOR_DPI_AWARE = 2
_LEGACY_TK_SCALING = 96.0 / 72.0  # pixels per point Tk uses when started DPI unaware

_applied = False


def enable_dpi_awareness() -> bool:
    """Make the process per-monitor DPI aware; return True if this call changed it.

    Tries ``shcore.SetProcessDpiAwareness(2)`` (Windows 8.1+), then
    ``user32.SetProcessDPIAware()`` (system aware, Vista+). Returns False on
    non-Windows, on failure, or when awareness was already set (for example by an
    application manifest), in which case nothing else should be adjusted.
    """
    global _applied
    if sys.platform != "win32":
        return False
    import ctypes

    try:
        hr = ctypes.windll.shcore.SetProcessDpiAwareness(PROCESS_PER_MONITOR_DPI_AWARE)
        # S_OK only; E_ACCESSDENIED means awareness was already set elsewhere.
        _applied = hr == 0
        return _applied
    except (AttributeError, OSError):
        pass
    try:
        _applied = bool(ctypes.windll.user32.SetProcessDPIAware())
    except (AttributeError, OSError):
        _applied = False
    return _applied


def keep_legacy_tk_scaling(root: Any) -> None:
    """Restore the ``tk scaling`` Tk would have picked without early DPI awareness.

    Call right after creating the Tk root. Does nothing unless
    :func:`enable_dpi_awareness` actually changed the process awareness.
    """
    if not _applied:
        return
    try:
        root.tk.call("tk", "scaling", _LEGACY_TK_SCALING)
    except Exception:  # noqa: S110 - best effort; keep the default scaling
        pass
