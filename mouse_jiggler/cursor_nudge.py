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
_NATURAL_BASE_SLEEP = _TRAJECTORY_BASE_SLEEP * 0.9
# Reference step count for the "standard" natural profile; profiles scale density from it.
_NATURAL_REF_STEPS = 100.0
_NATURAL_MIN_STEPS = 12
_NATURAL_MAX_STEPS = 4000


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


def _hold_seconds(motion_duration_seconds: float, fallback: float) -> float:
    """Return ``motion_duration_seconds`` when it is a positive finite number, else ``fallback``."""
    target = float(motion_duration_seconds)
    if not math.isfinite(target) or target <= 0:
        return max(0.0005, float(fallback))
    return target


def _deadline(
    clock: Callable[[], float] | None, motion_duration_seconds: float
) -> float | None:
    """Monotonic end time for the motion, or ``None`` when no clock is injected."""
    if clock is None:
        return None
    target = float(motion_duration_seconds)
    if not math.isfinite(target) or target <= 0:
        return None
    return float(clock()) + target


def _past(clock: Callable[[], float] | None, deadline: float | None) -> bool:
    return clock is not None and deadline is not None and float(clock()) >= deadline


def _lap_count(*, steps_per_lap: int, step_delay: float, motion_duration_seconds: float) -> int:
    """
    Number of whole laps that best fills ``motion_duration_seconds`` at ``step_delay`` per step.

    Always at least one lap, so a slow speed or a large shape can overrun a short duration
    by up to one lap instead of being sped up (which would make ``path_speed`` meaningless).
    """
    target = float(motion_duration_seconds)
    lap_seconds = max(1e-6, float(step_delay) * max(1, int(steps_per_lap)))
    if not math.isfinite(target) or target <= 0:
        return 1
    return max(1, int(round(target / lap_seconds)))


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
    Move cursor right by ``delta_pixels``, hold for ``motion_duration_seconds``, then restore.
    No-op if ``delta_pixels <= 0`` or ``get_pos`` fails.

    There is no path to trace, so ``path_speed`` only matters when the duration is not a
    positive number (the hold then falls back to the speed-based step delay).
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
    delay = _hold_seconds(motion_duration_seconds, _step_delay(_HORIZ_BASE_SLEEP, path_speed))
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
    clock: Callable[[], float] | None = None,
) -> bool:
    """
    Move the cursor along a path and return to the starting position.

    ``path_speed`` (0–30) sets the delay between path points; higher is faster.
    ``motion_duration_seconds`` is the approximate total time: circle and square paths are
    traced repeatedly (whole laps, at least one) until the duration is filled, so a faster
    speed draws more laps. ``horizontal`` holds the offset for the duration instead.

    ``clock`` (e.g. ``time.monotonic``) is optional: when given, no new lap starts once the
    duration has elapsed, so real sleep overhead cannot stretch a fast run far past it.
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
            clock=clock,
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
            clock=clock,
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
    clock: Callable[[], float] | None = None,
) -> tuple[int, int]:
    # Use denser sampling so arc movement appears smoother on screen.
    n = max(24, min(180, max(radius, 1) * 4))
    step = _step_delay(_TRAJECTORY_BASE_SLEEP, path_speed)
    laps = _lap_count(steps_per_lap=n, step_delay=step, motion_duration_seconds=motion_duration_seconds)
    deadline = _deadline(clock, motion_duration_seconds)
    x_last, y_last = cx, cy
    x_prev, y_prev = cx, cy
    for i in range(n * laps):
        k = i % n
        if i > 0 and k == 0 and _past(clock, deadline):
            break
        theta = 2.0 * math.pi * k / n
        x = int(round(cx + radius * math.cos(theta)))
        y = int(round(cy + radius * math.sin(theta)))
        if i > 0 and _position_changed_since(get_pos, (x_prev, y_prev)):
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
    clock: Callable[[], float] | None = None,
) -> None:
    x1, y1 = sx + side, sy
    x2, y2 = sx + side, sy + side
    x3, y3 = sx, sy + side
    edges = ((x1, y1), (x2, y2), (x3, y3), (sx, sy))
    x_prev, y_prev = sx, sy
    # Increase edge interpolation points to reduce visible corner jumps.
    steps_per_edge = max(6, min(64, max(1, side // 2)))
    step = _step_delay(_TRAJECTORY_BASE_SLEEP, path_speed)
    laps = _lap_count(
        steps_per_lap=steps_per_edge * 4,
        step_delay=step,
        motion_duration_seconds=motion_duration_seconds,
    )
    deadline = _deadline(clock, motion_duration_seconds)
    for lap in range(laps):
        if lap > 0 and _past(clock, deadline):
            break
        # Each lap ends on the start corner, so every lap begins from (sx, sy).
        prev_x, prev_y = sx, sy
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
    clock: Callable[[], float] | None = None,
) -> bool:
    """
    Irregular micro-moves that stay within ``max_offset`` pixels of the starting point,
    then return to the exact start. Meant to avoid obvious geometric traces.

    Each invocation picks a random wander cap up to ``max_offset`` so successive nudges
    vary in reach while respecting the configured ceiling.

    ``motion_duration_seconds`` is the approximate total time. ``path_speed`` (0–30) sets the
    nominal delay between cursor updates, so the number of wander steps is derived from
    duration / delay: a higher speed gives a denser, faster wander in the same time.
    With an optional ``clock``, the wander returns to the start early once the duration
    has elapsed.
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
    # Step count follows duration / per-update delay, so path speed changes density.
    # The intensity profile keeps its relative density (conservative = denser steps).
    target_total = float(motion_duration_seconds)
    if not math.isfinite(target_total) or target_total <= 0:
        target_total = 0.0
    update_delay = _step_delay(_NATURAL_BASE_SLEEP, path_speed)
    density = (step_rng[0] + step_rng[1]) / 2.0 / _NATURAL_REF_STEPS
    if target_total > 0:
        raw_steps = target_total / (update_delay * substeps) * density * r.uniform(0.85, 1.15)
    else:
        raw_steps = r.uniform(step_rng[0], step_rng[1])
    n_steps = max(_NATURAL_MIN_STEPS, min(_NATURAL_MAX_STEPS, int(round(raw_steps))))
    pull = r.uniform(pull_rng[0], pull_rng[1])
    max_step = max(1.0, float(cap) * r.uniform(max_step_ratio_rng[0], max_step_ratio_rng[1]))
    weights = [r.uniform(0.75, 1.35) for _ in range(n_steps)]
    weight_sum = sum(weights) if weights else 1.0
    if target_total <= 0:
        delays = [max(0.0005, update_delay * substeps * w) for w in weights]
    else:
        delays = [max(0.0005, target_total * (w / weight_sum)) for w in weights]
    cx, cy = float(sx), float(sy)
    vx, vy = 0.0, 0.0
    smooth, drift = smooth_pair
    last_set_x, last_set_y = sx, sy
    deadline = _deadline(clock, motion_duration_seconds)

    for i in range(n_steps):
        if i == n_steps - 1 or _past(clock, deadline):
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
