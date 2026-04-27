"""Horizontal cursor nudge with injectable position IO (testable without Win32)."""

from __future__ import annotations

from collections.abc import Callable


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
