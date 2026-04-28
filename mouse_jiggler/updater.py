"""Utilities for checking newer versions from GitHub releases."""

from __future__ import annotations

import json
import re
from urllib import error, request

LATEST_RELEASE_API = "https://api.github.com/repos/MomentaryChen/try-working-hard/releases/latest"


def _version_tuple(raw: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", raw)
    if not nums:
        return (0,)
    return tuple(int(n) for n in nums[:4])


def is_newer_version(latest: str, current: str) -> bool:
    return _version_tuple(latest) > _version_tuple(current)


def fetch_latest_release(timeout_sec: float = 4.0) -> dict[str, str]:
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
    if not tag:
        raise RuntimeError("Missing release tag in response.")
    return {"tag": tag, "url": html_url}
