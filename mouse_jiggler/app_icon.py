"""Load the shared app icon (``assets/app_icon.png``) for window, tray, and branding."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import Any


def load_app_icon_rgba() -> Any | None:
    """Return a Pillow RGBA image, or ``None`` if the asset is missing."""
    from PIL import Image

    fname = "app_icon.png"
    try:
        ref = files("mouse_jiggler") / "assets" / fname
        if ref.is_file():
            with ref.open("rb") as fp:
                return Image.open(fp).convert("RGBA")
    except (ModuleNotFoundError, OSError, TypeError, ValueError):
        pass
    alt = Path(__file__).resolve().parent / "assets" / fname
    if alt.is_file():
        return Image.open(alt).convert("RGBA")
    return None
