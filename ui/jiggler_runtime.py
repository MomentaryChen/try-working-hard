"""Background runtime for idle-based nudges in the PySide6 UI."""

from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Any

from PySide6.QtCore import QObject, Signal

from mouse_jiggler import analytics_store, nudge_logic, schedule_window
from mouse_jiggler.win32_mouse import (
    get_seconds_since_last_user_input,
    jiggle_mouse,
    jiggle_natural,
)


class JigglerRuntime(QObject):
    status_changed = Signal(str)
    countdown_changed = Signal(str)
    log_emitted = Signal(str)
    running_changed = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._cfg: dict[str, Any] = {}

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, cfg: dict[str, Any]) -> bool:
        if self.is_running():
            return False
        self._cfg = dict(cfg)
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self.running_changed.emit(True)
        self.log_emitted.emit("Started.")
        return True

    def stop(self) -> None:
        self._stop_event.set()
        t = self._thread
        if t is not None and t.is_alive():
            t.join(timeout=1.0)
        self._thread = None
        self.status_changed.emit("Stopped")
        self.countdown_changed.emit("--:--")
        self.running_changed.emit(False)
        self.log_emitted.emit("Stopped.")

    def _run(self) -> None:
        cfg = self._cfg
        unit = "sec" if cfg.get("interval_unit") == "sec" else "min"
        interval_sec = nudge_logic.parse_interval_to_seconds(str(cfg.get("interval_text", "5")), unit)
        if interval_sec is None:
            interval_sec = nudge_logic.DEFAULT_MINUTES * 60.0
        jitter_sec = nudge_logic.parse_interval_jitter_seconds_string(
            str(cfg.get("interval_jitter_text", "0"))
        ) or 0.0
        pixels = nudge_logic.parse_pixels_string(str(cfg.get("pixels_text", "100")))
        if pixels is None:
            pixels = nudge_logic.DEFAULT_PIXELS
        path_speed = nudge_logic.parse_path_speed_string(str(cfg.get("path_speed_text", "5")))
        if path_speed is None:
            path_speed = nudge_logic.DEFAULT_PATH_SPEED

        activity_style = "natural" if cfg.get("activity_style") == "natural" else "pattern"
        pattern = str(cfg.get("motion_pattern", "horizontal"))
        if pattern not in {"horizontal", "circle", "square"}:
            pattern = "horizontal"
        rare_click = bool(cfg.get("natural_rare_click", False))
        rare_scroll = bool(cfg.get("natural_rare_scroll", False))
        wait_sec = nudge_logic.next_wait_seconds(interval_sec, jitter_sec)
        last_nudge_monotonic: float | None = None

        use_schedule = bool(cfg.get("schedule_window", False))
        spec = None
        if use_schedule:
            spec = schedule_window.build_schedule_spec(
                window_segments_text=str(cfg.get("schedule_window_segments_text", "09:00-18:00")),
                include_weekends=bool(cfg.get("schedule_include_weekends", False)),
                cron_text=str(cfg.get("schedule_cron_text", "")),
            )
            if spec is None:
                self.log_emitted.emit("Invalid schedule config, disabled.")
                use_schedule = False

        runtime_tick = time.monotonic()
        while not self._stop_event.is_set():
            now_dt = datetime.now()
            now_mon = time.monotonic()
            if use_schedule and spec is not None and not schedule_window.is_within_schedule(now_dt, spec):
                self.status_changed.emit("Paused by schedule")
                next_start = schedule_window.next_schedule_start(now_dt, spec)
                rem = max(0.0, (next_start - now_dt).total_seconds())
                self.countdown_changed.emit(nudge_logic.remaining_seconds_to_countdown_display(rem))
                runtime_tick = now_mon
                time.sleep(0.3)
                continue

            elapsed = max(0.0, now_mon - runtime_tick)
            runtime_tick = now_mon
            if elapsed > 0:
                analytics_store.add_runtime_seconds(elapsed)

            idle = get_seconds_since_last_user_input()
            eta = nudge_logic.eta_seconds_until_idle_nudge(
                wait_sec, idle, now=now_mon, last_nudge_monotonic=last_nudge_monotonic
            )
            self.status_changed.emit("Waiting for idle")
            self.countdown_changed.emit(nudge_logic.remaining_seconds_to_countdown_display(eta))
            if eta > 0:
                time.sleep(min(0.25, max(0.05, eta)))
                continue

            try:
                if activity_style == "natural":
                    jiggle_natural(
                        pixels,
                        path_speed=path_speed,
                        rare_click=rare_click,
                        rare_scroll=rare_scroll,
                    )
                    analytics_store.record_nudge("natural")
                    self.log_emitted.emit("Nudge: natural")
                else:
                    jiggle_mouse(pixels, pattern, path_speed=path_speed)
                    analytics_store.record_nudge(pattern)
                    self.log_emitted.emit(f"Nudge: {pattern}")
            except OSError as exc:
                self.status_changed.emit("Runtime error")
                self.log_emitted.emit(f"Error: {exc}")
                break

            wait_sec = nudge_logic.next_wait_seconds(interval_sec, jitter_sec)
            last_nudge_monotonic = time.monotonic()
            time.sleep(0.05)

        self.running_changed.emit(False)
