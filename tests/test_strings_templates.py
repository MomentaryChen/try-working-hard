"""Ensure UI string templates still accept the keys used in ``app.py``."""

from __future__ import annotations

import pytest

from mouse_jiggler.strings import STRINGS


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_status_running_template(lang: str) -> None:
    s = STRINGS[lang]["status_running"]
    out = s.format(m=5.5, cd="3:00")
    assert "3:00" in out
    assert len(out) > 10


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_error_templates(lang: str) -> None:
    assert "0.1" in STRINGS[lang]["err_minutes"].format(min=0.1)
    assert STRINGS[lang]["err_pixels"].format(lo=0, hi=500)


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_log_started_template(lang: str) -> None:
    line = STRINGS[lang]["log_started"].format(m=2, sec=120, px=50)
    assert "50" in line
