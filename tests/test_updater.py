from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

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


# --- Checksum format published by .github/workflows/release.yml -------------------------

_TAG = "v2.1.0"
_PORTABLE = f"try-working-hard-{_TAG}.exe"
_SETUP = f"try-working-hard-setup-{_TAG}.exe"
_CHECKSUMS = f"try-working-hard-{_TAG}-checksums.txt"
_RELEASE_CHECKSUM_TEXT = f"{'a' * 64}  {_PORTABLE}\n{'b' * 64}  {_SETUP}\n"


def _release_assets() -> dict:
    return {
        "tag": _TAG,
        "assets": [
            {"name": _PORTABLE, "url": "https://example.com/portable.exe"},
            {"name": _SETUP, "url": "https://example.com/setup.exe"},
            {"name": _CHECKSUMS, "url": "https://example.com/checksums.txt"},
        ],
    }


def test_choose_checksum_asset_matches_release_workflow_name() -> None:
    asset = updater.choose_checksum_asset(_release_assets())
    assert asset is not None
    assert asset["name"] == _CHECKSUMS


def test_choose_checksum_asset_prefers_tagged_name() -> None:
    release = _release_assets()
    release["assets"].append({"name": "checksums.txt", "url": "https://example.com/old.txt"})
    asset = updater.choose_checksum_asset(release)
    assert asset is not None
    assert asset["name"] == _CHECKSUMS


def test_choose_checksum_asset_accepts_sha256_suffix() -> None:
    release = {
        "assets": [
            {"name": _SETUP, "url": "https://example.com/setup.exe"},
            {"name": f"{_SETUP}.sha256", "url": "https://example.com/setup.exe.sha256"},
        ]
    }
    asset = updater.choose_checksum_asset(release)
    assert asset is not None
    assert asset["name"] == f"{_SETUP}.sha256"


def test_choose_checksum_asset_returns_none_without_checksum_file() -> None:
    release = _release_assets()
    release["assets"] = release["assets"][:2]
    assert updater.choose_checksum_asset(release) is None


def test_parse_sha256_release_file_gives_each_binary_its_own_digest() -> None:
    assert updater.parse_sha256_from_text(_RELEASE_CHECKSUM_TEXT, _PORTABLE) == "a" * 64
    assert updater.parse_sha256_from_text(_RELEASE_CHECKSUM_TEXT, _SETUP) == "b" * 64


def test_parse_sha256_requires_exact_filename() -> None:
    # A name that only contains the target (or is contained in it) must not match.
    txt = f"{'c' * 64}  evil-{_SETUP}\n{'d' * 64}  {_SETUP}.bak\n"
    assert updater.parse_sha256_from_text(txt, _SETUP) is None
    assert updater.parse_sha256_from_text(_RELEASE_CHECKSUM_TEXT, "setup.exe") is None


def test_parse_sha256_handles_bom_crlf_case_and_binary_marker() -> None:
    txt = chr(0xFEFF) + f"{'E' * 64} *{_SETUP.upper()}\r\n"
    assert updater.parse_sha256_from_text(txt, _SETUP) == "e" * 64


def test_parse_sha256_handles_bsd_style_and_paths() -> None:
    bsd = f"SHA256 ({_SETUP}) = {'f' * 64}\n"
    assert updater.parse_sha256_from_text(bsd, _SETUP) == "f" * 64
    with_dir = f"{'1' * 64}  dist/{_SETUP}\n"
    assert updater.parse_sha256_from_text(with_dir, _SETUP) == "1" * 64


def test_parse_sha256_returns_none_when_missing() -> None:
    assert updater.parse_sha256_from_text("", _SETUP) is None
    assert updater.parse_sha256_from_text(f"{'a' * 64}  {_PORTABLE}\n", _SETUP) is None


# --- verify_installer_checksum ---------------------------------------------------------


def _write_installer(tmp_path: Path) -> tuple[Path, str]:
    path = tmp_path / _SETUP
    path.write_bytes(b"installer bytes")
    return path, hashlib.sha256(b"installer bytes").hexdigest()


def test_verify_installer_checksum_returns_digest_on_match(tmp_path: Path) -> None:
    path, digest = _write_installer(tmp_path)
    text = f"{'a' * 64}  {_PORTABLE}\n{digest}  {_SETUP}\n"
    out = updater.verify_installer_checksum(
        path, installer_name=_SETUP, checksum_url="https://x/c.txt", fetch=lambda _u: text
    )
    assert out == digest


def test_verify_installer_checksum_requires_checksum_asset(tmp_path: Path) -> None:
    path, _ = _write_installer(tmp_path)
    with pytest.raises(updater.ChecksumError) as ei:
        updater.verify_installer_checksum(
            path, installer_name=_SETUP, checksum_url="", fetch=lambda _u: ""
        )
    assert ei.value.reason == "missing_asset"


def test_verify_installer_checksum_fetch_failure(tmp_path: Path) -> None:
    path, _ = _write_installer(tmp_path)

    def _boom(_url: str) -> str:
        raise RuntimeError("Could not fetch checksum file.")

    with pytest.raises(updater.ChecksumError) as ei:
        updater.verify_installer_checksum(
            path, installer_name=_SETUP, checksum_url="https://x/c.txt", fetch=_boom
        )
    assert ei.value.reason == "fetch_failed"


def test_verify_installer_checksum_missing_digest_line(tmp_path: Path) -> None:
    path, _ = _write_installer(tmp_path)
    text = f"{'a' * 64}  {_PORTABLE}\n"
    with pytest.raises(updater.ChecksumError) as ei:
        updater.verify_installer_checksum(
            path, installer_name=_SETUP, checksum_url="https://x/c.txt", fetch=lambda _u: text
        )
    assert ei.value.reason == "missing_digest"


def test_verify_installer_checksum_mismatch(tmp_path: Path) -> None:
    path, digest = _write_installer(tmp_path)
    with pytest.raises(updater.ChecksumError) as ei:
        updater.verify_installer_checksum(
            path,
            installer_name=_SETUP,
            checksum_url="https://x/c.txt",
            fetch=lambda _u: _RELEASE_CHECKSUM_TEXT,
        )
    assert ei.value.reason == "mismatch"
    assert ei.value.expected == "b" * 64
    assert ei.value.actual == digest


def test_discard_file_removes_and_tolerates_missing(tmp_path: Path) -> None:
    path, _ = _write_installer(tmp_path)
    updater.discard_file(path)
    assert not path.exists()
    updater.discard_file(path)
