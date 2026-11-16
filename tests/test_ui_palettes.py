"""Palette tokens referenced by the UI must exist in every theme."""

from __future__ import annotations

import re
from pathlib import Path

from mouse_jiggler.app import MouseJigglerApp
from mouse_jiggler.ui_theme import _UI_PALETTES

_PKG = Path(__file__).resolve().parent.parent / "mouse_jiggler"
# Palette entries are copied onto the app as ``self._<KEY>`` (see ThemeMixin._apply_theme_palette).
_TOKEN_RE = re.compile(r"self\._([A-Z][A-Z0-9_]*)\b")


def test_dark_and_light_palettes_define_the_same_tokens() -> None:
    assert set(_UI_PALETTES["dark"]) == set(_UI_PALETTES["light"])


def test_every_referenced_uppercase_attribute_is_defined() -> None:
    palette_keys = set(_UI_PALETTES["dark"])
    class_constants = {
        name[1:] for name in dir(MouseJigglerApp) if name.startswith("_") and name[1:2].isupper()
    }
    missing: dict[str, set[str]] = {}
    for path in sorted(_PKG.glob("*.py")):
        for token in _TOKEN_RE.findall(path.read_text(encoding="utf-8")):
            if token not in palette_keys and token not in class_constants:
                missing.setdefault(path.name, set()).add(token)
    assert missing == {}, f"undefined palette tokens / constants: {missing}"
