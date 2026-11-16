"""Windows "Run at sign-in" registry helpers (HKCU ...\\CurrentVersion\\Run)."""

from __future__ import annotations

import sys
from pathlib import Path

# HKCU\Software\Microsoft\Windows\CurrentVersion\Run (optional boot entry).
_WIN_RUN_REGKEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_WIN_RUN_VALUE_NAME = "TryWorkingHardMouseNudge"


def _windows_autostart_command() -> str:
    """Command line to relaunch the app in tray (matches registry value)."""
    exe = str(Path(sys.executable).resolve())
    if getattr(sys, "frozen", False):
        return f'"{exe}" --start-in-tray'
    return f'"{exe}" -m mouse_jiggler --start-in-tray'


def _windows_run_autostart_read() -> str | None:
    if sys.platform != "win32":
        return None
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _WIN_RUN_REGKEY, 0, winreg.KEY_READ
        ) as key:
            val, _ = winreg.QueryValueEx(key, _WIN_RUN_VALUE_NAME)
        return str(val) if val else None
    except OSError:
        return None


def _windows_run_autoset(enabled: bool) -> None:
    if sys.platform != "win32":
        return
    import winreg

    if enabled:
        cmd = _windows_autostart_command()
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, _WIN_RUN_REGKEY) as k:
            winreg.SetValueEx(
                k, _WIN_RUN_VALUE_NAME, 0, winreg.REG_SZ, cmd
            )
    else:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, _WIN_RUN_REGKEY, 0, winreg.KEY_SET_VALUE
            ) as k:
                winreg.DeleteValue(k, _WIN_RUN_VALUE_NAME)
        except OSError:
            pass


def _windows_run_autostart_active() -> bool:
    if sys.platform != "win32":
        return False
    cur = _windows_run_autostart_read()
    return bool(cur) and cur.strip() == _windows_autostart_command().strip()
