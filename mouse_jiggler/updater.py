"""Utilities for checking newer versions and downloading release assets."""

from __future__ import annotations

import json
import hashlib
import re
from pathlib import Path
from typing import Any, Callable, Literal
from urllib import error, request

LATEST_RELEASE_API = "https://api.github.com/repos/MomentaryChen/try-working-hard/releases/latest"


class DownloadCancelledError(RuntimeError):
    """Raised when a download is cancelled by user request."""


def _version_tuple(raw: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", raw)
    if not nums:
        return (0,)
    return tuple(int(n) for n in nums[:4])


def is_newer_version(latest: str, current: str) -> bool:
    return _version_tuple(latest) > _version_tuple(current)


def summarize_release_notes(raw: str, *, max_lines: int = 2, max_chars: int = 180) -> str:
    """Return a short one-liner summary from GitHub release notes."""
    text = (raw or "").strip()
    if not text:
        return ""
    lines = []
    for line in text.splitlines():
        clean = line.strip()
        if not clean:
            continue
        if clean.startswith("#"):
            continue
        clean = re.sub(r"^[-*#>\s]+", "", clean).strip()
        if clean:
            lines.append(clean)
        if len(lines) >= max_lines:
            break
    if not lines:
        return ""
    summary = " ".join(lines)
    if len(summary) <= max_chars:
        return summary
    cut = summary[: max_chars - 1].rstrip()
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return f"{cut}…"


def fetch_latest_release(timeout_sec: float = 4.0) -> dict[str, Any]:
    req = request.Request(
        LATEST_RELEASE_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "try-working-hard-update-checker",
        },
    )
    try:
        with request.urlopen(req, timeout=timeout_sec) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
    except (error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Could not fetch latest release info.") from exc
    if not isinstance(data, dict):
        raise RuntimeError("Invalid release response.")
    tag = str(data.get("tag_name") or "").strip()
    html_url = str(data.get("html_url") or "").strip()
    body = str(data.get("body") or "").strip()
    name = str(data.get("name") or "").strip()
    if not tag:
        raise RuntimeError("Missing release tag in response.")
    assets_raw = data.get("assets")
    assets: list[dict[str, str]] = []
    if isinstance(assets_raw, list):
        for item in assets_raw:
            if not isinstance(item, dict):
                continue
            asset_name = str(item.get("name") or "").strip()
            asset_url = str(item.get("browser_download_url") or "").strip()
            if asset_name and asset_url:
                assets.append({"name": asset_name, "url": asset_url})
    return {"tag": tag, "url": html_url, "name": name, "body": body, "assets": assets}


def choose_windows_installer_asset(release: dict[str, Any]) -> dict[str, str] | None:
    """Pick the best-matching Windows installer (.exe) from release assets.

    Prefer assets whose filename contains the release ``tag``, then a setup-style
    name, then the highest version-like tuple parsed from the filename. This
    avoids picking an older stray ``*-setup-*.exe`` when scores tied only on
    length (GitHub releases should not mix versions, but mis-uploads happen).
    """
    tag = str(release.get("tag") or "").strip().lower()
    assets = release.get("assets")
    if not isinstance(assets, list):
        return None
    candidates: list[dict[str, str]] = []
    for item in assets:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        url = str(item.get("url") or "").strip()
        if not name or not url:
            continue
        if not name.lower().endswith(".exe"):
            continue
        candidates.append({"name": name, "url": url})
    if not candidates:
        return None

    def _rank(asset: dict[str, str]) -> tuple[int, int, int, tuple[int, ...], int]:
        lower = asset["name"].lower()
        tag_hit = 1 if (tag and tag in lower) else 0
        setup_hit = 1 if ("installer" in lower or "setup" in lower) else 0
        project_hit = 1 if "try-working-hard" in lower else 0
        ver = _version_tuple(lower)
        # Prefer shorter names only when everything else ties (stable, deterministic).
        return (tag_hit, setup_hit, project_hit, ver, -len(lower))

    return max(candidates, key=_rank)


def choose_checksum_asset(release: dict[str, Any]) -> dict[str, str] | None:
    """Pick the checksum asset from release assets.

    The release workflow publishes ``try-working-hard-<tag>-checksums.txt`` (one
    ``<sha256>  <filename>`` line per binary). ``*.sha256`` / ``*.sha256.txt`` files are
    accepted as well. Prefer names that contain the release ``tag``, then the shortest.
    """
    tag = str(release.get("tag") or "").strip().lower()
    assets = release.get("assets")
    if not isinstance(assets, list):
        return None
    candidates: list[dict[str, str]] = []
    for item in assets:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        url = str(item.get("url") or "").strip()
        if not name or not url:
            continue
        lower = name.lower()
        if lower.endswith(".sha256") or lower.endswith(".sha256.txt") or "checksums" in lower:
            candidates.append({"name": name, "url": url})
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda a: (0 if (tag and tag in a["name"].lower()) else 1, len(a["name"])),
    )


_BOM = chr(0xFEFF)

# ``<digest>  <name>`` (GNU text mode) or ``<digest> *<name>`` (GNU binary mode).
_GNU_LINE = re.compile(r"^([0-9a-fA-F]{64})\s+\*?(.+)$")
# ``SHA256 (<name>) = <digest>`` (BSD style).
_BSD_LINE = re.compile(r"^SHA256\s*\((.+)\)\s*=\s*([0-9a-fA-F]{64})$", re.IGNORECASE)


def parse_sha256_from_text(checksum_text: str, target_filename: str) -> str | None:
    """Extract the sha256 digest for ``target_filename`` from checksum file content.

    The filename must match exactly (case-insensitive, any leading path ignored);
    a name that merely contains the target is not accepted.
    """
    target_lower = target_filename.strip().lower()
    if not target_lower:
        return None
    for raw_line in checksum_text.splitlines():
        # A UTF-8 BOM may precede the first line (e.g. Windows PowerShell 5 ``-Encoding utf8``).
        line = raw_line.strip().lstrip(_BOM).strip()
        if not line:
            continue
        m = _GNU_LINE.match(line)
        if m:
            digest, name = m.group(1), m.group(2)
        else:
            m = _BSD_LINE.match(line)
            if not m:
                continue
            name, digest = m.group(1), m.group(2)
        name = name.strip().replace("\\", "/").rsplit("/", 1)[-1].lower()
        if name == target_lower:
            return digest.lower()
    return None


ChecksumFailure = Literal["missing_asset", "fetch_failed", "missing_digest", "mismatch"]


class ChecksumError(RuntimeError):
    """Raised when a downloaded installer cannot be verified against the release checksum."""

    def __init__(self, reason: ChecksumFailure, *, expected: str = "", actual: str = "") -> None:
        super().__init__(f"Installer checksum verification failed: {reason}")
        self.reason: ChecksumFailure = reason
        self.expected = expected
        self.actual = actual


def verify_installer_checksum(
    path: Path,
    *,
    installer_name: str,
    checksum_url: str,
    fetch: Callable[[str], str] | None = None,
) -> str:
    """Verify ``path`` against the release checksum file and return the verified digest.

    Raises :class:`ChecksumError` when there is no checksum asset, the checksum file
    cannot be fetched, it has no line for ``installer_name``, or the digest differs.
    The caller is responsible for deleting the file when this raises.
    """
    if not checksum_url.strip():
        raise ChecksumError("missing_asset")
    fetcher = fetch if fetch is not None else fetch_text
    try:
        checksum_text = fetcher(checksum_url)
    except Exception as exc:
        raise ChecksumError("fetch_failed") from exc
    expected = parse_sha256_from_text(checksum_text, installer_name)
    if not expected:
        raise ChecksumError("missing_digest")
    actual = sha256_file(path)
    if actual.lower() != expected.lower():
        raise ChecksumError("mismatch", expected=expected, actual=actual)
    return actual


def discard_file(path: Path) -> None:
    """Delete ``path`` if it exists; ignore errors (best effort cleanup)."""
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def fetch_text(url: str, *, timeout_sec: float = 10.0) -> str:
    """Fetch URL and decode as UTF-8 text."""
    req = request.Request(
        url,
        headers={
            "Accept": "text/plain,*/*",
            "User-Agent": "try-working-hard-updater",
        },
    )
    try:
        with request.urlopen(req, timeout=timeout_sec) as resp:  # noqa: S310
            return resp.read().decode("utf-8", errors="replace")
    except (error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError("Could not fetch checksum file.") from exc


def sha256_file(path: Path) -> str:
    """Return SHA256 digest for a local file."""
    h = hashlib.sha256()
    with path.open("rb") as rf:
        while True:
            chunk = rf.read(128 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def download_file(
    *,
    url: str,
    target_path: Path,
    progress_cb: Callable[[int, int | None], None] | None = None,
    cancel_cb: Callable[[], bool] | None = None,
    timeout_sec: float = 20.0,
) -> Path:
    """Download a file and optionally report progress as (bytes_done, bytes_total)."""
    req = request.Request(
        url,
        headers={
            "Accept": "application/octet-stream,*/*",
            "User-Agent": "try-working-hard-updater",
        },
    )
    tmp_path = target_path.with_suffix(target_path.suffix + ".part")
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with request.urlopen(req, timeout=timeout_sec) as resp:  # noqa: S310
            total_raw = resp.headers.get("Content-Length")
            total = int(total_raw) if total_raw and total_raw.isdigit() else None
            downloaded = 0
            with tmp_path.open("wb") as wf:
                while True:
                    if cancel_cb is not None and cancel_cb():
                        raise DownloadCancelledError("Download was cancelled.")
                    chunk = resp.read(64 * 1024)
                    if not chunk:
                        break
                    wf.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb is not None:
                        progress_cb(downloaded, total)
        tmp_path.replace(target_path)
        if progress_cb is not None:
            progress_cb(target_path.stat().st_size, target_path.stat().st_size)
        return target_path
    except (error.URLError, TimeoutError, OSError, DownloadCancelledError) as exc:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass
        if isinstance(exc, DownloadCancelledError):
            raise
        raise RuntimeError("Could not download installer.") from exc
