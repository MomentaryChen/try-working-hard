"""Home -> Control state: segmented-button mapping, activity-dependent widgets, input parsing."""

from __future__ import annotations

import tkinter as tk
from typing import Literal

from . import (
    nudge_logic,
)
from .cursor_nudge import ActivityStyle, MotionPattern, NaturalIntensity
from .ui_common import (
    _FONT_INTER,
    _LOG,
)


class ControlStateMixin:
    """Mixin for :class:`mouse_jiggler.app.MouseJigglerApp`; relies on its shared state."""

    def _refresh_run_toggle_text(self) -> None:
        if not hasattr(self, "btn_run_toggle"):
            return
        is_running = self._worker is not None and self._worker.is_alive() and not self._stop.is_set()
        self.btn_run_toggle.configure(text=self._t("btn_stop") if is_running else self._t("btn_start"))

    def _hide_natural_intensity_tooltip(self, *_args: object) -> None:
        if self._natural_intensity_tip_after_id is not None:
            try:
                self.root.after_cancel(self._natural_intensity_tip_after_id)
            except tk.TclError:
                pass
            self._natural_intensity_tip_after_id = None
        tip = self._natural_intensity_tip
        self._natural_intensity_tip = None
        if tip is not None:
            try:
                tip.destroy()
            except tk.TclError:
                pass

    def _show_natural_intensity_tooltip(self) -> None:
        self._hide_natural_intensity_tooltip()
        if self._shutting_down:
            return
        try:
            # Plain Tk toplevel: CTkToplevel + overrideredirect/topmost is flaky on Windows.
            tip = tk.Toplevel(self.root)
            try:
                tip.wm_overrideredirect(True)
            except tk.TclError:
                pass
            try:
                tip.attributes("-topmost", True)
            except tk.TclError:
                pass
            tip.configure(bg=self._ENTRY_BORDER)
            outer = tk.Frame(tip, bg=self._ENTRY_BORDER, padx=1, pady=1)
            outer.pack(fill="both", expand=True)
            inner = tk.Frame(outer, bg=self._SURFACE_SUBTLE)
            inner.pack(fill="both", expand=True)
            tk.Label(
                inner,
                text=self._t("natural_intensity_tooltip_title"),
                font=(_FONT_INTER, 14, "bold"),
                bg=self._SURFACE_SUBTLE,
                fg=self._TEXT_BODY,
                anchor="w",
                justify="left",
            ).pack(anchor="w", padx=10, pady=(8, 4))
            tk.Label(
                inner,
                text=self._t("natural_intensity_tooltip_body"),
                font=(_FONT_INTER, 12),
                bg=self._SURFACE_SUBTLE,
                fg=self._TEXT_MUTED,
                justify="left",
                anchor="w",
                wraplength=420,
            ).pack(anchor="w", padx=10, pady=(0, 8))
            tip.update_idletasks()
            x = int(self.root.winfo_pointerx()) + 14
            y = int(self.root.winfo_pointery()) + 14
            tip.geometry(f"+{x}+{y}")
            self._natural_intensity_tip = tip
        except (tk.TclError, OSError) as exc:
            _LOG.debug("Natural intensity tooltip failed: %s", exc)
            self._natural_intensity_tip = None

    def _schedule_show_natural_intensity_tooltip(self, *_args: object) -> None:
        self._hide_natural_intensity_tooltip()
        try:
            self._natural_intensity_tip_after_id = self.root.after(
                320, self._show_natural_intensity_tooltip
            )
        except tk.TclError:
            self._natural_intensity_tip_after_id = None

    def _bind_natural_intensity_tooltip_hover(self) -> None:
        self._lbl_natural_intensity.bind("<Enter>", self._schedule_show_natural_intensity_tooltip)
        self._lbl_natural_intensity.bind("<Leave>", self._hide_natural_intensity_tooltip)
        try:
            # CTkSegmentedButton.bind is not implemented in some customtkinter versions.
            self.seg_natural_intensity.bind("<Enter>", self._schedule_show_natural_intensity_tooltip)
            self.seg_natural_intensity.bind("<Leave>", self._hide_natural_intensity_tooltip)
            return
        except NotImplementedError:
            pass
        for child in self.seg_natural_intensity.winfo_children():
            try:
                child.bind("<Enter>", self._schedule_show_natural_intensity_tooltip)
                child.bind("<Leave>", self._hide_natural_intensity_tooltip)
            except (tk.TclError, AttributeError):
                continue

    def _segment_text(self, mode: Literal["control", "log"]) -> str:
        return self._t("seg_control") if mode == "control" else self._t("seg_log")

    def _mode_from_segment_value(self, value: str) -> Literal["control", "log"]:
        if value == self._t("seg_control"):
            return "control"
        return "log"

    def _set_interval_hint(self) -> None:
        if not hasattr(self, "_lbl_interval_hint"):
            return
        try:
            self._lbl_interval_hint.configure(text=self._t("interval_hint_sec"))
        except (tk.TclError, AttributeError):
            pass

    def _apply_interval_preset(self, value: str) -> None:
        if self._shutting_down:
            return
        self.var_minutes.set(value)
        self._set_interval_hint()
        self._schedule_save_config()

    def _set_interval_preset_widgets_state(self, st: str) -> None:
        if not hasattr(self, "_interval_preset_btns"):
            return
        for b in self._interval_preset_btns:
            try:
                b.configure(state=st)
            except (tk.TclError, AttributeError):
                pass

    def _seg_value_for_motion_pattern(self, p: MotionPattern) -> str:
        if p == "horizontal":
            return self._t("motion_pattern_line")
        if p == "circle":
            return self._t("motion_pattern_circle")
        return self._t("motion_pattern_square")

    def _motion_pattern_from_seg_value(self, value: str) -> MotionPattern:
        if value == self._t("motion_pattern_line"):
            return "horizontal"
        if value == self._t("motion_pattern_circle"):
            return "circle"
        return "square"

    def _sync_motion_pattern_seg(self) -> None:
        if not hasattr(self, "seg_motion_pattern"):
            return
        try:
            self.seg_motion_pattern.configure(
                values=[
                    self._t("motion_pattern_line"),
                    self._t("motion_pattern_circle"),
                    self._t("motion_pattern_square"),
                ]
            )
            self.seg_motion_pattern.set(self._seg_value_for_motion_pattern(self._motion_pattern))
        except (tk.TclError, AttributeError):
            pass

    def _on_motion_pattern_seg(self, value: str) -> None:
        if self._shutting_down:
            return
        self._motion_pattern = self._motion_pattern_from_seg_value(value)
        self._schedule_save_config()

    def _seg_value_for_activity_style(self, s: ActivityStyle) -> str:
        return (
            self._t("activity_style_pattern")
            if s == "pattern"
            else self._t("activity_style_natural")
        )

    def _activity_style_from_seg_value(self, value: str) -> ActivityStyle:
        return "natural" if value == self._t("activity_style_natural") else "pattern"

    def _sync_activity_style_seg(self) -> None:
        if not hasattr(self, "seg_activity_style"):
            return
        try:
            self.seg_activity_style.configure(
                values=[
                    self._t("activity_style_pattern"),
                    self._t("activity_style_natural"),
                ]
            )
            self.seg_activity_style.set(self._seg_value_for_activity_style(self._activity_style))
        except (tk.TclError, AttributeError):
            pass

    def _on_activity_style_seg(self, value: str) -> None:
        if self._shutting_down:
            return
        self._activity_style = self._activity_style_from_seg_value(value)
        self._refresh_activity_dependent_widgets()
        self._schedule_save_config()

    def _refresh_activity_dependent_widgets(self) -> None:
        natural = self._activity_style == "natural"
        try:
            if hasattr(self, "_lbl_motion_pattern"):
                if natural:
                    self._lbl_motion_pattern.grid_remove()
                else:
                    self._lbl_motion_pattern.grid()
            if hasattr(self, "_row_motion_pattern"):
                if natural:
                    self._row_motion_pattern.grid_remove()
                else:
                    self._row_motion_pattern.grid()
            if hasattr(self, "row_natural_opts"):
                if natural:
                    self.row_natural_opts.grid()
                else:
                    self.row_natural_opts.grid_remove()
        except (tk.TclError, AttributeError):
            pass
        self._sync_path_speed_labels_for_mode()
        self._sync_motion_pattern_label_for_mode()
        self._sync_pixels_hint()
        self._sync_activity_params_hint()

    def _pixels_cap_for_activity(self) -> int:
        return self.MAX_NATURAL_PIXELS if self._activity_style == "natural" else self.MAX_PIXELS

    def _sync_pixels_hint(self) -> None:
        if not hasattr(self, "_lbl_pixels_hint"):
            return
        try:
            self._lbl_pixels_hint.configure(
                text=self._t(
                    "pixels_hint",
                    lo=self.MIN_PIXELS,
                    hi=self._pixels_cap_for_activity(),
                )
            )
        except (tk.TclError, AttributeError):
            pass

    def _sync_path_speed_labels_for_mode(self) -> None:
        if not hasattr(self, "_lbl_path_speed"):
            return
        try:
            if self._activity_style == "natural":
                self._lbl_path_speed.configure(text=self._t("path_speed_label_natural"))
                self._lbl_path_speed_hint.configure(
                    text=self._t(
                        "path_speed_hint_natural",
                        lo=self.MIN_PATH_SPEED,
                        hi=self.MAX_PATH_SPEED,
                    )
                )
            else:
                self._lbl_path_speed.configure(text=self._t("path_speed_label"))
                self._lbl_path_speed_hint.configure(
                    text=self._t(
                        "path_speed_hint",
                        lo=self.MIN_PATH_SPEED,
                        hi=self.MAX_PATH_SPEED,
                    )
                )
        except (tk.TclError, AttributeError):
            pass

    def _sync_motion_pattern_label_for_mode(self) -> None:
        if not hasattr(self, "_lbl_motion_pattern"):
            return
        try:
            if self._activity_style == "natural":
                self._lbl_motion_pattern.configure(text=self._t("motion_pattern_label_when_natural"))
            else:
                self._lbl_motion_pattern.configure(text=self._t("motion_pattern_label"))
        except (tk.TclError, AttributeError):
            pass

    def _sync_activity_params_hint(self) -> None:
        if not hasattr(self, "_lbl_activity_mode_params"):
            return
        try:
            key = (
                "activity_mode_params_natural"
                if self._activity_style == "natural"
                else "activity_mode_params_fixed"
            )
            self._lbl_activity_mode_params.configure(text=self._t(key))
        except (tk.TclError, AttributeError):
            pass

    def _on_natural_pref_changed(self) -> None:
        if self._shutting_down or self._config_loading:
            return
        self._schedule_save_config()

    def _seg_value_for_natural_intensity(self, i: NaturalIntensity) -> str:
        mapping = {
            "conservative": self._t("natural_intensity_conservative"),
            "standard": self._t("natural_intensity_standard"),
            "strong": self._t("natural_intensity_strong"),
        }
        return mapping.get(i, self._t("natural_intensity_standard"))

    def _natural_intensity_from_seg_value(self, value: str) -> NaturalIntensity:
        if value == self._t("natural_intensity_conservative"):
            return "conservative"
        if value == self._t("natural_intensity_strong"):
            return "strong"
        return "standard"

    def _sync_natural_intensity_seg(self) -> None:
        if not hasattr(self, "seg_natural_intensity"):
            return
        try:
            self.seg_natural_intensity.configure(
                values=[
                    self._t("natural_intensity_conservative"),
                    self._t("natural_intensity_standard"),
                    self._t("natural_intensity_strong"),
                ]
            )
            self.seg_natural_intensity.set(self._seg_value_for_natural_intensity(self._natural_intensity))
        except (tk.TclError, AttributeError):
            pass

    def _on_natural_intensity_seg(self, value: str) -> None:
        if self._shutting_down:
            return
        self._natural_intensity = self._natural_intensity_from_seg_value(value)
        self._schedule_save_config()

    def _pattern_log_label(self) -> str:
        if self._activity_style == "natural":
            return self._t("motion_pattern_log_natural")
        return {
            "horizontal": self._t("motion_pattern_log_line"),
            "circle": self._t("motion_pattern_log_circle"),
            "square": self._t("motion_pattern_log_square"),
        }[self._motion_pattern]

    def _parse_interval(self) -> float | None:
        raw = self.var_minutes.get()
        s = nudge_logic.parse_seconds_string(
            raw,
            min_seconds=nudge_logic.MIN_SECONDS,
            max_seconds=nudge_logic.MAX_SECONDS,
        )
        if s is None:
            return None
        return s

    def _parse_interval_jitter(self) -> float | None:
        return nudge_logic.parse_interval_jitter_seconds_string(
            self.var_interval_jitter.get(),
            max_jitter=float(self.MAX_INTERVAL_JITTER_SEC),
        )

    def _parse_pixels(self) -> int | None:
        return nudge_logic.parse_pixels_string(
            self.var_pixels.get(),
            min_px=self.MIN_PIXELS,
            max_px=self._pixels_cap_for_activity(),
        )

    def _parse_motion_duration_seconds(self) -> int | None:
        return nudge_logic.parse_motion_duration_seconds_string(
            self.var_motion_duration.get(),
            min_seconds=self.MIN_MOTION_DURATION_SECONDS,
            max_seconds=self.MAX_MOTION_DURATION_SECONDS,
        )

    def _parse_path_speed(self) -> int | None:
        return nudge_logic.parse_path_speed_string(
            self.var_path_speed.get(),
            min_sp=self.MIN_PATH_SPEED,
            max_sp=self.MAX_PATH_SPEED,
        )
