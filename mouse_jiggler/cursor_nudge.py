"""Cursor motion with injectable position IO (testable without Win32)."""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from typing import Literal

MotionPattern = Literal["horizontal", "circle", "square"]
ActivityStyle = Literal["pattern", "natural"]

_TRAJECTORY_BASE_SLEEP = 0.02
_HORIZ_BASE_SLEEP = 0.05


def _step_delay(base: float, path_speed: int) -> float:
    """Higher ``path_speed`` (1–10) → shorter delay. Nominal speed = 5."""
    ps = max(1, min(10, int(path_speed)))
    t = base * (5.0 / float(ps))
    return max(0.002, min(0.12, t))


def _sleep_scaled(
    sleep: Callable[[float], object], delay: float, *, motion_duration_mult: float
) -> None:
    m = motion_duration_mult if math.isfinite(motion_duration_mult) and motion_duration_mult > 0 else 1.0
    sleep(max(0.0005, float(delay) * m))


def nudge_horizontal(
    delta_pixels: int,
    *,
    path_speed: int = 5,
    motion_duration_mult: float = 1.0,
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
    _sleep_scaled(
        sleep,
        _step_delay(_HORIZ_BASE_SLEEP, path_speed),
        motion_duration_mult=motion_duration_mult,
    )
    set_pos(x, y)


def nudge_trajectory(
    pattern: MotionPattern,
    pixels: int,
    path_speed: int,
    *,
    motion_duration_mult: float = 1.0,
    get_pos: Callable[[], tuple[int, int] | None],
    set_pos: Callable[[int, int], object],
    sleep: Callable[[float], object],
) -> None:
    """
    Move the cursor along a path and return to the starting position.

    ``path_speed`` (1–10) scales trace speed; higher is faster.
    """
    if pattern == "horizontal":
        nudge_horizontal(
            pixels,
            path_speed=path_speed,
            motion_duration_mult=motion_duration_mult,
            get_pos=get_pos,
            set_pos=set_pos,
            sleep=sleep,
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
        _trace_circle(
            sx,
            sy,
            r,
            path_speed,
            motion_duration_mult=motion_duration_mult,
            set_pos=set_pos,
            sleep=sleep,
        )
        set_pos(sx, sy)
        return

    if pattern == "square":
        _trace_square(
            sx,
            sy,
            r,
            path_speed,
            motion_duration_mult=motion_duration_mult,
            set_pos=set_pos,
            sleep=sleep,
        )
        set_pos(sx, sy)


def _trace_circle(
    cx: int,
    cy: int,
    radius: int,
    path_speed: int,
    *,
    motion_duration_mult: float,
    set_pos: Callable[[int, int], object],
    sleep: Callable[[float], object],
) -> None:
    step = _step_delay(_TRAJECTORY_BASE_SLEEP, path_speed)
    n = max(12, min(72, max(radius, 1) * 2))
    for k in range(n):
        theta = 2.0 * math.pi * k / n
        x = int(round(cx + radius * math.cos(theta)))
        y = int(round(cy + radius * math.sin(theta)))
        set_pos(x, y)
        _sleep_scaled(sleep, step, motion_duration_mult=motion_duration_mult)


def _trace_square(
    sx: int,
    sy: int,
    side: int,
    path_speed: int,
    *,
    motion_duration_mult: float,
    set_pos: Callable[[int, int], object],
    sleep: Callable[[float], object],
) -> None:
    step = _step_delay(_TRAJECTORY_BASE_SLEEP, path_speed)
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
            _sleep_scaled(sleep, step, motion_duration_mult=motion_duration_mult)
        prev_x, prev_y = tx, ty


def nudge_natural(
    max_offset: int,
    path_speed: int,
    *,
    motion_duration_mult: float = 1.0,
    get_pos: Callable[[], tuple[int, int] | None],
    set_pos: Callable[[int, int], object],
    sleep: Callable[[float], object],
    rng: random.Random | None = None,
) -> None:
    """
    Irregular micro-moves that stay within ``max_offset`` pixels of the starting point,
    then return to the exact start. Meant to avoid obvious geometric traces.

    Each invocation picks a random wander cap up to ``max_offset`` so successive nudges
    vary in reach while respecting the configured ceiling.
    """
    r = rng or random.Random()
    mo = int(max_offset)
    if mo <= 0:
        return
    pos = get_pos()
    if pos is None:
        return
    sx, sy = int(pos[0]), int(pos[1])
    cap = mo if mo < 3 else r.randint(max(2, int(mo * 0.15)), mo)
    step_delay = _step_delay(_TRAJECTORY_BASE_SLEEP * 0.9, path_speed)
    n_steps = r.randint(20, 52)
    pull = r.uniform(0.08, 0.22)
    max_step = max(1.0, float(cap) * r.uniform(0.16, 0.34))
    cx, cy = float(sx), float(sy)

    for i in range(n_steps):
        if i == n_steps - 1:
            set_pos(sx, sy)
            _sleep_scaled(
                sleep,
                step_delay * r.uniform(0.75, 1.35),
                motion_duration_mult=motion_duration_mult,
            )
            break
        rx = (r.random() - 0.5) * 2.0 * max_step
        ry = (r.random() - 0.5) * 2.0 * max_step
        cx = cx + rx + (sx - cx) * pull
        cy = cy + ry + (sy - cy) * pull
        dx, dy = cx - sx, cy - sy
        dist = math.hypot(dx, dy)
        if dist > cap and dist > 1e-6:
            scale = cap / dist
            cx = sx + dx * scale
            cy = sy + dy * scale
        set_pos(int(round(cx)), int(round(cy)))
        _sleep_scaled(
            sleep,
            step_delay * r.uniform(0.75, 1.35),
            motion_duration_mult=motion_duration_mult,
        )
