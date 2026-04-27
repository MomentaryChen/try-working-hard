"""
Periodic mouse nudge (idle prevention) — Windows only.
GUI: CustomTkinter; mouse: ctypes; system tray: pystray + Pillow.
"""

from __future__ import annotations

from importlib.metadata import version as package_version

from .app import MouseJigglerApp, main

try:
    __version__ = package_version("try-working-hard")
except Exception:  # noqa: S110
    __version__ = "1.0.0"

__all__ = ["MouseJigglerApp", "__version__", "main"]
