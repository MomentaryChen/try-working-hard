from __future__ import annotations

from mouse_jiggler import updater


def test_is_newer_version_semver_like() -> None:
    assert updater.is_newer_version("v1.2.0", "1.1.9") is True
    assert updater.is_newer_version("v1.2.0", "1.2.0") is False
    assert updater.is_newer_version("1.2.0", "v1.3.0") is False


def test_summarize_release_notes_from_markdown_body() -> None:
    body = """
## What's new
- Added version diff summary in update banner.
- Added rollback guidance for safer upgrade decisions.
- Fixed minor spacing.
"""
    out = updater.summarize_release_notes(body, max_lines=2, max_chars=120)
    assert "Added version diff summary" in out
    assert "rollback guidance" in out
