# -*- coding: utf-8 -*-
"""Generate app_icon.png and app.ico for Windows exe / UI (run from repo root: uv run python packaging/generate_icons.py)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw

# Match MouseJigglerApp accent (_ACCENT)
ACCENT = (114, 137, 218, 255)
WHITE = (245, 245, 245, 255)
MOTION = (234, 236, 255, 220)


def _rounded_rect_mask(size: int, radius: int) -> Image.Image:
    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    return m


def draw_app_icon(size: int = 256) -> Image.Image:
    """Rounded tile with pointer + motion dots (mouse nudge theme)."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    r = int(size * 0.18)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=r, fill=ACCENT)

    s = size / 256.0
    # Pointer (simplified arrow), white
    tip = (int(118 * s), int(72 * s))
    d.polygon(
        [
            tip,
            (int(118 * s), int(168 * s)),
            (int(138 * s), int(138 * s)),
            (int(188 * s), int(128 * s)),
        ],
        fill=WHITE,
    )
    d.polygon(
        [
            (int(138 * s), int(138 * s)),
            (int(118 * s), int(168 * s)),
            (int(158 * s), int(158 * s)),
        ],
        fill=(200, 210, 245, 255),
    )

    # Motion hint: three small circles trailing left
    for i, (cx, cy, rad) in enumerate(
        [
            (int(56 * s), int(118 * s), int(10 * s)),
            (int(38 * s), int(100 * s), int(7 * s)),
            (int(28 * s), int(82 * s), int(5 * s)),
        ]
    ):
        d.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), fill=MOTION)

    mask = _rounded_rect_mask(size, r)
    img.paste(layer, (0, 0), mask)
    return img


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    assets = root / "mouse_jiggler" / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    png_path = assets / "app_icon.png"
    ico_path = Path(__file__).resolve().parent / "app.ico"

    master = draw_app_icon(256)
    master.save(png_path, "PNG")
    # Windows shell: multiple sizes in one .ico
    master.save(
        ico_path,
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"Wrote {png_path}")
    print(f"Wrote {ico_path}")


if __name__ == "__main__":
    try:
        main()
    except OSError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
