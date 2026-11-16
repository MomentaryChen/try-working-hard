"""Start/stop, the background nudge loop, countdown and status strip, log bridge."""

from __future__ import annotations

import threading
import time
import tkinter as tk
from datetime import datetime
from typing import Any, Literal

import customtkinter as ctk

from . import (
    analytics_store,
    nudge_logic,
    schedule_window,
)
from .cursor_nudge import ActivityStyle, MotionInterrupted, MotionPattern
from .win32_mouse import (
    get_seconds_since_last_user_input,
    jiggle_mouse,
    jiggle_natural,
    set_keep_awake,
)


class RunnerMixin:
    """Mixin for :class:`mouse_jiggler.app.MouseJigglerApp`; relies on its shared state."""

    def _truncate_status_text(self, value: str) -> str:
        text = value.strip()
        if len(text) <= self.MAX_STATUS_LABEL_CHARS:
            return text
        return text[: self.MAX_STATUS_LABEL_CHARS - 3].rstrip() + "..."

    def _set_status_if_changed(self, text: str) -> None:
        """Set the status line only when the (clipped) text differs, avoiding label redraws."""
        if self._truncate_status_text(text) == self.status.get():
            return
        self.status.set(text)

    def _on_status_var_changed(self, *_args: object) -> None:
        if getattr(self, "_status_trace_guard", False):
            return
        current = self.status.get()
        clipped = self._truncate_status_text(current)
        if clipped == current:
            return
        self._status_trace_guard = True
        try:
            self.status.set(clipped)
        finally:
            self._status_trace_guard = False

    def _on_toggle_run(self) -> None:
        is_running = self._worker is not None and self._worker.is_alive() and not self._stop.is_set()
        if is_running:
            self._on_stop()
        else:
            self._on_start()

    def _t_status_running(self, cd: str) -> str:
        v = self._running_interval_value
        return self._t(
            "status_running_sec",
            v=v,
            cd=cd,
            md=int(round(self._running_motion_duration_seconds)),
        )

    def _refresh_running_status_from_countdown(self) -> None:
        if self._current_interval_sec <= 0:
            return
        if self._countdown_phase == "schedule" and self._schedule_resume_at is not None:
            rem = (self._schedule_resume_at - datetime.now()).total_seconds()
            cd = nudge_logic.remaining_seconds_to_countdown_display(rem)
            self.status.set(self._t("status_schedule_wait", cd=cd))
            self._apply_status_chrome("schedule")
            return
        rem = self._next_jiggle_monotonic - time.monotonic()
        cd = nudge_logic.remaining_seconds_to_countdown_display(rem)
        if self._countdown_phase == "burst":
            self.status.set(
                self._t(
                    "status_motion_burst",
                    cd=cd,
                    md=int(round(self._running_motion_duration_seconds)),
                )
            )
            self._apply_status_chrome("burst")
        else:
            self.status.set(self._t_status_running(cd))
            self._apply_status_chrome("interval")

    def _apply_status_chrome(
        self, kind: Literal["stopped", "interval", "burst", "schedule"]
    ) -> None:
        """Update status strip colors and LED to match schedule state."""
        # The countdown re-applies the same state every 500 ms; each configure() makes
        # CTk redraw its canvas, so skip when neither the state nor the theme changed.
        chrome_key = (kind, self._ui_theme)
        if chrome_key == getattr(self, "_status_chrome_key", None):
            return
        self._status_chrome_key = chrome_key
        if kind == "stopped":
            self._status_strip.configure(
                fg_color=self._STATUS_STRIP_BG_STOP,
                border_color=self._STATUS_STRIP_BORDER_STOP,
            )
            self._status_led.configure(text_color=(self._STATUS_LED_STOP, self._STATUS_LED_STOP))
            self._lbl_status.configure(text_color=(self._TEXT_BODY, self._TEXT_BODY))
        elif kind == "interval":
            self._status_strip.configure(
                fg_color=self._STATUS_STRIP_BG_RUN,
                border_color=self._STATUS_STRIP_BORDER_RUN,
            )
            self._status_led.configure(text_color=(self._STATUS_LED_RUN, self._STATUS_LED_RUN))
            self._lbl_status.configure(text_color=(self._STATUS_TEXT_RUN, self._STATUS_TEXT_RUN))
        elif kind == "schedule":
            self._status_strip.configure(
                fg_color=self._STATUS_STRIP_BG_SCHEDULE,
                border_color=self._STATUS_STRIP_BORDER_SCHEDULE,
            )
            self._status_led.configure(
                text_color=(self._STATUS_LED_SCHEDULE, self._STATUS_LED_SCHEDULE)
            )
            self._lbl_status.configure(
                text_color=(self._STATUS_TEXT_SCHEDULE, self._STATUS_TEXT_SCHEDULE)
            )
        else:
            self._status_strip.configure(
                fg_color=self._STATUS_STRIP_BG_BURST,
                border_color=self._STATUS_STRIP_BORDER_BURST,
            )
            self._status_led.configure(text_color=(self._STATUS_LED_BURST, self._STATUS_LED_BURST))
            self._lbl_status.configure(text_color=(self._STATUS_TEXT_BURST, self._STATUS_TEXT_BURST))

    def _append_log_line_trim(self, widget: ctk.CTkTextbox, line: str) -> None:
        widget.configure(state="normal")
        widget.insert("end", line)
        try:
            idx = widget.index("end-1c")
            total = int(str(idx).split(".")[0])
        except (tk.TclError, ValueError, AttributeError):
            body = widget.get("0.0", "end-1c")
            total = len(body.splitlines()) if body else 0
        excess = nudge_logic.log_lines_to_delete_from_top(total, self._LOG_TRIM_LINES)
        if excess > 0:
            widget.delete("1.0", f"{excess + 1}.0")
        widget.see("end")
        widget.configure(state="disabled")

    def _cancel_countdown_tick(self) -> None:
        if self._countdown_after_id is not None:
            try:
                self.root.after_cancel(self._countdown_after_id)
            except tk.TclError:
                pass
            self._countdown_after_id = None

    def _cancel_pending_burst_phase(self) -> None:
        if self._burst_enter_after_id is not None:
            try:
                self.root.after_cancel(self._burst_enter_after_id)
            except tk.TclError:
                pass
            self._burst_enter_after_id = None

    def _schedule_burst_phase(self, duration_sec: float) -> None:
        self._cancel_pending_burst_phase()
        try:
            self._burst_enter_after_id = self.root.after(
                120, lambda d=duration_sec: self._ui_enter_burst_phase(d)
            )
        except tk.TclError:
            self._burst_enter_after_id = None

    def _schedule_countdown_tick(self) -> None:
        self._cancel_countdown_tick()
        self._countdown_after_id = self.root.after(500, self._countdown_tick)

    def _countdown_tick(self) -> None:
        self._countdown_after_id = None
        if self._shutting_down:
            return
        if self._stop.is_set() or not (self._worker and self._worker.is_alive()):
            return

        rem = self._next_jiggle_monotonic - time.monotonic()
        countdown_str = nudge_logic.remaining_seconds_to_countdown_display(rem)
        if self._countdown_phase == "schedule" and self._schedule_resume_at is not None:
            rem = (self._schedule_resume_at - datetime.now()).total_seconds()
            countdown_str = nudge_logic.remaining_seconds_to_countdown_display(rem)
            self._set_status_if_changed(self._t("status_schedule_wait", cd=countdown_str))
            self._apply_status_chrome("schedule")
        elif self._countdown_phase == "burst":
            self._set_status_if_changed(
                self._t(
                    "status_motion_burst",
                    cd=countdown_str,
                    md=int(round(self._running_motion_duration_seconds)),
                )
            )
            self._apply_status_chrome("burst")
        else:
            self._set_status_if_changed(self._t_status_running(countdown_str))
            self._apply_status_chrome("interval")
        self._countdown_after_id = self.root.after(500, self._countdown_tick)

    def _log(self, message: str) -> None:
        if self._shutting_down:
            return
        try:
            if not self.root.winfo_exists():
                return
        except tk.TclError:
            return
        self._ui_invoke(lambda m=message: self._log_ui(m))

    def _ui_invoke(self, fn: Any) -> None:
        """Run a callable in the Tk main loop thread."""
        if self._shutting_down:
            return
        try:
            if threading.current_thread() is threading.main_thread():
                fn()
            else:
                self.root.after(0, fn)
        except tk.TclError:
            pass

    def _log_ui(self, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {message}\n"
        self._append_log_line_trim(self.log_text, line)
        # Before the Analytics page is built, its log is filled from log_text on first visit.
        if hasattr(self, "analytics_log"):
            self._append_log_line_trim(self.analytics_log, line)

    def _nudge_tick(
        self,
        pixels: int,
        pattern: MotionPattern,
        path_speed: int,
        motion_duration_seconds: int,
        *,
        activity_style: ActivityStyle,
        natural_rare_click: bool,
        natural_rare_scroll: bool,
        log_success: bool = True,
    ) -> None:
        self._ui_invoke(
            lambda d=motion_duration_seconds: self._schedule_burst_phase(float(d))
        )
        try:
            if activity_style == "natural":
                completed = jiggle_natural(
                    pixels,
                    path_speed=path_speed,
                    motion_duration_seconds=motion_duration_seconds,
                    intensity=self._natural_intensity,
                    rare_click=natural_rare_click,
                    rare_scroll=natural_rare_scroll,
                    propagate_interrupt=True,
                )
                rec_key = "natural"
            else:
                completed = jiggle_mouse(
                    pixels,
                    pattern,
                    path_speed=path_speed,
                    motion_duration_seconds=motion_duration_seconds,
                    propagate_interrupt=True,
                )
                rec_key = pattern
            if not completed:
                return
            if not log_success:
                return
            analytics_store.record_nudge(rec_key)
            if pixels > 0:
                self._log(self._t("log_nudge"))
            else:
                self._log(self._t("log_nudge_zero"))
        except MotionInterrupted:
            self._log(self._t("log_nudge_interrupted"))
        except OSError as e:
            self._log(self._t("log_nudge_fail", err=e))
        finally:
            self._ui_invoke(
                lambda: (
                    self._cancel_pending_burst_phase(),
                    self._ui_enter_interval_phase(),
                )
            )

    def _ui_enter_burst_phase(self, duration_sec: float) -> None:
        if self._shutting_down:
            return
        self._burst_enter_after_id = None
        self._countdown_phase = "burst"
        self._schedule_resume_at = None
        self._next_jiggle_monotonic = time.monotonic() + max(0.0, float(duration_sec))
        self._apply_status_chrome("burst")
        self._schedule_countdown_tick()

    def _ui_schedule_wait_begin(self, resume_at: datetime) -> None:
        if self._shutting_down:
            return
        self._countdown_phase = "schedule"
        self._schedule_resume_at = resume_at
        self._next_jiggle_monotonic = time.monotonic() + max(
            0.0, (resume_at - datetime.now()).total_seconds()
        )
        self._apply_status_chrome("schedule")
        self._schedule_countdown_tick()

    def _ui_exit_schedule_wait(self) -> None:
        if self._shutting_down:
            return
        self._schedule_resume_at = None
        self._countdown_phase = "interval"
        if self._worker is not None and self._worker.is_alive() and not self._stop.is_set():
            self._apply_status_chrome("interval")
            self._schedule_countdown_tick()
        else:
            self._apply_status_chrome("stopped")

    def _ui_enter_interval_phase(self) -> None:
        if self._shutting_down:
            return
        self._countdown_phase = "interval"
        self._schedule_resume_at = None
        if self._worker is not None and self._worker.is_alive() and not self._stop.is_set():
            self._apply_status_chrome("interval")
            self._schedule_countdown_tick()

    def _wait_for_schedule_if_needed(self) -> bool:
        if not self._run_schedule_window:
            return not self._stop.is_set()
        waited = False
        while not self._stop.is_set():
            now = datetime.now()
            spec = self._build_schedule_spec()
            if spec is None:
                return False
            if schedule_window.is_within_schedule(now, spec):
                if waited:
                    self._ui_invoke(lambda: self._log(self._t("log_schedule_resumed")))
                return not self._stop.is_set()
            waited = True
            resume_at = schedule_window.next_schedule_start(now, spec)
            self._ui_invoke(lambda ra=resume_at: self._ui_schedule_wait_begin(ra))
            end_mono = time.monotonic() + max(0.0, (resume_at - now).total_seconds())
            while time.monotonic() < end_mono and not self._stop.is_set():
                left = end_mono - time.monotonic()
                if left <= 0:
                    break
                step = min(30.0, left)
                if self._stop.wait(timeout=step):
                    return False
                if not self._run_schedule_window:
                    self._ui_invoke(self._ui_exit_schedule_wait)
                    return not self._stop.is_set()
            if self._stop.is_set():
                return False
        return False

    def _apply_keep_awake(self) -> None:
        """
        Keep the system and display awake while a run is active and the setting is on.

        Always called on the Tk main thread, because ``SetThreadExecutionState`` is per thread.
        """
        running = (
            self._worker is not None and self._worker.is_alive() and not self._stop.is_set()
        )
        want = running and not self._shutting_down and bool(self.var_keep_display_awake.get())
        if want == getattr(self, "_keep_awake_active", False):
            return
        set_keep_awake(want)
        self._keep_awake_active = want

    def _release_keep_awake(self) -> None:
        if getattr(self, "_keep_awake_active", False):
            set_keep_awake(False)
            self._keep_awake_active = False

    def _on_start(self) -> None:
        interval_sec = self._parse_interval()
        if interval_sec is None:
            err_body = self._t(
                "err_seconds",
                min=nudge_logic.MIN_SECONDS,
                max=nudge_logic.MAX_SECONDS,
            )
            self._show_error_dialog(
                self._t("err_title"),
                err_body,
            )
            self._log(self._t("log_start_fail_interval"))
            return
        ival = interval_sec
        jitter_sec = self._parse_interval_jitter()
        if jitter_sec is None:
            self._show_error_dialog(
                self._t("err_title"),
                self._t("err_jitter", max=self.MAX_INTERVAL_JITTER_SEC),
            )
            self._log(self._t("log_start_fail_jitter"))
            return
        pixels = self._parse_pixels()
        if pixels is None:
            self._show_error_dialog(
                self._t("err_title"),
                self._t(
                    "err_pixels",
                    lo=self.MIN_PIXELS,
                    hi=self._pixels_cap_for_activity(),
                ),
            )
            self._log(self._t("log_start_fail_pixels"))
            return
        path_speed = self._parse_path_speed()
        if path_speed is None:
            self._show_error_dialog(
                self._t("err_title"),
                self._t("err_path_speed", lo=self.MIN_PATH_SPEED, hi=self.MAX_PATH_SPEED),
            )
            self._log(self._t("log_start_fail_path_speed"))
            return
        motion_duration_seconds = self._parse_motion_duration_seconds()
        if motion_duration_seconds is None:
            self._show_error_dialog(
                self._t("err_title"),
                self._t(
                    "err_motion_duration",
                    lo=self.MIN_MOTION_DURATION_SECONDS,
                    hi=self.MAX_MOTION_DURATION_SECONDS,
                ),
            )
            self._log(self._t("log_start_fail_motion_duration"))
            return
        if self._worker is not None and self._worker.is_alive():
            return

        if bool(self.var_schedule_window.get()):
            psched = self._build_schedule_spec()
            if psched is None:
                self._show_error_dialog(
                    self._t("err_title"),
                    self._t("err_schedule_bounds"),
                )
                self._log(self._t("log_start_fail_schedule_bounds"))
                return

        self._stop.clear()
        self._run_schedule_window = bool(self.var_schedule_window.get())
        self._running_interval_value = ival
        self._running_interval_unit = "sec"
        self._running_motion_duration_seconds = float(motion_duration_seconds)
        self._current_interval_sec = interval_sec
        self._next_jiggle_monotonic = time.monotonic() + interval_sec
        run_pattern: MotionPattern = self._motion_pattern
        run_activity: ActivityStyle = self._activity_style
        n_click = bool(self.var_natural_rare_click.get())
        n_scroll = bool(self.var_natural_rare_scroll.get())

        self._worker = threading.Thread(
            target=self._run_loop,
            args=(
                interval_sec,
                jitter_sec,
                pixels,
                path_speed,
                motion_duration_seconds,
                run_activity,
                run_pattern,
                n_click,
                n_scroll,
            ),
            daemon=True,
        )
        self._worker.start()
        self._apply_keep_awake()

        self._analytics_runtime_anchor = time.monotonic()
        self._schedule_next_runtime_flush()

        self.btn_run_toggle.configure(state="normal")
        self._refresh_run_toggle_text()
        self.entry_minutes.configure(state="disabled")
        self.entry_pixels.configure(state="disabled")
        self.entry_path_speed.configure(state="disabled")
        self.entry_motion_duration.configure(state="disabled")
        self.entry_interval_jitter.configure(state="disabled")
        self._set_interval_preset_widgets_state("disabled")
        try:
            self.seg_motion_pattern.configure(state="disabled")
        except (tk.TclError, AttributeError):
            pass
        try:
            self.seg_activity_style.configure(state="disabled")
        except (tk.TclError, AttributeError):
            pass
        try:
            self.swt_natural_click.configure(state="disabled")
            self.swt_natural_scroll.configure(state="disabled")
            self.seg_natural_intensity.configure(state="disabled")
        except (tk.TclError, AttributeError):
            pass
        try:
            self.swt_schedule.configure(state="disabled")
        except (tk.TclError, AttributeError):
            pass
        try:
            self.entry_schedule_start.configure(state="disabled")
            self.entry_schedule_end.configure(state="disabled")
        except (tk.TclError, AttributeError):
            pass
        self._apply_status_chrome("interval")
        self._schedule_countdown_tick()
        pat = self._pattern_log_label()
        if jitter_sec > 0.0:
            self._log(
                self._t(
                    "log_started_sec_jitter",
                    v=ival,
                    j=jitter_sec,
                    pat=pat,
                    px=pixels,
                    ps=path_speed,
                    md=motion_duration_seconds,
                )
            )
        else:
            self._log(
                self._t(
                    "log_started_sec",
                    v=ival,
                    pat=pat,
                    px=pixels,
                    ps=path_speed,
                    md=motion_duration_seconds,
                )
            )
        if self._run_schedule_window:
            b = self._parsed_schedule_bounds_raw()
            if b is not None and b[0] < b[1]:
                ws, we = b
            else:
                ws, we = (
                    schedule_window.DEFAULT_WORK_START,
                    schedule_window.DEFAULT_WORK_END,
                )
            self._log(
                self._t(
                    "log_start_schedule",
                    start=schedule_window.format_hhmm(ws),
                    end=schedule_window.format_hhmm(we),
                    weekend=(
                        self._t("schedule_weekend_on")
                        if self._schedule_include_weekends
                        else self._t("schedule_weekend_off")
                    ),
                    cron=self._schedule_cron_text.strip() or self._t("schedule_cron_off"),
                )
            )

    def _on_stop(self) -> None:
        self._flush_runtime_segment()
        self._cancel_analytics_runtime_flush()
        self._stop.set()
        self._release_keep_awake()
        self._cancel_countdown_tick()
        self._current_interval_sec = 0.0
        self._countdown_phase = "interval"
        self._schedule_resume_at = None
        self.btn_run_toggle.configure(state="normal")
        self._refresh_run_toggle_text()
        self.entry_minutes.configure(state="normal")
        self.entry_pixels.configure(state="normal")
        self.entry_path_speed.configure(state="normal")
        self.entry_motion_duration.configure(state="normal")
        self.entry_interval_jitter.configure(state="normal")
        self._set_interval_preset_widgets_state("normal")
        try:
            self.seg_motion_pattern.configure(state="normal")
        except (tk.TclError, AttributeError):
            pass
        try:
            self.seg_activity_style.configure(state="normal")
        except (tk.TclError, AttributeError):
            pass
        try:
            self.swt_natural_click.configure(state="normal")
            self.swt_natural_scroll.configure(state="normal")
            self.seg_natural_intensity.configure(state="normal")
        except (tk.TclError, AttributeError):
            pass
        try:
            self.swt_schedule.configure(state="normal")
        except (tk.TclError, AttributeError):
            pass
        try:
            self.entry_schedule_start.configure(state="normal")
            self.entry_schedule_end.configure(state="normal")
        except (tk.TclError, AttributeError):
            pass
        self.status.set(self._t("status_stopped"))
        self._apply_status_chrome("stopped")
        self._log(self._t("log_stopped"))
        self._refresh_activity_dependent_widgets()

    def _run_loop(
        self,
        interval_sec: float,
        jitter_sec: float,
        pixels: int,
        path_speed: int,
        motion_duration_seconds: int,
        activity_style: ActivityStyle,
        pattern: MotionPattern,
        natural_rare_click: bool,
        natural_rare_scroll: bool,
    ) -> None:
        last_nudge_monotonic: float | None = None
        poll = 0.2
        active_interval = nudge_logic.next_wait_seconds(interval_sec, jitter_sec)
        while not self._stop.is_set():
            if not self._wait_for_schedule_if_needed():
                break
            now = time.monotonic()
            idle = get_seconds_since_last_user_input()
            eta = nudge_logic.eta_seconds_until_idle_nudge(
                active_interval, idle, now=now, last_nudge_monotonic=last_nudge_monotonic
            )
            self._next_jiggle_monotonic = now + eta
            to_sleep = min(poll, max(0.01, eta))
            if self._stop.wait(timeout=to_sleep):
                break
            now = time.monotonic()
            idle = get_seconds_since_last_user_input()
            if idle < active_interval:
                continue
            if last_nudge_monotonic is not None and (now - last_nudge_monotonic) < active_interval:
                continue
            self._nudge_tick(
                pixels,
                pattern,
                path_speed,
                motion_duration_seconds,
                activity_style=activity_style,
                natural_rare_click=natural_rare_click,
                natural_rare_scroll=natural_rare_scroll,
                log_success=True,
            )
            # Count interval from when movement fully finishes, not from nudge start.
            last_nudge_monotonic = time.monotonic()
            active_interval = nudge_logic.next_wait_seconds(interval_sec, jitter_sec)
