"""CustomTkinter UI and scheduling for the mouse nudge app."""

from __future__ import annotations

import argparse
import sys
import threading
import tkinter as tk
from datetime import datetime
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from typing import Any, Literal

import customtkinter as ctk

from . import (
    local_config,
    nudge_logic,
    schedule_window,
)
from .app_icon import load_app_icon_rgba
from .cursor_nudge import ActivityStyle, MotionPattern, NaturalIntensity
from .strings import STRINGS, Lang
from .tray import HAS_TRAY, TrayController
from .ui_a11y import A11yMixin
from .ui_analytics import AnalyticsMixin
from .ui_common import (
    _FONT_INTER,
    UiTheme,
    _apply_start_maximized,
    _read_version_from_pyproject,
)
from .ui_config import ConfigMixin
from .ui_control_panel import ControlPanelMixin
from .ui_control_state import ControlStateMixin
from .ui_dialogs import DialogsMixin
from .ui_layout import LayoutMixin
from .ui_runner import RunnerMixin
from .ui_settings import SettingsMixin
from .ui_theme import ThemeMixin
from .ui_updates import UpdatesMixin


class MouseJigglerApp(
    ThemeMixin,
    A11yMixin,
    ControlStateMixin,
    ControlPanelMixin,
    ConfigMixin,
    DialogsMixin,
    UpdatesMixin,
    LayoutMixin,
    AnalyticsMixin,
    SettingsMixin,
    RunnerMixin,
):
    MIN_MINUTES = nudge_logic.MIN_MINUTES
    DEFAULT_MINUTES = nudge_logic.DEFAULT_MINUTES
    MIN_PIXELS = nudge_logic.MIN_PIXELS
    MAX_PIXELS = nudge_logic.MAX_PIXELS
    DEFAULT_PIXELS = nudge_logic.DEFAULT_PIXELS
    MIN_PATH_SPEED = nudge_logic.MIN_PATH_SPEED
    MAX_PATH_SPEED = nudge_logic.MAX_PATH_SPEED
    DEFAULT_PATH_SPEED = nudge_logic.DEFAULT_PATH_SPEED
    MAX_NATURAL_PIXELS = nudge_logic.MAX_NATURAL_PIXELS
    MIN_MOTION_DURATION_SECONDS = nudge_logic.MIN_MOTION_DURATION_SECONDS
    MAX_MOTION_DURATION_SECONDS = nudge_logic.MAX_MOTION_DURATION_SECONDS
    DEFAULT_MOTION_DURATION_SECONDS = nudge_logic.DEFAULT_MOTION_DURATION_SECONDS
    MAX_INTERVAL_JITTER_SEC = int(nudge_logic.MAX_INTERVAL_JITTER_SEC)
    MAX_STATUS_LABEL_CHARS = 88
    _LOG_TRIM_LINES = nudge_logic.LOG_TRIM_LINES
    _SIDEBAR_WIDTH = 200
    _UI_PAD = 26
    _AUTO_UPDATE_STARTUP_DELAY_MS = 1500
    _AUTO_UPDATE_INTERVAL_MS = 1 * 60 * 60 * 1000
    _AUTO_UPDATE_RETRY_MS = 15 * 60 * 1000

    def __init__(self, start_in_tray: bool = False) -> None:
        self._start_in_tray = bool(start_in_tray) and bool(HAS_TRAY)

        _cfg0 = local_config.load_config()
        _ut = _cfg0.get("ui_theme")
        self._ui_theme: UiTheme = _ut if _ut in ("dark", "light") else "light"
        self._apply_theme_palette(self._ui_theme)
        self._set_ctk_builtin_theme(self._ui_theme)

        self._lang: Lang = "en"
        self._segment_mode: Literal["control", "log"] = "control"
        self._active_nav: Literal["home", "settings", "analytics"] = "home"

        # CTkFont requires an existing Tk root or tkinter raises RuntimeError
        self.root = ctk.CTk()
        self._font_title = ctk.CTkFont(family=_FONT_INTER, size=28, weight="bold")
        self._font_brand = ctk.CTkFont(family=_FONT_INTER, size=20, weight="bold")
        self._font_body = ctk.CTkFont(family=_FONT_INTER, size=14)
        self._font_body_bold = ctk.CTkFont(family=_FONT_INTER, size=14, weight="bold")
        self._font_hint = ctk.CTkFont(family=_FONT_INTER, size=12)
        self._font_mono = ctk.CTkFont(family="Consolas", size=13)

        self.root.title(self._app_title_with_version())
        self.root.geometry("920x640")
        self.root.minsize(860, 580)
        self.root.configure(fg_color=self._MAIN_BG)
        self._window_icon_photo: tk.PhotoImage | None = None
        self._apply_window_icon()

        self._nav_icons = self._build_nav_icons()

        self._stop = threading.Event()
        self._worker: threading.Thread | None = None
        self._next_jiggle_monotonic = 0.0
        self._interval_unit: nudge_logic.IntervalUnit = "sec"
        self._running_interval_value = 0.0
        self._running_interval_unit: nudge_logic.IntervalUnit = "sec"
        self._current_interval_sec = 0.0
        self._running_motion_duration_seconds = float(self.DEFAULT_MOTION_DURATION_SECONDS)
        self._countdown_after_id: str | None = None
        self._burst_enter_after_id: str | None = None
        self._countdown_phase: Literal["interval", "burst", "schedule"] = "interval"
        self.status = tk.StringVar(value=self._t("status_stopped"))
        self._status_trace_guard = False
        self.status.trace_add("write", self._on_status_var_changed)
        self._schedule_resume_at: datetime | None = None
        self._run_schedule_window = False
        self._schedule_ws = schedule_window.DEFAULT_WORK_START
        self._schedule_we = schedule_window.DEFAULT_WORK_END
        self._schedule_segments_text = "09:00-18:00"
        self._schedule_include_weekends = False
        self._schedule_cron_text = ""

        self._tray = TrayController()
        self._shutting_down = False
        self._config_save_after_id: str | None = None
        self._config_loading = False
        self._intro_acknowledged = True
        self._motion_pattern: MotionPattern = "horizontal"
        self._auto_check_updates = True
        self._keep_awake_active = False
        self._update_check_in_progress = False
        self._update_check_after_id: str | None = None
        self._update_notice_url = ""
        self._update_notice_installer_url = ""
        self._update_notice_installer_name = ""
        self._update_notice_checksum_url = ""
        self._update_notice_checksum_name = ""
        self._update_notice_latest_tag = ""
        self._update_download_in_progress = False
        self._update_download_cancel_requested = False
        self._update_download_started_at = 0.0
        self._update_download_dialog: ctk.CTkToplevel | None = None
        self._update_download_label: ctk.CTkLabel | None = None
        self._update_download_bar: ctk.CTkProgressBar | None = None
        self._update_download_percent: ctk.CTkLabel | None = None
        self._update_download_meta: ctk.CTkLabel | None = None
        self._btn_update_download_cancel: ctk.CTkButton | None = None
        self._natural_intensity_tip: tk.Toplevel | None = None
        self._natural_intensity_tip_after_id: str | None = None
        self._update_notice_after_id: str | None = None
        self._update_notice_anim_after_id: str | None = None
        self._update_notice_target_h = 72
        self._activity_style: ActivityStyle = "pattern"
        self._natural_intensity: NaturalIntensity = "standard"

        self._analytics_trigger_mode: Literal["today", "week"] = "today"
        self._analytics_runtime_anchor = 0.0
        self._analytics_runtime_after_id: str | None = None

        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(1, weight=1)

        self._build_sidebar()
        self._build_main()
        self._build_global_update_notice()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._config_loading = True
        try:
            self._apply_loaded_config(_cfg0)
        finally:
            self._config_loading = False
        self._register_config_persistence()

        self._log(self._t("log_ready"))
        self._setup_a11y()
        if not self._start_in_tray:
            self.root.after(250, self._maybe_show_first_intro)
        # CTk can re-apply geometry after the first layout pass; schedule re-maximize after it.
        if not self._start_in_tray:
            self.root.after(0, self._reapply_start_maximized)
            self.root.after(150, self._reapply_start_maximized)
        if self._start_in_tray:
            self.root.after(120, self._bootstrap_tray_start)

        self.root.after(4500, self._tick_analytics_charts_loop)
        self._schedule_auto_update_check(self._AUTO_UPDATE_STARTUP_DELAY_MS)

    def _bootstrap_tray_start(self) -> None:
        if self._shutting_down or not HAS_TRAY:
            return
        try:
            self._log_ui(self._t("log_tray_start_hidden"))
        except tk.TclError:
            pass
        self.root.withdraw()
        self._start_tray()

    def _reapply_start_maximized(self) -> None:
        if self._shutting_down or self._start_in_tray:
            return
        _apply_start_maximized(self.root)

    def _pkg_version(self) -> str:
        try:
            import mouse_jiggler as _pkg  # noqa: PLC0415

            bundled_version = getattr(_pkg, "__version__", "").strip()
            if bundled_version:
                return bundled_version
        except Exception:
            pass

        try:
            return pkg_version("try-working-hard")
        except PackageNotFoundError:
            pyproject_version = _read_version_from_pyproject()
            if pyproject_version:
                return pyproject_version
            return "1.0.0"

    def _app_title_with_version(self) -> str:
        return f"{self._t('window_title')} v{self._pkg_version()}"

    def _apply_window_icon(self) -> None:
        from PIL import Image, ImageTk

        im = load_app_icon_rgba()
        if im is None:
            return
        if im.size[0] > 128 or im.size[1] > 128:
            im = im.resize((128, 128), Image.Resampling.LANCZOS)
        try:
            self._window_icon_photo = ImageTk.PhotoImage(im)
            self.root.iconphoto(True, self._window_icon_photo)
        except tk.TclError:
            self._window_icon_photo = None

    def _t(self, key: str, **kwargs: Any) -> str:
        s = STRINGS[self._lang][key]
        return s.format(**kwargs) if kwargs else s

    def _on_lang_switch(self, label: str) -> None:
        self._lang = "zh" if label == "繁中" else "en"
        self._apply_language()
        self._schedule_save_config()

    def _apply_language(self) -> None:
        self.root.title(self._app_title_with_version())
        if hasattr(self, "_brand"):
            self._brand.configure(text=self._app_title_with_version())
        sub = self._t("app_subtitle").strip()
        self._lbl_subtitle.configure(text=sub)
        p = self._UI_PAD
        if sub:
            if not self._lbl_subtitle.winfo_ismapped():
                self._lbl_subtitle.pack(anchor="w", padx=p, pady=(0, p), after=self._brand)
        else:
            self._lbl_subtitle.pack_forget()
        if hasattr(self, "_lbl_appearance"):
            self._lbl_appearance.configure(text=self._t("theme_appearance"))
        self._lbl_lang.configure(text=self._t("lang_ui"))
        self._hint.configure(text=self._theme_footer_text())
        if hasattr(self, "_hint_appearance"):
            self._hint_appearance.configure(text=self._theme_footer_text())
        self._lbl_dashboard.configure(text=self._t("dashboard"))
        if hasattr(self, "_lbl_extra_params_title"):
            self._lbl_extra_params_title.configure(text=self._t("fixed_params_title"))
        self._lbl_interval.configure(text=self._t("interval_label"))
        if hasattr(self, "_lbl_interval_presets"):
            self._lbl_interval_presets.configure(text=self._t("interval_presets_caption"))
        self._set_interval_hint()
        if hasattr(self, "_lbl_interval_jitter"):
            self._lbl_interval_jitter.configure(text=self._t("interval_jitter_label"))
            self._lbl_interval_jitter_hint.configure(
                text=self._t("interval_jitter_hint", max=self.MAX_INTERVAL_JITTER_SEC)
            )
        if hasattr(self, "_interval_preset_btns") and hasattr(self, "_interval_preset_specs"):
            for b, spec in zip(self._interval_preset_btns, self._interval_preset_specs, strict=True):
                b.configure(text=self._t(spec))
        self._sync_motion_pattern_seg()
        if hasattr(self, "_lbl_activity_style"):
            self._lbl_activity_style.configure(text=self._t("activity_style_label"))
        self._sync_activity_style_seg()
        if hasattr(self, "_lbl_activity_mode_params"):
            self._sync_activity_params_hint()
        if hasattr(self, "swt_natural_click"):
            self.swt_natural_click.configure(text=self._t("natural_rare_click"))
        if hasattr(self, "swt_natural_scroll"):
            self.swt_natural_scroll.configure(text=self._t("natural_rare_scroll"))
        if hasattr(self, "_lbl_natural_intensity"):
            self._lbl_natural_intensity.configure(text=self._t("natural_intensity_label"))
            self._hide_natural_intensity_tooltip()
        self._sync_natural_intensity_seg()
        if hasattr(self, "_lbl_natural_opts_hint"):
            self._lbl_natural_opts_hint.configure(text=self._t("natural_opts_hint"))
        self._refresh_activity_dependent_widgets()
        self._lbl_pixels.configure(text=self._t("pixels_label"))
        self._sync_pixels_hint()
        if hasattr(self, "_lbl_motion_duration"):
            self._lbl_motion_duration.configure(text=self._t("motion_duration_label"))
            self._lbl_motion_duration_hint.configure(
                text=self._t(
                    "motion_duration_hint",
                    lo=self.MIN_MOTION_DURATION_SECONDS,
                    hi=self.MAX_MOTION_DURATION_SECONDS,
                )
            )
        self._refresh_run_toggle_text()
        self._lbl_tray_sw.configure(text=self._t("tray_switch_title"))
        tray_hint = self._t("tray_switch_hint")
        if not HAS_TRAY:
            tray_hint += self._t("tray_no_pystray")
        self._hint_tray.configure(text=tray_hint)
        if hasattr(self, "_lbl_autostart_sw"):
            self._lbl_autostart_sw.configure(text=self._t("autostart_switch_title"))
        if hasattr(self, "_hint_autostart"):
            a_start = self._t("autostart_switch_hint")
            if sys.platform != "win32":
                a_start += self._t("autostart_not_windows")
            elif not HAS_TRAY:
                a_start += self._t("autostart_requires_tray")
            self._hint_autostart.configure(text=a_start)
        if hasattr(self, "_lbl_about_updates"):
            self._lbl_about_updates.configure(text=self._t("about_updates_title"))
        if hasattr(self, "_lbl_version_info"):
            self._lbl_version_info.configure(
                text=self._t("version_info", version=self._pkg_version())
            )
        if hasattr(self, "btn_contact_us"):
            self.btn_contact_us.configure(text=self._t("btn_contact_us"))
        if hasattr(self, "btn_check_updates"):
            self.btn_check_updates.configure(text=self._t("btn_check_updates"))
        if hasattr(self, "_lbl_auto_updates_sw"):
            self._lbl_auto_updates_sw.configure(text=self._t("auto_check_updates_title"))
        if hasattr(self, "_hint_auto_updates"):
            self._hint_auto_updates.configure(text=self._t("auto_check_updates_hint"))
        if hasattr(self, "_lbl_keep_awake_sw"):
            self._lbl_keep_awake_sw.configure(text=self._t("keep_display_awake_title"))
        if hasattr(self, "_hint_keep_awake"):
            self._hint_keep_awake.configure(text=self._t("keep_display_awake_hint"))
        if hasattr(self, "btn_update_notice_open"):
            self.btn_update_notice_open.configure(text=self._t("update_banner_open"))
        if hasattr(self, "btn_update_notice_close"):
            self.btn_update_notice_close.configure(text=self._t("update_banner_close"))
        self._lbl_schedule_sw.configure(text=self._t("schedule_window_title"))
        self._lbl_schedule_time_start.configure(text=self._t("schedule_window_start_label"))
        self._lbl_schedule_time_end.configure(text=self._t("schedule_window_end_label"))
        self._hint_schedule.configure(text=self._t("schedule_window_hint"))
        self._lbl_log_title.configure(text=self._t("log_title"))
        self._lbl_settings_title.configure(text=self._t("settings_title"))
        if hasattr(self, "btn_open_config"):
            self.btn_open_config.configure(text=self._t("btn_open_config_file"))
        self._lbl_analytics_title.configure(text=self._t("analytics_title"))
        if hasattr(self, "_lbl_analytics_sub"):
            self._lbl_analytics_sub.configure(text=self._t("analytics_subtitle"))
        if self._lbl_analytics_loading is not None:
            self._lbl_analytics_loading.configure(text=self._t(self._analytics_loading_key))
        if hasattr(self, "_lbl_chart_triggers"):
            self._lbl_chart_triggers.configure(text=self._t("analytics_chart_triggers"))
            self._lbl_chart_runtime.configure(text=self._t("analytics_chart_runtime"))
            self._lbl_chart_patterns.configure(text=self._t("analytics_chart_patterns"))
        if hasattr(self, "_seg_analytics_range"):
            vt = self._t("analytics_range_today")
            vw = self._t("analytics_range_week")
            self._seg_analytics_range.configure(values=[vt, vw])
            cur = vt if self._analytics_trigger_mode == "today" else vw
            self._seg_analytics_range.set(cur)

        self._nav_home.configure(text=f"  {self._t('nav_home')}")
        self._nav_settings.configure(text=f"  {self._t('nav_settings')}")
        self._nav_analytics.configure(text=f"  {self._t('nav_analytics')}")

        self.segmented.configure(values=[self._t("seg_control"), self._t("seg_log")])
        self.segmented.set(self._segment_text(self._segment_mode))
        if hasattr(self, "_seg_ui_theme"):
            self._seg_ui_theme.configure(
                values=[
                    self._t("theme_appearance_dark"),
                    self._t("theme_appearance_light"),
                ]
            )
        self._sync_ui_theme_seg()
        self._sync_nav_highlight()
        self._refresh_schedule_banner()

        if self._stop.is_set() or not (self._worker and self._worker.is_alive()):
            self.status.set(self._t("status_stopped"))
            self._apply_status_chrome("stopped")
        else:
            self._refresh_running_status_from_countdown()

        if hasattr(self, "_fig_trigger"):
            self._refresh_analytics_charts()

    def _start_tray(self) -> None:
        self._tray.start(
            tooltip=self._app_title_with_version(),
            label_show=self._t("tray_show"),
            label_quit=self._t("tray_quit"),
            on_show=lambda: self.root.after(0, self._show_from_tray),
            on_quit=lambda: self.root.after(0, self._quit_from_tray),
        )

    def _stop_tray(self) -> None:
        self._tray.stop()

    def _full_shutdown(self) -> None:
        if self._shutting_down:
            return
        self._save_config_now()
        self._shutting_down = True
        self._hide_natural_intensity_tooltip()

        self._cancel_analytics_runtime_flush()
        self._cancel_auto_update_check()
        self._close_installer_progress_dialog()
        self._flush_runtime_segment()

        self._stop.set()
        self._release_keep_awake()
        self._cancel_countdown_tick()

        w = self._worker
        if w is not None and w.is_alive():
            w.join(timeout=3.0)

        self._stop_tray()
        t = self._tray.thread
        if t is not None and t.is_alive():
            t.join(timeout=3.0)

        try:
            self.root.quit()
        except tk.TclError:
            pass
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def _show_from_tray(self) -> None:
        if self._shutting_down:
            return
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(200, lambda: self.root.attributes("-topmost", False))
        try:
            self.root.focus_force()
        except tk.TclError:
            pass

    def _quit_from_tray(self) -> None:
        try:
            self._log_ui(self._t("log_exit"))
        except tk.TclError:
            pass
        self._full_shutdown()

    def _on_close(self) -> None:
        if self.var_tray_close.get() and HAS_TRAY:
            try:
                self._log_ui(self._t("log_tray_minimize"))
            except tk.TclError:
                pass
            self.root.withdraw()
            self._start_tray()
            return

        try:
            self._log_ui(self._t("log_exit"))
        except tk.TclError:
            pass
        self._full_shutdown()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    p = argparse.ArgumentParser(
        prog="mouse_jiggler",
        description="Mouse nudge on a schedule (CustomTkinter UI).",
    )
    p.add_argument(
        "--start-in-tray",
        action="store_true",
        help="Start with the main window in the system tray (requires pystray).",
    )
    a = p.parse_args()
    MouseJigglerApp(start_in_tray=bool(a.start_in_tray)).run()
