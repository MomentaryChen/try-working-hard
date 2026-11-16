"""Loading, snapshotting and debounced saving of config.json."""

from __future__ import annotations

import tkinter as tk
from typing import Any

from . import (
    local_config,
)


class ConfigMixin:
    """Mixin for :class:`mouse_jiggler.app.MouseJigglerApp`; relies on its shared state."""

    def _apply_loaded_config(self, cfg: dict[str, Any]) -> None:
        lang = cfg.get("lang")
        if lang in ("zh", "en"):
            self._lang = lang  # type: ignore[assignment]
        self.var_minutes.set(str(cfg.get("interval_text", str(int(self.DEFAULT_MINUTES)))))
        u = cfg.get("interval_unit", "min")
        self._interval_unit = "sec"
        if u == "min":
            try:
                legacy_sec = float(str(self.var_minutes.get()).strip().replace(",", ".")) * 60.0
                self.var_minutes.set(str(int(round(legacy_sec))))
            except (TypeError, ValueError):
                self.var_minutes.set(str(int(self.DEFAULT_MINUTES * 60)))
        self.var_interval_jitter.set(str(cfg.get("interval_jitter_text", "0")))
        self.var_pixels.set(str(cfg.get("pixels_text", str(self.DEFAULT_PIXELS))))
        self.var_path_speed.set(
            str(cfg.get("path_speed_text", str(int(self.DEFAULT_PATH_SPEED))))
        )
        self.var_motion_duration.set(
            str(
                cfg.get(
                    "motion_duration_seconds_text",
                    str(int(self.DEFAULT_MOTION_DURATION_SECONDS)),
                )
            )
        )
        mp = cfg.get("motion_pattern", "horizontal")
        self._motion_pattern = mp if mp in ("horizontal", "circle", "square") else "horizontal"
        ast = cfg.get("activity_style", "pattern")
        self._activity_style = ast if ast in ("pattern", "natural") else "pattern"
        ni = cfg.get("natural_intensity", "standard")
        self._natural_intensity = (
            ni if ni in ("conservative", "standard", "strong") else "standard"
        )
        if hasattr(self, "var_natural_rare_click"):
            self.var_natural_rare_click.set(bool(cfg.get("natural_rare_click", False)))
        if hasattr(self, "var_natural_rare_scroll"):
            self.var_natural_rare_scroll.set(bool(cfg.get("natural_rare_scroll", False)))
        self.var_tray_close.set(bool(cfg.get("close_to_tray", False)))
        self.var_schedule_window.set(bool(cfg.get("schedule_window", False)))
        self.var_schedule_start.set(
            str(cfg.get("schedule_window_start_text", "09:00"))
        )
        self.var_schedule_end.set(str(cfg.get("schedule_window_end_text", "18:00")))
        self._auto_check_updates = bool(cfg.get("auto_check_updates", True))
        self._schedule_segments_text = str(
            cfg.get(
                "schedule_window_segments_text",
                f"{self.var_schedule_start.get()}-{self.var_schedule_end.get()}",
            )
        )
        self._schedule_include_weekends = bool(cfg.get("schedule_include_weekends", False))
        self._schedule_cron_text = str(cfg.get("schedule_cron_text", ""))
        self._sync_schedule_times_from_vars()
        self._schedule_changed.set()
        self._run_schedule_window = bool(self.var_schedule_window.get())
        self._intro_acknowledged = bool(cfg.get("intro_acknowledged", True))
        self._lang_seg.set("繁中" if self._lang == "zh" else "English")
        if hasattr(self, "var_auto_check_updates"):
            self.var_auto_check_updates.set(self._auto_check_updates)

        ut = cfg.get("ui_theme")
        if ut in ("dark", "light") and ut != self._ui_theme:
            self._ui_theme = ut  # type: ignore[assignment]
            self._apply_theme_palette(self._ui_theme)
            self._set_ctk_builtin_theme(self._ui_theme)
            self._reapply_theme_to_widgets()
        elif ut in ("dark", "light"):
            self._ui_theme = ut  # type: ignore[assignment]
        self._sync_ui_theme_seg()

        self._apply_language()
        self._refresh_schedule_banner()

    def _config_snapshot(self) -> dict[str, Any]:
        return {
            "lang": self._lang,
            "ui_theme": self._ui_theme,
            "interval_text": self.var_minutes.get(),
            "interval_unit": "sec",
            "interval_jitter_text": self.var_interval_jitter.get(),
            "pixels_text": self.var_pixels.get(),
            "path_speed_text": self.var_path_speed.get(),
            "motion_duration_seconds_text": self.var_motion_duration.get(),
            "motion_pattern": self._motion_pattern,
            "activity_style": self._activity_style,
            "natural_intensity": self._natural_intensity,
            "natural_rare_click": bool(self.var_natural_rare_click.get()),
            "natural_rare_scroll": bool(self.var_natural_rare_scroll.get()),
            "close_to_tray": bool(self.var_tray_close.get()),
            "schedule_window": bool(self.var_schedule_window.get()),
            "schedule_window_start_text": self.var_schedule_start.get(),
            "schedule_window_end_text": self.var_schedule_end.get(),
            "schedule_window_segments_text": self._schedule_segments_text,
            "schedule_include_weekends": self._schedule_include_weekends,
            "schedule_cron_text": self._schedule_cron_text,
            "intro_acknowledged": self._intro_acknowledged,
            "auto_check_updates": bool(self.var_auto_check_updates.get()),
        }

    def _register_config_persistence(self) -> None:
        def _on_write(*_a: object) -> None:
            self._schedule_save_config()

        def _on_schedule_flag(*_a: object) -> None:
            self._run_schedule_window = bool(self.var_schedule_window.get())
            self._sync_schedule_times_from_vars()
            self._schedule_changed.set()
            self._schedule_save_config()
            self._refresh_schedule_banner()

        def _on_schedule_times_write(*_a: object) -> None:
            self._sync_schedule_times_from_vars()
            self._schedule_save_config()
            self._refresh_schedule_banner()

        def _on_auto_updates_toggle(*_a: object) -> None:
            _on_write()
            if bool(self.var_auto_check_updates.get()):
                self._schedule_auto_update_check(self._AUTO_UPDATE_STARTUP_DELAY_MS)
            else:
                self._cancel_auto_update_check()

        try:
            self.var_tray_close.trace_add("write", _on_write)
            self.var_minutes.trace_add("write", _on_write)
            self.var_interval_jitter.trace_add("write", _on_write)
            self.var_pixels.trace_add("write", _on_write)
            self.var_path_speed.trace_add("write", _on_write)
            self.var_motion_duration.trace_add("write", _on_write)
            self.var_schedule_window.trace_add("write", _on_schedule_flag)
            self.var_schedule_start.trace_add("write", _on_schedule_times_write)
            self.var_schedule_end.trace_add("write", _on_schedule_times_write)
            self.var_auto_check_updates.trace_add("write", _on_auto_updates_toggle)
        except (tk.TclError, AttributeError):
            pass

    def _schedule_save_config(self) -> None:
        if self._config_loading or self._shutting_down:
            return
        if self._config_save_after_id is not None:
            try:
                self.root.after_cancel(self._config_save_after_id)
            except tk.TclError:
                pass
        self._config_save_after_id = self.root.after(400, self._flush_save_config)

    def _flush_save_config(self) -> None:
        self._config_save_after_id = None
        if self._config_loading or self._shutting_down:
            return
        local_config.save_config(self._config_snapshot())

    def _save_config_now(self) -> None:
        if self._config_save_after_id is not None:
            try:
                self.root.after_cancel(self._config_save_after_id)
            except tk.TclError:
                pass
            self._config_save_after_id = None
        if self._config_loading:
            return
        local_config.save_config(self._config_snapshot())
