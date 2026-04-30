"""Cursor motion with injectable position IO (testable without Win32)."""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from typing import Literal

MotionPattern = Literal["horizontal", "circle", "square"]
ActivityStyle = Literal["pattern", "natural"]
NaturalIntensity = Literal["conservative", "standard", "strong"]

_TRAJECTORY_BASE_SLEEP = 0.02
_HORIZ_BASE_SLEEP = 0.05


class MotionInterrupted(Exception):
    """Raised when user cursor input is detected during a motion sequence."""


def _step_delay(base: float, path_speed: int) -> float:
    """Higher ``path_speed`` (0–30) → shorter delay. Nominal speed = 5."""
    ps = max(0, min(30, int(path_speed)))
    t = base * (6.0 / float(ps + 1))
    return max(0.002, min(0.12, t))


def _sleep_scaled(
    sleep: Callable[[float], object], delay: float
) -> None:
    sleep(max(0.0005, float(delay)))


def _position_changed_since(
    get_pos: Callable[[], tuple[int, int] | None], expected: tuple[int, int], *, tolerance: int = 2
) -> bool:
    cur = get_pos()
    if cur is None:
        return False
    return abs(int(cur[0]) - int(expected[0])) > tolerance or abs(int(cur[1]) - int(expected[1])) > tolerance


def _sleep_interruptible(
    sleep: Callable[[float], object],
    delay: float,
    *,
    should_abort: Callable[[], bool],
    quantum: float = 0.01,
) -> None:
    remain = max(0.0005, float(delay))
    while remain > 0:
        if should_abort():
            raise MotionInterrupted()
        step = min(remain, quantum)
        sleep(step)
        remain -= step


def _target_step_delay(base_delay: float, *, steps: int, motion_duration_seconds: float) -> float:
    """Scale per-step delay so total active movement approaches target seconds."""
    s = max(1, int(steps))
    target = float(motion_duration_seconds)
    if not math.isfinite(target) or target <= 0:
        return max(0.0005, float(base_delay))
    nominal_total = max(0.0005, float(base_delay)) * float(s)
    scale = target / nominal_total
    return max(0.0005, float(base_delay) * scale)


def nudge_horizontal(
    delta_pixels: int,
    *,
    path_speed: int = 5,
    motion_duration_seconds: float = 10.0,
    get_pos: Callable[[], tuple[int, int] | None],
    set_pos: Callable[[int, int], object],
    sleep: Callable[[float], object],
) -> bool:
    """
    Move cursor right by ``delta_pixels``, pause, then restore. No-op if ``delta_pixels <= 0``
    or ``get_pos`` fails.
    """
    d = int(delta_pixels)
    if d <= 0:
        return False
    pos = get_pos()
    if pos is None:
        return False
    x, y = pos
    set_pos(x + d, y)
    expected = (x + d, y)
    delay = _target_step_delay(
        _step_delay(_HORIZ_BASE_SLEEP, path_speed),
        steps=1,
        motion_duration_seconds=motion_duration_seconds,
    )
    _sleep_interruptible(
        sleep,
        delay,
        should_abort=lambda: _position_changed_since(get_pos, expected),
    )
    if _position_changed_since(get_pos, expected):
        raise MotionInterrupted()
    set_pos(x, y)
    return True


def nudge_trajectory(
    pattern: MotionPattern,
    pixels: int,
    path_speed: int,
    *,
    motion_duration_seconds: float = 10.0,
    get_pos: Callable[[], tuple[int, int] | None],
    set_pos: Callable[[int, int], object],
    sleep: Callable[[float], object],
) -> bool:
    """
    Move the cursor along a path and return to the starting position.

    ``path_speed`` (1–10) scales trace speed; higher is faster.
    """
    if pattern == "horizontal":
        return nudge_horizontal(
            pixels,
            path_speed=path_speed,
            motion_duration_seconds=motion_duration_seconds,
            get_pos=get_pos,
            set_pos=set_pos,
            sleep=sleep,
        )

    r = int(pixels)
    if r <= 0:
        return False
    pos = get_pos()
    if pos is None:
        return False
    sx, sy = pos

    if pattern == "circle":
        lx, ly = _trace_circle(
            sx,
            sy,
            r,
            path_speed,
            motion_duration_seconds=motion_duration_seconds,
            get_pos=get_pos,
            set_pos=set_pos,
            sleep=sleep,
        )
        # End of the arc is not the starting point; compare to last commanded pixel.
        if _position_changed_since(get_pos, (lx, ly)):
            raise MotionInterrupted()
        set_pos(sx, sy)
        return True

    if pattern == "square":
        _trace_square(
            sx,
            sy,
            r,
            path_speed,
            motion_duration_seconds=motion_duration_seconds,
            get_pos=get_pos,
            set_pos=set_pos,
            sleep=sleep,
        )
        if _position_changed_since(get_pos, (sx, sy)):
            raise MotionInterrupted()
        set_pos(sx, sy)
        return True
    return False


def _trace_circle(
    cx: int,
    cy: int,
    radius: int,
    path_speed: int,
    *,
    motion_duration_seconds: float,
    get_pos: Callable[[], tuple[int, int] | None],
    set_pos: Callable[[int, int], object],
    sleep: Callable[[float], object],
) -> tuple[int, int]:
    # Use denser sampling so arc movement appears smoother on screen.
    n = max(24, min(180, max(radius, 1) * 4))
    step = _target_step_delay(
        _step_delay(_TRAJECTORY_BASE_SLEEP, path_speed),
        steps=n,
        motion_duration_seconds=motion_duration_seconds,
    )
    x_last, y_last = cx, cy
    for k in range(n):
        theta = 2.0 * math.pi * k / n
        x = int(round(cx + radius * math.cos(theta)))
        y = int(round(cy + radius * math.sin(theta)))
        if k > 0 and _position_changed_since(get_pos, (x_prev, y_prev)):
            raise MotionInterrupted()
        set_pos(x, y)
        _sleep_interruptible(
            sleep,
            step,
            should_abort=lambda ex=x, ey=y: _position_changed_since(get_pos, (ex, ey)),
        )
        x_prev, y_prev = x, y
        x_last, y_last = x, y
    return x_last, y_last


def _trace_square(
    sx: int,
    sy: int,
    side: int,
    path_speed: int,
    *,
    motion_duration_seconds: float,
    get_pos: Callable[[], tuple[int, int] | None],
    set_pos: Callable[[int, int], object],
    sleep: Callable[[float], object],
) -> None:
    x1, y1 = sx + side, sy
    x2, y2 = sx + side, sy + side
    x3, y3 = sx, sy + side
    edges = ((x1, y1), (x2, y2), (x3, y3), (sx, sy))
    prev_x, prev_y = sx, sy
    x_prev, y_prev = sx, sy
    # Increase edge interpolation points to reduce visible corner jumps.
    steps_per_edge = max(6, min(64, max(1, side // 2)))
    total_steps = steps_per_edge * 4
    step = _target_step_delay(
        _step_delay(_TRAJECTORY_BASE_SLEEP, path_speed),
        steps=total_steps,
        motion_duration_seconds=motion_duration_seconds,
    )
    for tx, ty in edges:
        for t in range(1, steps_per_edge + 1):
            a = t / steps_per_edge
            x = int(round(prev_x + (tx - prev_x) * a))
            y = int(round(prev_y + (ty - prev_y) * a))
            if _position_changed_since(get_pos, (x_prev, y_prev)):
                raise MotionInterrupted()
            set_pos(x, y)
            _sleep_interruptible(
                sleep,
                step,
                should_abort=lambda ex=x, ey=y: _position_changed_since(get_pos, (ex, ey)),
            )
            x_prev, y_prev = x, y
        prev_x, prev_y = tx, ty


def nudge_natural(
    max_offset: int,
    path_speed: int,
    *,
    motion_duration_seconds: float = 10.0,
    intensity: NaturalIntensity = "standard",
    get_pos: Callable[[], tuple[int, int] | None],
    set_pos: Callable[[int, int], object],
    sleep: Callable[[float], object],
    rng: random.Random | None = None,
) -> bool:
    """
    Irregular micro-moves that stay within ``max_offset`` pixels of the starting point,
    then return to the exact start. Meant to avoid obvious geometric traces.

    Each invocation picks a random wander cap up to ``max_offset`` so successive nudges
    vary in reach while respecting the configured ceiling.
    """
    r = rng or random.Random()
    mo = int(max_offset)
    if mo <= 0:
        return False
    pos = get_pos()
    if pos is None:
        return False
    sx, sy = int(pos[0]), int(pos[1])
    profiles: dict[
        NaturalIntensity,
        tuple[
            float,
            float,
            tuple[int, int],
            tuple[float, float],
            int,
            tuple[float, float],
            tuple[float, float],
        ],
    ] = {
        # Calm and compact: lower cap, denser steps, higher smoothing.
        "conservative": (0.35, 0.65, (96, 210), (0.90, 0.10), 5, (0.08, 0.16), (0.12, 0.24)),
        # Balanced behavior around configured max offset.
        "standard": (0.70, 0.95, (60, 140), (0.86, 0.14), 3, (0.10, 0.22), (0.08, 0.22)),
        # Pronounced and smoother: near-max cap with more interpolation for fluid travel.
        "strong": (0.95, 1.0, (34, 82), (0.82, 0.18), 3, (0.14, 0.28), (0.08, 0.18)),
    }
    (
        cap_lo_ratio,
        cap_hi_ratio,
        step_rng,
        smooth_pair,
        substeps,
        max_step_ratio_rng,
        pull_rng,
    ) = profiles.get(intensity, profiles["standard"])
    # Honor configured displacement more directly: keep only mild randomness.
    # This makes natural-mode "Nudge (pixels)" feel effective instead of often too small.
    if mo < 3:
        cap = mo
    else:
        cap = r.randint(max(2, int(mo * cap_lo_ratio)), max(2, int(mo * cap_hi_ratio)))
    # More micro-steps yields smoother perceived movement.
    n_steps = r.randint(step_rng[0], step_rng[1])
    pull = r.uniform(pull_rng[0], pull_rng[1])
    max_step = max(1.0, float(cap) * r.uniform(max_step_ratio_rng[0], max_step_ratio_rng[1]))
    weights = [r.uniform(0.75, 1.35) for _ in range(n_steps)]
    weight_sum = sum(weights) if weights else 1.0
    target_total = float(motion_duration_seconds)
    if not math.isfinite(target_total) or target_total <= 0:
        base = _step_delay(_TRAJECTORY_BASE_SLEEP * 0.9, path_speed)
        delays = [max(0.0005, base * w) for w in weights]
    else:
        delays = [max(0.0005, target_total * (w / weight_sum)) for w in weights]
    cx, cy = float(sx), float(sy)
    vx, vy = 0.0, 0.0
    smooth, drift = smooth_pair
    last_set_x, last_set_y = sx, sy

    for i in range(n_steps):
        if i == n_steps - 1:
            if _position_changed_since(get_pos, (last_set_x, last_set_y)):
                raise MotionInterrupted()
            set_pos(sx, sy)
            _sleep_interruptible(
                sleep,
                delays[i],
                should_abort=lambda: _position_changed_since(get_pos, (sx, sy)),
            )
            break
        rx = (r.random() - 0.5) * 2.0 * max_step
        ry = (r.random() - 0.5) * 2.0 * max_step
        # Add inertia so direction changes are smoother and less jittery.
        vx = vx * smooth + rx * drift
        vy = vy * smooth + ry * drift
        cx = cx + vx + (sx - cx) * pull
        cy = cy + vy + (sy - cy) * pull
        dx, dy = cx - sx, cy - sy
        dist = math.hypot(dx, dy)
        if dist > cap and dist > 1e-6:
            scale = cap / dist
            cx = sx + dx * scale
            cy = sy + dy * scale
        if _position_changed_since(get_pos, (last_set_x, last_set_y)):
            raise MotionInterrupted()
        target_x, target_y = int(round(cx)), int(round(cy))
        seg_delay = max(0.0005, delays[i] / substeps)
        sx0, sy0 = last_set_x, last_set_y
        for j in range(1, substeps + 1):
            a = j / substeps
            set_x = int(round(sx0 + (target_x - sx0) * a))
            set_y = int(round(sy0 + (target_y - sy0) * a))
            if _position_changed_since(get_pos, (last_set_x, last_set_y)):
                raise MotionInterrupted()
            set_pos(set_x, set_y)
            last_set_x, last_set_y = set_x, set_y
            _sleep_interruptible(
                sleep,
                seg_delay,
                should_abort=lambda ex=set_x, ey=set_y: _position_changed_since(get_pos, (ex, ey)),
            )
    return True
