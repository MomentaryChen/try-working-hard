"""
Periodic mouse nudge (idle prevention) — Windows only.
GUI: CustomTkinter; mouse: ctypes; system tray: pystray + Pillow.
"""

from __future__ import annotations

from .app import MouseJigglerApp, main

__all__ = ["MouseJigglerApp", "main"]
