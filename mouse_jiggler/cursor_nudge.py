"""Cursor motion with injectable position IO (testable without Win32)."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Literal

MotionPattern = Literal["horizontal", "circle", "square"]

# Pause between samples along a path (keeps input rate reasonable).
_TRAJECTORY_STEP_SLEEP = 0.02


def nudge_horizontal(
    delta_pixels: int,
    *,
    get_pos: Callable[[], tuple[int, int] | None],
    set_pos: Callable[[int, int], object],
    sleep: Callable[[float], object],
) -> None:
    """
    Move cursor right by ``delta_pixels``, pause, then restore. No-op if ``delta_pixels <= 0``
    or ``get_pos`` fails.
    """
    d = int(delta_pixels)
    if d <= 0:
        return
    pos = get_pos()
    if pos is None:
        return
    x, y = pos
    set_pos(x + d, y)
    sleep(0.05)
    set_pos(x, y)


def nudge_trajectory(
    pattern: MotionPattern,
    pixels: int,
    *,
    get_pos: Callable[[], tuple[int, int] | None],
    set_pos: Callable[[int, int], object],
    sleep: Callable[[float], object],
) -> None:
    """
    Move the cursor along a path and return to the starting position.

    - ``horizontal``: same as :func:`nudge_horizontal` (``pixels`` = horizontal delta).
    - ``circle``: ``pixels`` = radius in pixels; path is a full circle around the start point.
    - ``square``: ``pixels`` = edge length; path is a square with the start point as the top-left
      corner, moving clockwise.
    """
    if pattern == "horizontal":
        nudge_horizontal(
            pixels, get_pos=get_pos, set_pos=set_pos, sleep=sleep
        )
        return

    r = int(pixels)
    if r <= 0:
        return
    pos = get_pos()
    if pos is None:
        return
    sx, sy = pos

    if pattern == "circle":
        _trace_circle(sx, sy, r, set_pos=set_pos, sleep=sleep)
        set_pos(sx, sy)
        return

    if pattern == "square":
        _trace_square(sx, sy, r, set_pos=set_pos, sleep=sleep)
        set_pos(sx, sy)


def _trace_circle(
    cx: int,
    cy: int,
    radius: int,
    *,
    set_pos: Callable[[int, int], object],
    sleep: Callable[[float], object],
) -> None:
    # Resolution scales slightly with radius; bounded for very large values.
    n = max(12, min(72, max(radius, 1) * 2))
    for k in range(n):
        theta = 2.0 * math.pi * k / n
        x = int(round(cx + radius * math.cos(theta)))
        y = int(round(cy + radius * math.sin(theta)))
        set_pos(x, y)
        sleep(_TRAJECTORY_STEP_SLEEP)


def _trace_square(
    sx: int,
    sy: int,
    side: int,
    *,
    set_pos: Callable[[int, int], object],
    sleep: Callable[[float], object],
) -> None:
    x1, y1 = sx + side, sy
    x2, y2 = sx + side, sy + side
    x3, y3 = sx, sy + side
    edges = ((x1, y1), (x2, y2), (x3, y3), (sx, sy))
    prev_x, prev_y = sx, sy
    steps_per_edge = max(3, min(28, max(1, side // 4)))
    for tx, ty in edges:
        for t in range(1, steps_per_edge + 1):
            a = t / steps_per_edge
            x = int(round(prev_x + (tx - prev_x) * a))
            y = int(round(prev_y + (ty - prev_y) * a))
            set_pos(x, y)
            sleep(_TRAJECTORY_STEP_SLEEP)
        prev_x, prev_y = tx, ty
