"""Ensure UI string templates still accept the keys used in ``app.py``."""

from __future__ import annotations

import pytest

from mouse_jiggler.strings import STRINGS


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_status_running_min_template(lang: str) -> None:
    s = STRINGS[lang]["status_running_min"]
    out = s.format(v=5.5, cd="3:00")
    assert "3:00" in out
    assert len(out) > 10


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_status_running_sec_template(lang: str) -> None:
    s = STRINGS[lang]["status_running_sec"]
    out = s.format(v=30.0, cd="0:12")
    assert "0:12" in out
    assert len(out) > 10


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_error_templates(lang: str) -> None:
    assert "0.1" in STRINGS[lang]["err_minutes"].format(min=0.1)
    assert STRINGS[lang]["err_seconds"].format(min=6.0)
    assert STRINGS[lang]["err_pixels"].format(lo=0, hi=500)


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_log_started_min_template(lang: str) -> None:
    line = STRINGS[lang]["log_started_min"].format(
        v=2, sec=120, pat="circle", px=50, ps=7
    )
    assert "50" in line
    assert "7" in line


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_log_started_sec_template(lang: str) -> None:
    line = STRINGS[lang]["log_started_sec"].format(
        v=30, pat="line", px=50, ps=5
    )
    assert "50" in line
    assert "5" in line


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_path_speed_templates(lang: str) -> None:
    assert STRINGS[lang]["err_path_speed"].format(lo=1, hi=10)
    assert STRINGS[lang]["path_speed_hint"].format(lo=1, hi=10)


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_a11y_help_body_includes_version(lang: str) -> None:
    body = STRINGS[lang]["a11y_help_body"].format(version="1.0.0")
    assert "1.0.0" in body
    assert "F1" in body


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_intro_body_includes_version(lang: str) -> None:
    body = STRINGS[lang]["intro_body"].format(version="2.0.0")
    assert "2.0.0" in body
