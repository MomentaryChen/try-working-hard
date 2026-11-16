"""Shared UI constants and small widget / packaging helpers for the app modules."""

from __future__ import annotations

import logging
import re
import sys
import tkinter as tk
from importlib.resources import files
from pathlib import Path
from typing import Any, Literal

import customtkinter as ctk

# Primary UI font (Inter). If missing, Tk picks a substitute.
_FONT_INTER = "Inter"
_LOG = logging.getLogger(__name__)

# Pro dark / light: unified corner radius; padding in class (see _UI_PAD).
_R = 12
_R_BTN = _R  # primary / secondary button radius (used by _btn)


def _read_version_from_pyproject() -> str | None:
    """Best-effort fallback: read project version from pyproject.toml."""
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    try:
        content = pyproject_path.read_text(encoding="utf-8")
    except OSError:
        return None

    match = re.search(r'(?m)^\s*version\s*=\s*"([^"]+)"\s*$', content)
    if not match:
        return None
    return match.group(1).strip()

UiTheme = Literal["dark", "light"]


def _try_takefocus(widget: Any, value: int | bool) -> None:
    """Set takefocus on CTk/Tk widgets; ignore if unsupported (keyboard / screen-reader support)."""
    # CTkButton: takefocus is not a valid **kwargs to CTkBaseClass / configure (CustomTkinter 5.x).
    if isinstance(widget, ctk.CTkButton):
        return
    try:
        widget.configure(takefocus=value)  # type: ignore[union-attr]
    except (tk.TclError, AttributeError, TypeError, ValueError):
        pass


def _apply_start_maximized(root: tk.Misc) -> None:
    """Maximize the main window (restored size still comes from minsize/geometry on un-maximize).

    May need to be called again after CustomTkinter layout or after a modal dialog: both can clear
    ``zoomed`` on Windows by applying an explicit ``geometry`` or reparenting focus.
    """
    try:
        if sys.platform == "win32":
            root.state("zoomed")
        else:
            root.attributes("-zoomed", True)
    except tk.TclError:
        pass


def _tint_rgba_image(im: Any, hex_color: str) -> Any:
    """Recolor non-transparent pixels (monochrome Lucide-style PNG assets)."""
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    out = im.convert("RGBA")
    px = out.load()
    w, h = out.size
    for yy in range(h):
        for xx in range(w):
            *_, a = px[xx, yy]
            if a:
                px[xx, yy] = (r, g, b, a)
    return out


def _load_pkg_nav_png(stem: str) -> Any | None:
    """Load sidebar icon PNG from ``mouse_jiggler/assets/icons`` (wheel-safe)."""
    from PIL import Image

    fname = f"{stem}.png"
    try:
        ref = files("mouse_jiggler") / "assets" / "icons" / fname
        if ref.is_file():
            with ref.open("rb") as fp:
                return Image.open(fp).convert("RGBA")
    except (ModuleNotFoundError, OSError, TypeError, ValueError):
        pass
    alt = Path(__file__).resolve().parent / "assets" / "icons" / fname
    if alt.is_file():
        return Image.open(alt).convert("RGBA")
    return None
