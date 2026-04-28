from __future__ import annotations

from mouse_jiggler import updater


def test_is_newer_version_semver_like() -> None:
    assert updater.is_newer_version("v1.2.0", "1.1.9") is True
    assert updater.is_newer_version("v1.2.0", "1.2.0") is False
    assert updater.is_newer_version("1.2.0", "v1.3.0") is False
