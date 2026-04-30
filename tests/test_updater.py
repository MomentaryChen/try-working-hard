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


def test_choose_windows_installer_asset_prefers_tagged_project_exe() -> None:
    release = {
        "tag": "v1.2.0",
        "assets": [
            {"name": "notes.txt", "url": "https://example.com/notes.txt"},
            {"name": "other-tool-v1.2.0.exe", "url": "https://example.com/other.exe"},
            {
                "name": "try-working-hard-v1.2.0.exe",
                "url": "https://example.com/try-working-hard-v1.2.0.exe",
            },
        ],
    }
    asset = updater.choose_windows_installer_asset(release)
    assert asset is not None
    assert asset["name"] == "try-working-hard-v1.2.0.exe"


def test_choose_windows_installer_asset_prefers_setup_over_plain_exe() -> None:
    release = {
        "tag": "v1.2.0",
        "assets": [
            {
                "name": "try-working-hard-v1.2.0.exe",
                "url": "https://example.com/portable.exe",
            },
            {
                "name": "try-working-hard-setup-v1.2.0.exe",
                "url": "https://example.com/setup.exe",
            },
        ],
    }
    asset = updater.choose_windows_installer_asset(release)
    assert asset is not None
    assert asset["name"] == "try-working-hard-setup-v1.2.0.exe"


def test_choose_windows_installer_asset_prefers_newer_setup_when_tag_not_in_names() -> None:
    """If several setup exes share the same score, pick the highest version in the filename."""
    release = {
        "tag": "v9.9.9",
        "assets": [
            {
                "name": "try-working-hard-setup-v1.0.0.exe",
                "url": "https://example.com/old-setup.exe",
            },
            {
                "name": "try-working-hard-setup-v2.0.0.exe",
                "url": "https://example.com/new-setup.exe",
            },
        ],
    }
    asset = updater.choose_windows_installer_asset(release)
    assert asset is not None
    assert asset["name"] == "try-working-hard-setup-v2.0.0.exe"


def test_choose_windows_installer_asset_prefers_filename_matching_tag_over_newer_mismatch() -> None:
    release = {
        "tag": "v1.2.0",
        "assets": [
            {
                "name": "try-working-hard-setup-v1.2.0.exe",
                "url": "https://example.com/correct-setup.exe",
            },
            {
                "name": "try-working-hard-setup-v9.0.0.exe",
                "url": "https://example.com/stray-setup.exe",
            },
        ],
    }
    asset = updater.choose_windows_installer_asset(release)
    assert asset is not None
    assert asset["name"] == "try-working-hard-setup-v1.2.0.exe"


def test_choose_windows_installer_asset_returns_none_without_exe() -> None:
    release = {
        "tag": "v1.2.0",
        "assets": [{"name": "source.zip", "url": "https://example.com/source.zip"}],
    }
    assert updater.choose_windows_installer_asset(release) is None


def test_choose_checksum_asset_prefers_checksum_files() -> None:
    release = {
        "assets": [
            {"name": "try-working-hard-v1.2.0.exe", "url": "https://example.com/app.exe"},
            {"name": "checksums.txt", "url": "https://example.com/checksums.txt"},
        ]
    }
    asset = updater.choose_checksum_asset(release)
    assert asset is not None
    assert asset["name"] == "checksums.txt"


def test_parse_sha256_from_text_extracts_target_digest() -> None:
    txt = (
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa  other.exe\n"
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb  try-working-hard-v1.2.0.exe\n"
    )
    out = updater.parse_sha256_from_text(txt, "try-working-hard-v1.2.0.exe")
    assert out == "b" * 64
