"""Immutable settings snapshot handed from the Tk thread to the nudge worker thread."""

from __future__ import annotations

from dataclasses import dataclass

from .cursor_nudge import ActivityStyle, MotionPattern, NaturalIntensity


@dataclass(frozen=True)
class RunConfig:
    """Settings captured on **Start**; the worker reads only this, never mutable UI state."""

    interval_sec: float
    jitter_sec: float
    pixels: int
    path_speed: int
    motion_duration_seconds: int
    activity_style: ActivityStyle
    pattern: MotionPattern
    natural_intensity: NaturalIntensity
    rare_click: bool
    rare_scroll: bool
