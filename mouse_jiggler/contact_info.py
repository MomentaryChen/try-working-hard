"""Maintainer contact: prefer local ``git config user.name`` / ``user.email``, else bundled defaults."""

from __future__ import annotations

import subprocess
import sys

_DEFAULT_NAME = "MomentaryChen"
_DEFAULT_EMAIL = "zzser15963@gmail.com"


def _git_config(key: str) -> str | None:
    if getattr(sys, "frozen", False):
        return None
    try:
        r = subprocess.run(
            ["git", "config", "--get", key],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if r.returncode == 0 and (s := r.stdout.strip()):
            return s
    except (OSError, subprocess.TimeoutExpired, ValueError):
        pass
    return None


def maintainer_contact() -> tuple[str, str]:
    """Return (display name, email) for the Contact section in Settings."""
    name = _git_config("user.name") or _DEFAULT_NAME
    email = _git_config("user.email") or _DEFAULT_EMAIL
    return (name, email)
