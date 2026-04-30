"""Utilities for checking newer versions and downloading release assets."""

from __future__ import annotations

import json
import hashlib
import re
from pathlib import Path
from typing import Any, Callable
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
    """Pick the best-matching Windows installer (.exe) from release assets."""
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

    def _score(asset: dict[str, str]) -> tuple[int, int]:
        lower = asset["name"].lower()
        score = 0
        if "try-working-hard" in lower:
            score += 3
        if tag and tag in lower:
            score += 2
        if "installer" in lower or "setup" in lower:
            score += 4
        return (score, -len(lower))

    return sorted(candidates, key=_score, reverse=True)[0]


def choose_checksum_asset(release: dict[str, Any]) -> dict[str, str] | None:
    """Pick an optional checksum asset from release assets."""
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
    return sorted(candidates, key=lambda a: len(a["name"]))[0]


def parse_sha256_from_text(checksum_text: str, target_filename: str) -> str | None:
    """Extract sha256 digest for a target filename from checksum file content."""
    target_lower = target_filename.strip().lower()
    for raw_line in checksum_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = re.search(r"\b([a-fA-F0-9]{64})\b", line)
        if not m:
            continue
        digest = m.group(1).lower()
        if target_lower in line.lower():
            return digest
    return None


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
