"""CustomTkinter UI and scheduling for the mouse nudge app."""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time
import tkinter as tk
from datetime import date, datetime
from importlib.metadata import version as pkg_version
from importlib.resources import files
from pathlib import Path
from tkinter import messagebox
from typing import Any, Literal

import customtkinter as ctk

from . import analytics_charts, analytics_store, local_config, nudge_logic, schedule_window
from .app_icon import load_app_icon_rgba
from .cursor_nudge import MotionPattern
from .strings import Lang, STRINGS
from .tray import HAS_TRAY, TrayController
from .win32_mouse import get_seconds_since_last_user_input, jiggle_mouse

# Primary UI font (Inter). If missing, Tk picks a substitute.
_FONT_INTER = "Inter"

# Pro dark / light: unified corner radius; padding in class (see _UI_PAD).
_R = 12
_R_BTN = _R  # primary / secondary button radius (used by _btn)

UiTheme = Literal["dark", "light"]
_UI_PALETTES: dict[UiTheme, dict[str, str]] = {
    "dark": {
        "MAIN_BG": "#0D1117",
        "SIDEBAR_BG": "#010409",
        "CARD_BG": "#161B22",
        "CARD_BORDER": "#30363D",
        "ENTRY_BG": "#0D1117",
        "ENTRY_BORDER": "#30363D",
        "ACCENT": "#2F81F7",
        "ACCENT_HOVER": "#58A6FF",
        "TEXT_ON_ACCENT": "#FFFFFF",
        "SURFACE_SUBTLE": "#0D1117",
        "SURFACE_SUBTLE_HOVER": "#21262D",
        "BORDER": "#30363D",
        "TEXT_TITLE": "#FFFFFF",
        "TEXT_BODY": "#C9D1D9",
        "TEXT_MUTED": "#8B949E",
        "TEXT_DISABLED": "#484F58",
        "TEXT_LOG": "#C9D1D9",
        "NAV_TEXT": "#8B949E",
        "NAV_HOVER": "#21262D",
        "NAV_SELECTED": "#2F81F7",
        "NAV_ON_SELECTED": "#FFFFFF",
        "BTN_SECONDARY": "#21262D",
        "BTN_SECONDARY_HOVER": "#30363D",
        "STATUS_STRIP_BG_STOP": "#161B22",
        "STATUS_STRIP_BORDER_STOP": "#30363D",
        "STATUS_LED_STOP": "#6E7681",
        "STATUS_STRIP_BG_RUN": "#0D1B12",
        "STATUS_STRIP_BORDER_RUN": "#238636",
        "STATUS_LED_RUN": "#3FB950",
        "STATUS_TEXT_RUN": "#7EE787",
        "STATUS_STRIP_BG_BURST": "#1C1008",
        "STATUS_STRIP_BORDER_BURST": "#D29922",
        "STATUS_LED_BURST": "#E3B341",
        "STATUS_TEXT_BURST": "#D4A72C",
        "STATUS_STRIP_BG_SCHEDULE": "#0C1C2E",
        "STATUS_STRIP_BORDER_SCHEDULE": "#1F6FEB",
        "STATUS_LED_SCHEDULE": "#58A6FF",
        "STATUS_TEXT_SCHEDULE": "#79C0FF",
    },
    "light": {
        "MAIN_BG": "#F9FAFB",
        "SIDEBAR_BG": "#F3F4F6",
        "CARD_BG": "#FFFFFF",
        "CARD_BORDER": "#E5E7EB",
        "ENTRY_BG": "#F9FAFB",
        "ENTRY_BORDER": "#E5E7EB",
        "ACCENT": "#3B82F6",
        "ACCENT_HOVER": "#2563EB",
        "TEXT_ON_ACCENT": "#FFFFFF",
        "SURFACE_SUBTLE": "#F3F4F6",
        "SURFACE_SUBTLE_HOVER": "#E5E7EB",
        "BORDER": "#E5E7EB",
        "TEXT_TITLE": "#111827",
        "TEXT_BODY": "#111827",
        "TEXT_MUTED": "#6B7280",
        "TEXT_DISABLED": "#9CA3AF",
        "TEXT_LOG": "#111827",
        "NAV_TEXT": "#6B7280",
        "NAV_HOVER": "#E5E7EB",
        "NAV_SELECTED": "#3B82F6",
        "NAV_ON_SELECTED": "#FFFFFF",
        "BTN_SECONDARY": "#E5E7EB",
        "BTN_SECONDARY_HOVER": "#D1D5DB",
        "STATUS_STRIP_BG_STOP": "#F3F4F6",
        "STATUS_STRIP_BORDER_STOP": "#E5E7EB",
        "STATUS_LED_STOP": "#9CA3AF",
        "STATUS_STRIP_BG_RUN": "#ECFDF5",
        "STATUS_STRIP_BORDER_RUN": "#6EE7B7",
        "STATUS_LED_RUN": "#059669",
        "STATUS_TEXT_RUN": "#065F46",
        "STATUS_STRIP_BG_BURST": "#FFFBEB",
        "STATUS_STRIP_BORDER_BURST": "#FCD34D",
        "STATUS_LED_BURST": "#D97706",
        "STATUS_TEXT_BURST": "#92400E",
        "STATUS_STRIP_BG_SCHEDULE": "#F0F9FF",
        "STATUS_STRIP_BORDER_SCHEDULE": "#7DD3FC",
        "STATUS_LED_SCHEDULE": "#0284C7",
        "STATUS_TEXT_SCHEDULE": "#0369A1",
    },
}


def _try_takefocus(widget: Any, value: int | bool) -> None:
    """Set takefocus on CTk/Tk widgets; ignore if unsupported (keyboard / screen-reader support)."""
    # CTkButton: takefocus is not a valid **kwargs to CTkBaseClass / configure (CustomTkinter 5.x).
    if isinstance(widget, ctk.CTkButton):
        return
    try:
        widget.configure(takefocus=value)  # type: ignore[union-attr]
    except (tk.TclError, AttributeError, TypeError, ValueError):
        pass


def _apply_start_maximized(root: tk.Misc) -> None:
    """Maximize the main window (restored size still comes from minsize/geometry on un-maximize).

    May need to be called again after CustomTkinter layout or after a modal dialog: both can clear
    ``zoomed`` on Windows by applying an explicit ``geometry`` or reparenting focus.
    """
    try:
        if sys.platform == "win32":
            root.state("zoomed")
        else:
            root.attributes("-zoomed", True)
    except tk.TclError:
        pass


def _tint_rgba_image(im: Any, hex_color: str) -> Any:
    """Recolor non-transparent pixels (monochrome Lucide-style PNG assets)."""
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    out = im.convert("RGBA")
    px = out.load()
    w, h = out.size
    for yy in range(h):
        for xx in range(w):
            *_, a = px[xx, yy]
            if a:
                px[xx, yy] = (r, g, b, a)
    return out


def _load_pkg_nav_png(stem: str) -> Any | None:
    """Load sidebar icon PNG from ``mouse_jiggler/assets/icons`` (wheel-safe)."""
    from PIL import Image

    fname = f"{stem}.png"
    try:
        ref = files("mouse_jiggler") / "assets" / "icons" / fname
        if ref.is_file():
            with ref.open("rb") as fp:
                return Image.open(fp).convert("RGBA")
    except (ModuleNotFoundError, OSError, TypeError, ValueError):
        pass
    alt = Path(__file__).resolve().parent / "assets" / "icons" / fname
    if alt.is_file():
        return Image.open(alt).convert("RGBA")
    return None


# HKCU\Software\Microsoft\Windows\CurrentVersion\Run (optional boot entry).
_WIN_RUN_REGKEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_WIN_RUN_VALUE_NAME = "TryWorkingHardMouseNudge"


def _windows_autostart_command() -> str:
    """Command line to relaunch the app in tray (matches registry value)."""
    exe = str(Path(sys.executable).resolve())
    if getattr(sys, "frozen", False):
        return f'"{exe}" --start-in-tray'
    return f'"{exe}" -m mouse_jiggler --start-in-tray'


def _windows_run_autostart_read() -> str | None:
    if sys.platform != "win32":
        return None
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _WIN_RUN_REGKEY, 0, winreg.KEY_READ
        ) as key:
            val, _ = winreg.QueryValueEx(key, _WIN_RUN_VALUE_NAME)
        return str(val) if val else None
    except OSError:
        return None


def _windows_run_autoset(enabled: bool) -> None:
    if sys.platform != "win32":
        return
    import winreg

    if enabled:
        cmd = _windows_autostart_command()
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, _WIN_RUN_REGKEY) as k:
            winreg.SetValueEx(
                k, _WIN_RUN_VALUE_NAME, 0, winreg.REG_SZ, cmd
            )
    else:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, _WIN_RUN_REGKEY, 0, winreg.KEY_SET_VALUE
            ) as k:
                winreg.DeleteValue(k, _WIN_RUN_VALUE_NAME)
        except OSError:
            pass


def _windows_run_autostart_active() -> bool:
    if sys.platform != "win32":
        return False
    cur = _windows_run_autostart_read()
    return bool(cur) and cur.strip() == _windows_autostart_command().strip()


class MouseJigglerApp:
    MIN_MINUTES = nudge_logic.MIN_MINUTES
    DEFAULT_MINUTES = nudge_logic.DEFAULT_MINUTES
    MIN_PIXELS = nudge_logic.MIN_PIXELS
    MAX_PIXELS = nudge_logic.MAX_PIXELS
    DEFAULT_PIXELS = nudge_logic.DEFAULT_PIXELS
    MIN_PATH_SPEED = nudge_logic.MIN_PATH_SPEED
    MAX_PATH_SPEED = nudge_logic.MAX_PATH_SPEED
    DEFAULT_PATH_SPEED = nudge_logic.DEFAULT_PATH_SPEED
    MAX_INTERVAL_JITTER_SEC = int(nudge_logic.MAX_INTERVAL_JITTER_SEC)
    _LOG_TRIM_LINES = nudge_logic.LOG_TRIM_LINES
    _SIDEBAR_WIDTH = 200
    _UI_PAD = 26

    def _apply_theme_palette(self, name: UiTheme) -> None:
        for key, value in _UI_PALETTES[name].items():
            setattr(self, f"_{key}", value)

    def _set_ctk_builtin_theme(self, name: UiTheme) -> None:
        if name == "dark":
            ctk.set_appearance_mode("dark")
            ctk.set_default_color_theme("dark-blue")
        else:
            ctk.set_appearance_mode("light")
            ctk.set_default_color_theme("blue")

    def _theme_footer_text(self) -> str:
        return self._t(
            "theme_status_dark" if self._ui_theme == "dark" else "theme_status_light"
        )

    def _sync_ui_theme_seg(self) -> None:
        if not hasattr(self, "_seg_ui_theme"):
            return
        d = self._t("theme_appearance_dark")
        l = self._t("theme_appearance_light")
        self._seg_ui_theme.set(d if self._ui_theme == "dark" else l)

    def _on_ui_theme_seg(self, value: str) -> None:
        dark = self._t("theme_appearance_dark")
        new: UiTheme = "dark" if value == dark else "light"
        if new == self._ui_theme:
            return
        self._ui_theme = new
        self._apply_theme_palette(self._ui_theme)
        self._set_ctk_builtin_theme(self._ui_theme)
        self._reapply_theme_to_widgets()
        self._apply_language()
        self._schedule_save_config()

    def _reapply_theme_to_widgets(self) -> None:
        """Re-apply palette tokens to all widgets after dark/light switch."""
        self.root.configure(fg_color=self._MAIN_BG)
        if hasattr(self, "_sidebar"):
            self._sidebar.configure(fg_color=self._SIDEBAR_BG)
        if hasattr(self, "_brand"):
            self._brand.configure(text_color=(self._TEXT_TITLE, self._TEXT_TITLE))
        if hasattr(self, "_lbl_subtitle"):
            self._lbl_subtitle.configure(text_color=self._TEXT_BODY)
        if hasattr(self, "_hint"):
            self._hint.configure(
                text=self._theme_footer_text(), text_color=self._TEXT_MUTED
            )
        if hasattr(self, "_hint_appearance"):
            self._hint_appearance.configure(
                text=self._theme_footer_text(), text_color=self._TEXT_MUTED
            )

        self._nav_icons = self._build_nav_icons()
        self._sync_nav_highlight()

        if hasattr(self, "_lbl_dashboard"):
            self._lbl_dashboard.configure(text_color=(self._TEXT_TITLE, self._TEXT_TITLE))
        if hasattr(self, "segmented"):
            self.segmented.configure(
                fg_color=self._SURFACE_SUBTLE,
                selected_color=self._ACCENT,
                selected_hover_color=self._ACCENT_HOVER,
                unselected_color=self._SURFACE_SUBTLE,
                unselected_hover_color=self._SURFACE_SUBTLE_HOVER,
                text_color=(self._TEXT_BODY, self._TEXT_ON_ACCENT),
                text_color_disabled=(self._TEXT_DISABLED, self._TEXT_DISABLED),
            )
        if hasattr(self, "frame_control"):
            self.frame_control.configure(
                fg_color=self._CARD_BG,
                border_color=self._CARD_BORDER,
                scrollbar_button_color=self._BTN_SECONDARY,
                scrollbar_button_hover_color=self._BTN_SECONDARY_HOVER,
            )
        if hasattr(self, "frame_log"):
            self.frame_log.configure(
                fg_color=self._CARD_BG,
                border_color=self._CARD_BORDER,
            )
        if hasattr(self, "page_settings"):
            self.page_settings.configure(
                fg_color=self._CARD_BG,
                border_color=self._CARD_BORDER,
            )
        if hasattr(self, "page_analytics"):
            self.page_analytics.configure(
                fg_color=self._CARD_BG,
                border_color=self._CARD_BORDER,
            )
        if hasattr(self, "analytics_scroll"):
            self.analytics_scroll.configure(
                fg_color=self._CARD_BG,
                border_color=self._CARD_BORDER,
                scrollbar_button_color=self._BTN_SECONDARY,
                scrollbar_button_hover_color=self._BTN_SECONDARY_HOVER,
            )

        for w in ("entry_minutes", "entry_pixels", "entry_path_speed"):
            if hasattr(self, w):
                getattr(self, w).configure(
                    fg_color=self._ENTRY_BG,
                    text_color=(self._TEXT_BODY, self._TEXT_BODY),
                    border_color=self._ENTRY_BORDER,
                )
        if hasattr(self, "seg_interval_unit"):
            self.seg_interval_unit.configure(
                fg_color=self._SURFACE_SUBTLE,
                selected_color=self._ACCENT,
                selected_hover_color=self._ACCENT_HOVER,
                unselected_color=self._SURFACE_SUBTLE,
                unselected_hover_color=self._SURFACE_SUBTLE_HOVER,
                text_color=(self._TEXT_BODY, self._TEXT_ON_ACCENT),
                text_color_disabled=(self._TEXT_DISABLED, self._TEXT_DISABLED),
            )
        if hasattr(self, "seg_motion_pattern"):
            self.seg_motion_pattern.configure(
                fg_color=self._SURFACE_SUBTLE,
                selected_color=self._ACCENT,
                selected_hover_color=self._ACCENT_HOVER,
                unselected_color=self._BTN_SECONDARY,
                unselected_hover_color=self._BTN_SECONDARY_HOVER,
                text_color=(self._TEXT_BODY, self._TEXT_BODY),
                text_color_disabled=(self._TEXT_DISABLED, self._TEXT_DISABLED),
            )
        if hasattr(self, "_seg_ui_theme"):
            self._seg_ui_theme.configure(
                fg_color=self._SURFACE_SUBTLE,
                selected_color=self._ACCENT,
                selected_hover_color=self._ACCENT_HOVER,
                unselected_color=self._SURFACE_SUBTLE,
                unselected_hover_color=self._SURFACE_SUBTLE_HOVER,
                text_color=(self._TEXT_BODY, self._TEXT_ON_ACCENT),
            )
        if hasattr(self, "_lang_seg"):
            self._lang_seg.configure(
                fg_color=self._SURFACE_SUBTLE,
                selected_color=self._ACCENT,
                selected_hover_color=self._ACCENT_HOVER,
                unselected_color=self._SURFACE_SUBTLE,
                unselected_hover_color=self._SURFACE_SUBTLE_HOVER,
                text_color=(self._TEXT_BODY, self._TEXT_ON_ACCENT),
            )

        if hasattr(self, "btn_start"):
            self.btn_start.configure(
                fg_color=self._ACCENT,
                hover_color=self._ACCENT_HOVER,
                text_color=(self._TEXT_ON_ACCENT, self._TEXT_ON_ACCENT),
            )
        if hasattr(self, "btn_stop"):
            self.btn_stop.configure(
                fg_color="transparent",
                hover_color=self._NAV_HOVER,
                text_color=(self._NAV_TEXT, self._NAV_TEXT),
            )
        if hasattr(self, "btn_open_config"):
            self.btn_open_config.configure(
                fg_color="transparent",
                hover_color=self._NAV_HOVER,
                text_color=(self._NAV_TEXT, self._NAV_TEXT),
            )
        if hasattr(self, "swt_tray"):
            if self._ui_theme == "dark":
                self.swt_tray.configure(
                    fg_color=self._BORDER,
                    progress_color=self._ACCENT,
                    button_color="#C9D1D9",
                    button_hover_color="#8B949E",
                )
            else:
                self.swt_tray.configure(
                    fg_color=self._BORDER,
                    progress_color=self._ACCENT,
                    button_color="#FFFFFF",
                    button_hover_color="#F3F4F6",
                )
        if hasattr(self, "swt_autostart"):
            if self._ui_theme == "dark":
                self.swt_autostart.configure(
                    fg_color=self._BORDER,
                    progress_color=self._ACCENT,
                    button_color="#C9D1D9",
                    button_hover_color="#8B949E",
                )
            else:
                self.swt_autostart.configure(
                    fg_color=self._BORDER,
                    progress_color=self._ACCENT,
                    button_color="#FFFFFF",
                    button_hover_color="#F3F4F6",
                )
        if hasattr(self, "swt_schedule"):
            if self._ui_theme == "dark":
                self.swt_schedule.configure(
                    fg_color=self._BORDER,
                    progress_color=self._ACCENT,
                    button_color="#C9D1D9",
                    button_hover_color="#8B949E",
                )
            else:
                self.swt_schedule.configure(
                    fg_color=self._BORDER,
                    progress_color=self._ACCENT,
                    button_color="#FFFFFF",
                    button_hover_color="#F3F4F6",
                )
        if hasattr(self, "_interval_preset_btns"):
            for b in self._interval_preset_btns:
                b.configure(
                    fg_color=self._SURFACE_SUBTLE,
                    hover_color=self._SURFACE_SUBTLE_HOVER,
                    text_color=(self._TEXT_BODY, self._TEXT_BODY),
                )

        for name in (
            "_lbl_settings_title",
            "_lbl_analytics_title",
            "_lbl_interval",
            "_lbl_interval_presets",
            "_lbl_pixels",
            "_lbl_path_speed",
            "_lbl_motion_pattern",
            "_lbl_chart_triggers",
            "_lbl_chart_runtime",
            "_lbl_chart_patterns",
            "_lbl_lang",
            "_lbl_appearance",
            "_lbl_log_title",
            "_lbl_tray_sw",
            "_lbl_autostart_sw",
            "_lbl_schedule_sw",
        ):
            if hasattr(self, name):
                w = getattr(self, name)
                if name in ("_lbl_settings_title", "_lbl_analytics_title"):
                    w.configure(text_color=(self._TEXT_TITLE, self._TEXT_TITLE))
                else:
                    w.configure(text_color=(self._TEXT_BODY, self._TEXT_BODY))

        for name in (
            "_lbl_pixels_hint",
            "_lbl_path_speed_hint",
            "_hint_tray",
            "_hint_autostart",
            "_hint_schedule",
        ):
            if hasattr(self, name):
                getattr(self, name).configure(text_color=self._TEXT_MUTED)
        if hasattr(self, "_lbl_interval_hint"):
            self._lbl_interval_hint.configure(text_color=self._TEXT_MUTED)
        if hasattr(self, "_lbl_analytics_sub"):
            self._lbl_analytics_sub.configure(text_color=self._TEXT_MUTED)
        if hasattr(self, "_lbl_interval_presets"):
            self._lbl_interval_presets.configure(
                text_color=(self._TEXT_MUTED, self._TEXT_MUTED)
            )

        if hasattr(self, "log_text"):
            self.log_text.configure(
                fg_color=self._ENTRY_BG,
                text_color=(self._TEXT_LOG, self._TEXT_LOG),
                border_color=self._ENTRY_BORDER,
            )
        if hasattr(self, "analytics_log"):
            self.analytics_log.configure(
                fg_color=self._ENTRY_BG,
                text_color=(self._TEXT_LOG, self._TEXT_LOG),
                border_color=self._ENTRY_BORDER,
            )

        if hasattr(self, "_seg_analytics_range"):
            self._seg_analytics_range.configure(
                fg_color=self._SURFACE_SUBTLE,
                selected_color=self._ACCENT,
                selected_hover_color=self._ACCENT_HOVER,
                unselected_color=self._SURFACE_SUBTLE,
                unselected_hover_color=self._SURFACE_SUBTLE_HOVER,
                text_color=(self._TEXT_BODY, self._TEXT_ON_ACCENT),
            )

        if hasattr(self, "_fig_trigger"):
            self._refresh_analytics_charts()

        if self._stop.is_set() or not (self._worker and self._worker.is_alive()):
            self._apply_status_chrome("stopped")
        else:
            self._refresh_running_status_from_countdown()

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

        self.root.title(self._t("window_title"))
        self.root.geometry("920x640")
        self.root.minsize(860, 580)
        self.root.configure(fg_color=self._MAIN_BG)
        self._window_icon_photo: tk.PhotoImage | None = None
        self._apply_window_icon()

        self._nav_icons = self._build_nav_icons()

        self._stop = threading.Event()
        self._worker: threading.Thread | None = None
        self._next_jiggle_monotonic = 0.0
        self._interval_unit: nudge_logic.IntervalUnit = "min"
        self._running_interval_value = 0.0
        self._running_interval_unit: nudge_logic.IntervalUnit = "min"
        self._current_interval_sec = 0.0
        self._countdown_after_id: str | None = None
        self._countdown_phase: Literal["interval", "burst", "schedule"] = "interval"
        self.status = tk.StringVar(value=self._t("status_stopped"))
        self._schedule_resume_at: datetime | None = None
        self._run_schedule_window = False

        self._tray = TrayController()
        self._shutting_down = False
        self._config_save_after_id: str | None = None
        self._config_loading = False
        self._intro_acknowledged = True
        self._motion_pattern: MotionPattern = "horizontal"

        self._analytics_trigger_mode: Literal["today", "week"] = "today"
        self._analytics_runtime_anchor = 0.0
        self._analytics_runtime_after_id: str | None = None

        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main()

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
            return pkg_version("try-working-hard")
        except Exception:
            return "1.0.0"

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

    def _a11y_label_focus_entry(self, label: ctk.CTkLabel, entry: ctk.CTkEntry) -> None:
        try:
            label.configure(cursor="hand2")
        except (tk.TclError, AttributeError):
            pass

        def _on_click(_: object) -> None:
            if self._shutting_down:
                return
            try:
                entry.focus_set()
            except (tk.TclError, AttributeError):
                pass

        label.bind("<Button-1>", _on_click)

    def _setup_a11y(self) -> None:
        self.root.bind_all("<F1>", self._a11y_help)
        self.root.bind_all("<F2>", self._a11y_f2)
        self.root.bind_all("<F3>", self._a11y_f3)
        self.root.bind_all("<F4>", self._a11y_f4)
        self.root.bind_all("<KeyPress-F5>", self._a11y_f5)
        self.root.bind_all("<F6>", self._a11y_f6)
        self.root.bind_all("<Return>", self._a11y_return)
        self.root.bind_all("<Escape>", self._a11y_escape)
        self.root.after(120, self._a11y_initial_focus)

    def _a11y_initial_focus(self) -> None:
        if self._shutting_down:
            return
        try:
            self.entry_minutes.focus_set()
        except (tk.TclError, AttributeError):
            pass

    def _a11y_help(self, _e: object | None = None) -> str | None:
        messagebox.showinfo(
            self._t("a11y_help_title"),
            self._t("a11y_help_body", version=self._pkg_version()),
            parent=self.root,
        )
        return "break"

    def _a11y_f2(self, _e: object | None = None) -> str | None:
        self._on_nav("home")
        return "break"

    def _a11y_f3(self, _e: object | None = None) -> str | None:
        self._on_nav("settings")
        return "break"

    def _a11y_f4(self, _e: object | None = None) -> str | None:
        self._on_nav("analytics")
        return "break"

    def _a11y_f5(self, e: tk.Event) -> str | None:
        if self._shutting_down:
            return
        is_shift = bool((e.state or 0) & 0x1)
        if is_shift:
            self._a11y_try_stop()
        else:
            self._a11y_try_start()
        return "break"

    def _a11y_f6(self, _e: object | None = None) -> str | None:
        if self._active_nav != "home":
            self._on_nav("home")
        self._nav_to_mode("log" if self._segment_mode == "control" else "control")
        return "break"

    def _is_main_window_visible(self) -> bool:
        """True when the main window is mapped (not minimized to the tray)."""
        if self._shutting_down:
            return False
        try:
            return bool(self.root.winfo_viewable())
        except tk.TclError:
            return False

    def _a11y_return(self, _e: object | None = None) -> str | None:
        if not self._is_main_window_visible():
            return
        self._a11y_try_start()
        return "break"

    def _a11y_escape(self, _e: object | None = None) -> str | None:
        if not self._is_main_window_visible():
            return
        self._a11y_try_stop()
        return "break"

    def _a11y_try_start(self) -> None:
        if self._active_nav != "home" or self._segment_mode != "control":
            return
        try:
            st = str(self.btn_start.cget("state")).lower()
        except (tk.TclError, AttributeError):
            return
        if st == "disabled" or (st.isdigit() and st == "0"):
            return
        self._on_start()

    def _a11y_try_stop(self) -> None:
        if self._active_nav != "home" or self._segment_mode != "control":
            return
        try:
            st = str(self.btn_stop.cget("state")).lower()
        except (tk.TclError, AttributeError):
            return
        if st == "disabled" or (st.isdigit() and st == "0"):
            return
        self._on_stop()

    def _t(self, key: str, **kwargs: Any) -> str:
        s = STRINGS[self._lang][key]
        return s.format(**kwargs) if kwargs else s

    def _segment_text(self, mode: Literal["control", "log"]) -> str:
        return self._t("seg_control") if mode == "control" else self._t("seg_log")

    def _mode_from_segment_value(self, value: str) -> Literal["control", "log"]:
        if value == self._t("seg_control"):
            return "control"
        return "log"

    def _t_status_running(self, cd: str) -> str:
        v = self._running_interval_value
        if self._running_interval_unit == "min":
            return self._t("status_running_min", v=v, cd=cd)
        return self._t("status_running_sec", v=v, cd=cd)

    def _sync_interval_unit_seg(self) -> None:
        if not hasattr(self, "seg_interval_unit"):
            return
        try:
            self.seg_interval_unit.configure(
                values=[self._t("interval_unit_min"), self._t("interval_unit_sec")]
            )
            sel = (
                self._t("interval_unit_min")
                if self._interval_unit == "min"
                else self._t("interval_unit_sec")
            )
            self.seg_interval_unit.set(sel)
        except (tk.TclError, AttributeError):
            pass

    def _set_interval_hint(self) -> None:
        if not hasattr(self, "_lbl_interval_hint"):
            return
        key = "interval_hint_min" if self._interval_unit == "min" else "interval_hint_sec"
        try:
            self._lbl_interval_hint.configure(text=self._t(key))
        except (tk.TclError, AttributeError):
            pass

    def _on_interval_unit_seg(self, value: str) -> None:
        if self._shutting_down:
            return
        self._interval_unit = (
            "min" if value == self._t("interval_unit_min") else "sec"
        )
        self._set_interval_hint()
        self._schedule_save_config()

    def _apply_interval_preset(self, value: str, unit: nudge_logic.IntervalUnit) -> None:
        if self._shutting_down:
            return
        self._interval_unit = unit
        self.var_minutes.set(value)
        self._sync_interval_unit_seg()
        self._set_interval_hint()
        self._schedule_save_config()

    def _on_autostart_win_committed(self) -> None:
        if self._shutting_down or self._config_loading:
            return
        if sys.platform != "win32" or not HAS_TRAY:
            return
        _windows_run_autoset(bool(self.var_autostart_win.get()))

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

    def _pattern_log_label(self) -> str:
        return {
            "horizontal": self._t("motion_pattern_log_line"),
            "circle": self._t("motion_pattern_log_circle"),
            "square": self._t("motion_pattern_log_square"),
        }[self._motion_pattern]

    def _on_lang_switch(self, label: str) -> None:
        self._lang = "zh" if label == "繁中" else "en"
        self._apply_language()
        self._schedule_save_config()

    def _apply_loaded_config(self, cfg: dict[str, Any]) -> None:
        lang = cfg.get("lang")
        if lang in ("zh", "en"):
            self._lang = lang  # type: ignore[assignment]
        self.var_minutes.set(str(cfg.get("interval_text", str(int(self.DEFAULT_MINUTES)))))
        u = cfg.get("interval_unit", "min")
        self._interval_unit = u if u in ("min", "sec") else "min"
        self.var_interval_jitter.set(str(cfg.get("interval_jitter_text", "0")))
        self.var_pixels.set(str(cfg.get("pixels_text", str(self.DEFAULT_PIXELS))))
        self.var_path_speed.set(
            str(cfg.get("path_speed_text", str(int(self.DEFAULT_PATH_SPEED))))
        )
        mp = cfg.get("motion_pattern", "horizontal")
        self._motion_pattern = mp if mp in ("horizontal", "circle", "square") else "horizontal"
        self.var_tray_close.set(bool(cfg.get("close_to_tray", False)))
        self.var_schedule_window.set(bool(cfg.get("schedule_window", False)))
        self._run_schedule_window = bool(self.var_schedule_window.get())
        self._intro_acknowledged = bool(cfg.get("intro_acknowledged", True))
        self._lang_seg.set("繁中" if self._lang == "zh" else "English")

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

    def _config_snapshot(self) -> dict[str, Any]:
        return {
            "lang": self._lang,
            "ui_theme": self._ui_theme,
            "interval_text": self.var_minutes.get(),
            "interval_unit": self._interval_unit,
            "interval_jitter_text": self.var_interval_jitter.get(),
            "pixels_text": self.var_pixels.get(),
            "path_speed_text": self.var_path_speed.get(),
            "motion_pattern": self._motion_pattern,
            "close_to_tray": bool(self.var_tray_close.get()),
            "schedule_window": bool(self.var_schedule_window.get()),
            "intro_acknowledged": self._intro_acknowledged,
        }

    def _maybe_show_first_intro(self) -> None:
        if self._shutting_down:
            return
        if self._start_in_tray:
            return
        if self._intro_acknowledged:
            return
        try:
            if not self.root.winfo_exists():
                return
        except tk.TclError:
            return
        messagebox.showinfo(
            self._t("intro_title"),
            self._t("intro_body", version=self._pkg_version()),
            parent=self.root,
        )
        self._reapply_start_maximized()
        self._intro_acknowledged = True
        self._save_config_now()

    def _register_config_persistence(self) -> None:
        def _on_write(*_a: object) -> None:
            self._schedule_save_config()

        def _on_schedule_flag(*_a: object) -> None:
            self._run_schedule_window = bool(self.var_schedule_window.get())
            self._schedule_save_config()

        try:
            self.var_tray_close.trace_add("write", _on_write)
            self.var_minutes.trace_add("write", _on_write)
            self.var_interval_jitter.trace_add("write", _on_write)
            self.var_pixels.trace_add("write", _on_write)
            self.var_path_speed.trace_add("write", _on_write)
            self.var_schedule_window.trace_add("write", _on_schedule_flag)
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

    def _on_open_config_file(self) -> None:
        path = local_config.default_config_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.is_file():
                self._save_config_now()
            if hasattr(os, "startfile"):
                os.startfile(str(path.resolve()))
            else:
                messagebox.showinfo(
                    self._t("settings_title"),
                    self._t("open_config_path_only", path=str(path.resolve())),
                )
        except OSError as e:
            messagebox.showerror(
                self._t("err_title"),
                self._t("err_open_config_file", err=str(e)),
            )

    def _apply_language(self) -> None:
        self.root.title(self._t("window_title"))
        self._lbl_subtitle.configure(text=self._t("app_subtitle"))
        if hasattr(self, "_lbl_appearance"):
            self._lbl_appearance.configure(text=self._t("theme_appearance"))
        self._lbl_lang.configure(text=self._t("lang_ui"))
        self._hint.configure(text=self._theme_footer_text())
        if hasattr(self, "_hint_appearance"):
            self._hint_appearance.configure(text=self._theme_footer_text())
        self._lbl_dashboard.configure(text=self._t("dashboard"))
        self._lbl_interval.configure(text=self._t("interval_label"))
        if hasattr(self, "_lbl_interval_presets"):
            self._lbl_interval_presets.configure(text=self._t("interval_presets_caption"))
        if hasattr(self, "seg_interval_unit"):
            self._sync_interval_unit_seg()
        self._set_interval_hint()
        if hasattr(self, "_lbl_interval_jitter"):
            self._lbl_interval_jitter.configure(text=self._t("interval_jitter_label"))
            self._lbl_interval_jitter_hint.configure(
                text=self._t("interval_jitter_hint", max=self.MAX_INTERVAL_JITTER_SEC)
            )
        if hasattr(self, "_interval_preset_btns") and hasattr(self, "_interval_preset_specs"):
            for b, spec in zip(self._interval_preset_btns, self._interval_preset_specs, strict=True):
                b.configure(text=self._t(spec))
        if hasattr(self, "_lbl_motion_pattern"):
            self._lbl_motion_pattern.configure(text=self._t("motion_pattern_label"))
        self._sync_motion_pattern_seg()
        self._lbl_pixels.configure(text=self._t("pixels_label"))
        self._lbl_pixels_hint.configure(
            text=self._t("pixels_hint", lo=self.MIN_PIXELS, hi=self.MAX_PIXELS)
        )
        if hasattr(self, "_lbl_path_speed"):
            self._lbl_path_speed.configure(text=self._t("path_speed_label"))
            self._lbl_path_speed_hint.configure(
                text=self._t(
                    "path_speed_hint",
                    lo=self.MIN_PATH_SPEED,
                    hi=self.MAX_PATH_SPEED,
                )
            )
        self.btn_start.configure(text=self._t("btn_start"))
        self.btn_stop.configure(text=self._t("btn_stop"))
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
        self._lbl_schedule_sw.configure(text=self._t("schedule_window_title"))
        self._hint_schedule.configure(text=self._t("schedule_window_hint"))
        self._lbl_log_title.configure(text=self._t("log_title"))
        self._lbl_settings_title.configure(text=self._t("settings_title"))
        if hasattr(self, "btn_open_config"):
            self.btn_open_config.configure(text=self._t("btn_open_config_file"))
        self._lbl_analytics_title.configure(text=self._t("analytics_title"))
        self._lbl_analytics_sub.configure(text=self._t("analytics_subtitle"))
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

        if self._stop.is_set() or not (self._worker and self._worker.is_alive()):
            self.status.set(self._t("status_stopped"))
            self._apply_status_chrome("stopped")
        else:
            self._refresh_running_status_from_countdown()

        if hasattr(self, "_fig_trigger"):
            self._refresh_analytics_charts()

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
            self.status.set(self._t("status_motion_burst", cd=cd))
            self._apply_status_chrome("burst")
        else:
            self.status.set(self._t_status_running(cd))
            self._apply_status_chrome("interval")

    def _apply_status_chrome(
        self, kind: Literal["stopped", "interval", "burst", "schedule"]
    ) -> None:
        """Update status strip colors and LED to match schedule state."""
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

    def _btn(self, master: Any, **kwargs: Any) -> ctk.CTkButton:
        """Primary/secondary style buttons (12–16px corner radius)."""
        kw = dict(corner_radius=_R_BTN, font=self._font_body, height=40)
        kw.update(kwargs)
        kw.pop("takefocus", None)  # CTkButton rejects this in **kwargs
        w = ctk.CTkButton(master, **kw)
        return w

    def _build_nav_icons(self) -> dict[str, ctk.CTkImage]:
        """Sidebar nav icons; tint matches unselected nav (gray on light)."""
        specs: list[tuple[str, str]] = [
            ("home", "house"),
            ("settings", "settings"),
            ("analytics", "chart-column"),
        ]
        out: dict[str, ctk.CTkImage] = {}
        for key, stem in specs:
            im = _load_pkg_nav_png(stem)
            if im is not None:
                im = _tint_rgba_image(im, self._NAV_TEXT)
                out[key] = ctk.CTkImage(light_image=im, dark_image=im, size=(20, 20))
            else:
                out[key] = self._nav_icon_fallback(key, self._NAV_TEXT, self._TEXT_MUTED)
        return out

    def _one_nav_ctk_image(
        self, key: str, body_hex: str, muted_hex: str
    ) -> ctk.CTkImage:
        """Single nav icon for the given key and two-tone glyph colors."""
        stems = {
            "home": "house",
            "settings": "settings",
            "analytics": "chart-column",
        }
        stem = stems[key]
        im = _load_pkg_nav_png(stem)
        if im is not None:
            im = _tint_rgba_image(im, body_hex)
            return ctk.CTkImage(light_image=im, dark_image=im, size=(20, 20))
        return self._nav_icon_fallback(key, body_hex, muted_hex)

    def _nav_icon_fallback(self, key: str, ic_body: str, ic_muted: str) -> ctk.CTkImage:
        from PIL import Image, ImageDraw

        def _ic(draw_fn: Any) -> ctk.CTkImage:
            sz = 20
            im = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            draw_fn(d, sz)
            return ctk.CTkImage(light_image=im, dark_image=im, size=(20, 20))

        def house(draw: ImageDraw.ImageDraw, s: int) -> None:
            draw.rectangle([6, 10, s - 6, s - 4], fill=ic_body)
            draw.polygon([(4, 10), (s // 2, 5), (s - 4, 10)], fill=ic_body)

        def gear(draw: ImageDraw.ImageDraw, s: int) -> None:
            cx, cy = s // 2, s // 2
            draw.ellipse([4, 4, s - 4, s - 4], outline=ic_body, width=2)
            draw.ellipse([7, 7, s - 7, s - 7], fill=ic_muted)
            draw.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=ic_body)

        def chart(draw: ImageDraw.ImageDraw, s: int) -> None:
            draw.line([(4, s - 4), (4, 4)], fill=ic_body, width=2)
            draw.line([(4, s - 4), (s - 4, s - 4)], fill=ic_body, width=2)
            draw.rectangle([6, 12, 9, s - 5], fill=ic_muted)
            draw.rectangle([11, 8, 14, s - 5], fill=ic_muted)
            draw.rectangle([16, 6, 19, s - 5], fill=ic_body)

        fn = {"home": house, "settings": gear, "analytics": chart}[key]
        return _ic(fn)

    def _nav_btn(self, master: Any, *, text: str, icon: ctk.CTkImage, command: Any) -> ctk.CTkButton:
        return ctk.CTkButton(
            master,
            text=text,
            image=icon,
            compound="left",
            anchor="w",
            corner_radius=_R,
            height=44,
            font=self._font_body,
            fg_color="transparent",
            hover_color=self._NAV_HOVER,
            text_color=(self._NAV_TEXT, self._NAV_TEXT),
            command=command,
        )

    def _build_sidebar(self) -> None:
        p = self._UI_PAD
        self._sidebar = ctk.CTkFrame(
            self.root,
            width=self._SIDEBAR_WIDTH,
            corner_radius=_R,
            fg_color=self._SIDEBAR_BG,
        )
        self._sidebar.grid(row=0, column=0, sticky="nsew", padx=(p, 0), pady=p)
        self._sidebar.grid_propagate(False)
        sidebar = self._sidebar

        self._brand = ctk.CTkLabel(
            sidebar,
            text="try-working-hard",
            font=self._font_brand,
            text_color=(self._TEXT_TITLE, self._TEXT_TITLE),
            anchor="w",
        )
        self._brand.pack(anchor="w", padx=p, pady=(p, 4))

        self._lbl_subtitle = ctk.CTkLabel(
            sidebar,
            text=self._t("app_subtitle"),
            font=self._font_body,
            text_color=self._TEXT_BODY,
            anchor="w",
        )
        self._lbl_subtitle.pack(anchor="w", padx=p, pady=(0, p))

        ic = self._nav_icons
        self._nav_home = self._nav_btn(
            sidebar,
            text=f"  {self._t('nav_home')}",
            icon=ic["home"],
            command=lambda: self._on_nav("home"),
        )
        self._nav_home.pack(fill="x", padx=p, pady=(0, p))

        self._nav_settings = self._nav_btn(
            sidebar,
            text=f"  {self._t('nav_settings')}",
            icon=ic["settings"],
            command=lambda: self._on_nav("settings"),
        )
        self._nav_settings.pack(fill="x", padx=p, pady=(0, p))

        self._nav_analytics = self._nav_btn(
            sidebar,
            text=f"  {self._t('nav_analytics')}",
            icon=ic["analytics"],
            command=lambda: self._on_nav("analytics"),
        )
        self._nav_analytics.pack(fill="x", padx=p, pady=(0, p))

        spacer = ctk.CTkFrame(sidebar, fg_color="transparent")
        spacer.pack(expand=True, fill="both")

        self._hint = ctk.CTkLabel(
            sidebar,
            text=self._theme_footer_text(),
            font=ctk.CTkFont(family=_FONT_INTER, size=11),
            text_color=self._TEXT_MUTED,
        )
        self._hint.pack(anchor="w", padx=p, pady=(0, p))
        self._sync_nav_highlight()

    def _build_main(self) -> None:
        p = self._UI_PAD
        main = ctk.CTkFrame(self.root, corner_radius=_R, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=(0, p), pady=p)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(0, weight=1)

        self.pages_host = ctk.CTkFrame(main, corner_radius=_R, fg_color="transparent")
        self.pages_host.grid(row=0, column=0, sticky="nsew")
        self.pages_host.grid_columnconfigure(0, weight=1)
        self.pages_host.grid_rowconfigure(0, weight=1)

        self.page_home = ctk.CTkFrame(self.pages_host, corner_radius=_R, fg_color="transparent")
        self.page_home.grid(row=0, column=0, sticky="nsew")
        self.page_home.grid_columnconfigure(0, weight=1)
        self.page_home.grid_rowconfigure(3, weight=1)

        self._status_strip = ctk.CTkFrame(
            self.page_home,
            corner_radius=_R,
            fg_color=self._STATUS_STRIP_BG_STOP,
            border_width=1,
            border_color=self._STATUS_STRIP_BORDER_STOP,
        )
        self._status_strip.grid(row=0, column=0, sticky="ew", padx=p, pady=(p, 8))
        self._status_strip.grid_columnconfigure(0, weight=1)
        status_inner = ctk.CTkFrame(self._status_strip, fg_color="transparent")
        status_inner.grid(row=0, column=0, sticky="ew", padx=14, pady=12)
        status_inner.grid_columnconfigure(1, weight=1)
        self._status_led = ctk.CTkLabel(
            status_inner,
            text="\u25cf",
            font=ctk.CTkFont(family=_FONT_INTER, size=12, weight="bold"),
            text_color=(self._STATUS_LED_STOP, self._STATUS_LED_STOP),
            width=18,
        )
        self._status_led.grid(row=0, column=0, sticky="nw", padx=(0, 10), pady=2)
        self._lbl_status = ctk.CTkLabel(
            status_inner,
            textvariable=self.status,
            font=self._font_body,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            anchor="w",
            justify="left",
        )
        self._lbl_status.grid(row=0, column=1, sticky="ew")

        head = ctk.CTkFrame(self.page_home, fg_color="transparent")
        head.grid(row=1, column=0, sticky="ew", padx=p, pady=(0, p))
        head.grid_columnconfigure(0, weight=1)

        self._lbl_dashboard = ctk.CTkLabel(
            head,
            text=self._t("dashboard"),
            font=self._font_title,
            text_color=(self._TEXT_TITLE, self._TEXT_TITLE),
        )
        self._lbl_dashboard.grid(row=0, column=0, sticky="w")

        self.segmented = ctk.CTkSegmentedButton(
            head,
            values=[self._t("seg_control"), self._t("seg_log")],
            command=self._on_segment,
            corner_radius=_R,
            font=self._font_body_bold,
            height=38,
            fg_color=self._SURFACE_SUBTLE,
            selected_color=self._ACCENT,
            selected_hover_color=self._ACCENT_HOVER,
            unselected_color=self._SURFACE_SUBTLE,
            unselected_hover_color=self._SURFACE_SUBTLE_HOVER,
            text_color=(self._TEXT_BODY, self._TEXT_ON_ACCENT),
            text_color_disabled=(self._TEXT_DISABLED, self._TEXT_DISABLED),
        )
        _try_takefocus(self.segmented, 1)
        self.segmented.grid(row=0, column=1, sticky="e")
        self.segmented.set(self._segment_text(self._segment_mode))

        self.content_host = ctk.CTkFrame(self.page_home, fg_color="transparent")
        self.content_host.grid(row=3, column=0, sticky="nsew", padx=p, pady=(0, p))
        self.content_host.grid_columnconfigure(0, weight=1)
        self.content_host.grid_rowconfigure(0, weight=1)

        self.frame_control = ctk.CTkScrollableFrame(
            self.content_host,
            fg_color=self._CARD_BG,
            corner_radius=_R,
            border_width=1,
            border_color=self._CARD_BORDER,
            scrollbar_button_color=self._BTN_SECONDARY,
            scrollbar_button_hover_color=self._BTN_SECONDARY_HOVER,
        )
        self.frame_control.grid(row=0, column=0, sticky="nsew")
        self.frame_control.grid_columnconfigure(0, weight=1)
        self._fill_control_panel(self.frame_control)

        self.frame_log = ctk.CTkFrame(
            self.content_host,
            fg_color=self._CARD_BG,
            corner_radius=_R,
            border_width=1,
            border_color=self._CARD_BORDER,
        )
        self._fill_log_panel(self.frame_log)
        self.frame_log.grid_remove()

        self.page_settings = ctk.CTkFrame(
            self.pages_host,
            corner_radius=_R,
            fg_color=self._CARD_BG,
            border_width=1,
            border_color=self._CARD_BORDER,
        )
        self._fill_settings_panel(self.page_settings)

        self.page_analytics = ctk.CTkFrame(
            self.pages_host,
            corner_radius=_R,
            fg_color=self._CARD_BG,
            border_width=1,
            border_color=self._CARD_BORDER,
        )
        self._fill_analytics_panel(self.page_analytics)

        self.page_settings.grid_remove()
        self.page_analytics.grid_remove()

    def _on_nav(self, page: Literal["home", "settings", "analytics"]) -> None:
        self._active_nav = page
        self._sync_nav_highlight()
        self.page_home.grid_remove()
        self.page_settings.grid_remove()
        self.page_analytics.grid_remove()
        if page == "home":
            self.page_home.grid(row=0, column=0, sticky="nsew")
            self._apply_view()
        elif page == "settings":
            self.page_settings.grid(row=0, column=0, sticky="nsew")
        else:
            self.page_analytics.grid(row=0, column=0, sticky="nsew")
            self._sync_analytics_log_from_main()
            self._refresh_analytics_charts()

    def _sync_nav_highlight(self) -> None:
        for key, btn in (
            ("home", self._nav_home),
            ("settings", self._nav_settings),
            ("analytics", self._nav_analytics),
        ):
            if key == self._active_nav:
                icon = self._one_nav_ctk_image(
                    key, self._NAV_ON_SELECTED, self._TEXT_BODY
                )
                btn.configure(
                    image=icon,
                    fg_color=self._NAV_SELECTED,
                    hover_color=self._ACCENT_HOVER,
                    text_color=(self._NAV_ON_SELECTED, self._NAV_ON_SELECTED),
                )
            else:
                icon = self._one_nav_ctk_image(
                    key, self._NAV_TEXT, self._TEXT_MUTED
                )
                btn.configure(
                    image=icon,
                    fg_color="transparent",
                    hover_color=self._NAV_HOVER,
                    text_color=(self._NAV_TEXT, self._NAV_TEXT),
                )

    def _fill_settings_panel(self, card: ctk.CTkFrame) -> None:
        p = self._UI_PAD
        card.grid_columnconfigure(0, weight=1)

        self._lbl_settings_title = ctk.CTkLabel(
            card,
            text=self._t("settings_title"),
            font=self._font_title,
            text_color=(self._TEXT_TITLE, self._TEXT_TITLE),
        )
        self._lbl_settings_title.grid(row=0, column=0, sticky="w", padx=p, pady=(p, p))

        self._lbl_appearance = ctk.CTkLabel(
            card,
            text=self._t("theme_appearance"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            anchor="w",
        )
        self._lbl_appearance.grid(row=1, column=0, sticky="w", padx=p, pady=(0, p))

        self._seg_ui_theme = ctk.CTkSegmentedButton(
            card,
            values=[
                self._t("theme_appearance_dark"),
                self._t("theme_appearance_light"),
            ],
            command=self._on_ui_theme_seg,
            corner_radius=_R,
            font=self._font_body_bold,
            height=36,
            fg_color=self._SURFACE_SUBTLE,
            selected_color=self._ACCENT,
            selected_hover_color=self._ACCENT_HOVER,
            unselected_color=self._SURFACE_SUBTLE,
            unselected_hover_color=self._SURFACE_SUBTLE_HOVER,
            text_color=(self._TEXT_BODY, self._TEXT_ON_ACCENT),
        )
        self._seg_ui_theme.grid(row=2, column=0, sticky="ew", padx=p, pady=(0, p))
        self._sync_ui_theme_seg()
        _try_takefocus(self._seg_ui_theme, 1)

        self._hint_appearance = ctk.CTkLabel(
            card,
            text=self._theme_footer_text(),
            font=ctk.CTkFont(family=_FONT_INTER, size=11),
            text_color=self._TEXT_MUTED,
            anchor="w",
        )
        self._hint_appearance.grid(row=3, column=0, sticky="w", padx=p, pady=(p, p))

        self._lbl_lang = ctk.CTkLabel(
            card,
            text=self._t("lang_ui"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            anchor="w",
        )
        self._lbl_lang.grid(row=4, column=0, sticky="w", padx=p, pady=(0, p))

        self._lang_seg = ctk.CTkSegmentedButton(
            card,
            values=["繁中", "English"],
            command=self._on_lang_switch,
            corner_radius=_R,
            font=self._font_body_bold,
            height=36,
            fg_color=self._SURFACE_SUBTLE,
            selected_color=self._ACCENT,
            selected_hover_color=self._ACCENT_HOVER,
            unselected_color=self._SURFACE_SUBTLE,
            unselected_hover_color=self._SURFACE_SUBTLE_HOVER,
            text_color=(self._TEXT_BODY, self._TEXT_ON_ACCENT),
        )
        self._lang_seg.grid(row=5, column=0, sticky="ew", padx=p, pady=(0, p))
        self._lang_seg.set("English")
        _try_takefocus(self._lang_seg, 1)

        self.btn_open_config = self._btn(
            card,
            text=self._t("btn_open_config_file"),
            command=self._on_open_config_file,
            fg_color="transparent",
            hover_color=self._NAV_HOVER,
            text_color=(self._NAV_TEXT, self._NAV_TEXT),
            anchor="w",
        )
        self.btn_open_config.grid(row=6, column=0, sticky="w", padx=p, pady=(0, p))
        _try_takefocus(self.btn_open_config, 1)

        self.var_tray_close = tk.BooleanVar(value=False)
        tray_row = ctk.CTkFrame(card, fg_color="transparent")
        tray_row.grid(row=7, column=0, sticky="ew", padx=p, pady=(0, 8))
        tray_row.grid_columnconfigure(0, weight=1)

        self._lbl_tray_sw = ctk.CTkLabel(
            tray_row,
            text=self._t("tray_switch_title"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            anchor="w",
        )
        self._lbl_tray_sw.grid(row=0, column=0, sticky="w")

        self.swt_tray = ctk.CTkSwitch(
            tray_row,
            text="",
            variable=self.var_tray_close,
            width=52,
            switch_width=40,
            switch_height=22,
            fg_color=self._BORDER,
            progress_color=self._ACCENT,
            button_color="#FFFFFF",
            button_hover_color="#F3F4F6",
            font=self._font_body,
        )
        self.swt_tray.grid(row=0, column=1, sticky="e", padx=(16, 0))
        _try_takefocus(self.swt_tray, 1)

        tray_hint = self._t("tray_switch_hint")
        if not HAS_TRAY:
            tray_hint += self._t("tray_no_pystray")
        self._hint_tray = ctk.CTkLabel(
            card,
            text=tray_hint,
            font=self._font_hint,
            text_color=self._TEXT_MUTED,
            anchor="w",
            justify="left",
            wraplength=520,
        )
        self._hint_tray.grid(row=8, column=0, sticky="ew", padx=p, pady=(0, p))
        if not HAS_TRAY:
            self.swt_tray.configure(state="disabled")

        can_autowin = sys.platform == "win32" and HAS_TRAY
        self.var_autostart_win = tk.BooleanVar(
            value=bool(can_autowin and _windows_run_autostart_active())
        )
        autostart_row = ctk.CTkFrame(card, fg_color="transparent")
        autostart_row.grid(row=9, column=0, sticky="ew", padx=p, pady=(0, 8))
        autostart_row.grid_columnconfigure(0, weight=1)

        self._lbl_autostart_sw = ctk.CTkLabel(
            autostart_row,
            text=self._t("autostart_switch_title"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            anchor="w",
        )
        self._lbl_autostart_sw.grid(row=0, column=0, sticky="w")

        self.swt_autostart = ctk.CTkSwitch(
            autostart_row,
            text="",
            variable=self.var_autostart_win,
            width=52,
            switch_width=40,
            switch_height=22,
            fg_color=self._BORDER,
            progress_color=self._ACCENT,
            button_color="#FFFFFF",
            button_hover_color="#F3F4F6",
            font=self._font_body,
            command=self._on_autostart_win_committed,
        )
        self.swt_autostart.grid(row=0, column=1, sticky="e", padx=(16, 0))
        _try_takefocus(self.swt_autostart, 1)

        a_hint = self._t("autostart_switch_hint")
        if sys.platform != "win32":
            a_hint += self._t("autostart_not_windows")
        elif not HAS_TRAY:
            a_hint += self._t("autostart_requires_tray")
        self._hint_autostart = ctk.CTkLabel(
            card,
            text=a_hint,
            font=self._font_hint,
            text_color=self._TEXT_MUTED,
            anchor="w",
            justify="left",
            wraplength=520,
        )
        self._hint_autostart.grid(row=10, column=0, sticky="ew", padx=p, pady=(0, p))
        if not can_autowin:
            self.swt_autostart.configure(state="disabled")

    def _fill_analytics_panel(self, card: ctk.CTkFrame) -> None:
        from matplotlib.figure import Figure

        p = self._UI_PAD
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(2, weight=1)

        self._lbl_analytics_title = ctk.CTkLabel(
            card,
            text=self._t("analytics_title"),
            font=self._font_title,
            text_color=(self._TEXT_TITLE, self._TEXT_TITLE),
        )
        self._lbl_analytics_title.grid(row=0, column=0, sticky="w", padx=p, pady=(p, p))

        self._lbl_analytics_sub = ctk.CTkLabel(
            card,
            text=self._t("analytics_subtitle"),
            font=self._font_body,
            text_color=self._TEXT_MUTED,
            anchor="w",
        )
        self._lbl_analytics_sub.grid(row=1, column=0, sticky="w", padx=p, pady=(0, p))

        self.analytics_scroll = ctk.CTkScrollableFrame(
            card,
            fg_color=self._CARD_BG,
            corner_radius=_R,
            border_width=1,
            border_color=self._CARD_BORDER,
            scrollbar_button_color=self._BTN_SECONDARY,
            scrollbar_button_hover_color=self._BTN_SECONDARY_HOVER,
        )
        self.analytics_scroll.grid(row=2, column=0, sticky="nsew", padx=p, pady=(0, p))
        self.analytics_scroll.grid_columnconfigure(0, weight=1)

        self._analytics_trigger_mode = "today"

        self._lbl_chart_triggers = ctk.CTkLabel(
            self.analytics_scroll,
            text=self._t("analytics_chart_triggers"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            anchor="w",
        )
        self._lbl_chart_triggers.grid(row=0, column=0, sticky="w", padx=p, pady=(p, 4))

        seg_row = ctk.CTkFrame(self.analytics_scroll, fg_color="transparent")
        seg_row.grid(row=1, column=0, sticky="ew", padx=p, pady=(0, p))
        vt = self._t("analytics_range_today")
        vw = self._t("analytics_range_week")
        self._seg_analytics_range = ctk.CTkSegmentedButton(
            seg_row,
            values=[vt, vw],
            command=self._on_analytics_trigger_range,
            corner_radius=_R,
            font=self._font_body,
            height=34,
            fg_color=self._SURFACE_SUBTLE,
            selected_color=self._ACCENT,
            selected_hover_color=self._ACCENT_HOVER,
            unselected_color=self._SURFACE_SUBTLE,
            unselected_hover_color=self._SURFACE_SUBTLE_HOVER,
            text_color=(self._TEXT_BODY, self._TEXT_ON_ACCENT),
        )
        self._seg_analytics_range.pack(side="left")
        self._seg_analytics_range.set(vt)
        _try_takefocus(self._seg_analytics_range, 1)

        trig_host = tk.Frame(self.analytics_scroll, bg=self._CARD_BG)
        trig_host.grid(row=2, column=0, sticky="ew", padx=p, pady=(0, p))

        self._fig_trigger = Figure(figsize=(6.5, 2.85), dpi=100)
        self._mpl_canvas_trigger = analytics_charts.attach_canvas(self._fig_trigger, trig_host)

        self._lbl_chart_runtime = ctk.CTkLabel(
            self.analytics_scroll,
            text=self._t("analytics_chart_runtime"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            anchor="w",
        )
        self._lbl_chart_runtime.grid(row=3, column=0, sticky="w", padx=p, pady=(p, 4))

        run_host = tk.Frame(self.analytics_scroll, bg=self._CARD_BG)
        run_host.grid(row=4, column=0, sticky="ew", padx=p, pady=(0, p))

        self._fig_runtime = Figure(figsize=(6.5, 2.85), dpi=100)
        self._mpl_canvas_runtime = analytics_charts.attach_canvas(self._fig_runtime, run_host)

        self._lbl_chart_patterns = ctk.CTkLabel(
            self.analytics_scroll,
            text=self._t("analytics_chart_patterns"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            anchor="w",
        )
        self._lbl_chart_patterns.grid(row=5, column=0, sticky="w", padx=p, pady=(p, 4))

        pie_host = tk.Frame(self.analytics_scroll, bg=self._CARD_BG)
        pie_host.grid(row=6, column=0, sticky="ew", padx=p, pady=(0, p))

        self._fig_patterns = Figure(figsize=(6.5, 2.95), dpi=100)
        self._mpl_canvas_patterns = analytics_charts.attach_canvas(self._fig_patterns, pie_host)

        self.analytics_log = ctk.CTkTextbox(
            card,
            corner_radius=_R,
            font=self._font_mono,
            fg_color=self._ENTRY_BG,
            text_color=(self._TEXT_LOG, self._TEXT_LOG),
            border_width=1,
            border_color=self._ENTRY_BORDER,
            height=150,
        )
        self.analytics_log.grid(row=3, column=0, sticky="ew", padx=p, pady=(0, p))
        self.analytics_log.configure(state="disabled")
        _try_takefocus(self.analytics_log, 1)

        self._refresh_analytics_charts()

    def _sync_analytics_log_from_main(self) -> None:
        try:
            body = self.log_text.get("0.0", "end-1c")
        except tk.TclError:
            return
        self.analytics_log.configure(state="normal")
        self.analytics_log.delete("0.0", "end")
        if body:
            self.analytics_log.insert("0.0", body)
        self.analytics_log.configure(state="disabled")
        self.analytics_log.see("end")

    def _palette_for_charts(self) -> analytics_charts.ChartPalette:
        return analytics_charts.ChartPalette(
            fig_face=self._CARD_BG,
            ax_face=self._ENTRY_BG,
            text=self._TEXT_BODY,
            muted=self._TEXT_MUTED,
            accent=self._ACCENT,
            grid=self._BORDER,
            tick=self._TEXT_MUTED,
        )

    def _refresh_analytics_charts(self) -> None:
        if not hasattr(self, "_fig_trigger"):
            return
        try:
            days_map = analytics_store.load_days_copy()
        except OSError:
            days_map = {}
        today_key = date.today().isoformat()
        palette = self._palette_for_charts()
        mode = self._analytics_trigger_mode
        analytics_charts.render_trigger_figure(
            self._fig_trigger,
            palette=palette,
            mode=mode,
            days_map=days_map,
            today_key=today_key,
            empty_msg=self._t("analytics_empty"),
            xlabel_today=self._t("analytics_axis_hour"),
            xlabel_week=self._t("analytics_axis_day"),
            ylabel=self._t("analytics_axis_count"),
        )
        self._mpl_canvas_trigger.draw()
        analytics_charts.render_runtime_figure(
            self._fig_runtime,
            palette=palette,
            days_map=days_map,
            today_key=today_key,
            empty_msg=self._t("analytics_empty"),
            xlabel=self._t("analytics_axis_day"),
            ylabel_min=self._t("analytics_axis_runtime_min"),
            bar_days=14,
        )
        self._mpl_canvas_runtime.draw()
        labels = (
            self._t("motion_pattern_line"),
            self._t("motion_pattern_circle"),
            self._t("motion_pattern_square"),
        )
        analytics_charts.render_patterns_figure(
            self._fig_patterns,
            palette=palette,
            days_map=days_map,
            labels=labels,
            empty_msg=self._t("analytics_empty"),
        )
        self._mpl_canvas_patterns.draw()

    def _tick_analytics_charts_loop(self) -> None:
        if self._shutting_down:
            return
        if self._active_nav == "analytics":
            try:
                self._refresh_analytics_charts()
            except Exception:
                pass
        self.root.after(5000, self._tick_analytics_charts_loop)

    def _on_analytics_trigger_range(self, value: str) -> None:
        vt = self._t("analytics_range_today")
        self._analytics_trigger_mode = "today" if value == vt else "week"
        self._refresh_analytics_charts()

    def _cancel_analytics_runtime_flush(self) -> None:
        if self._analytics_runtime_after_id is not None:
            try:
                self.root.after_cancel(self._analytics_runtime_after_id)
            except (tk.TclError, ValueError):
                pass
            self._analytics_runtime_after_id = None

    def _schedule_next_runtime_flush(self) -> None:
        self._cancel_analytics_runtime_flush()
        self._analytics_runtime_after_id = self.root.after(
            60000, self._analytics_runtime_flush_tick
        )

    def _analytics_runtime_flush_tick(self) -> None:
        self._analytics_runtime_after_id = None
        if self._shutting_down:
            return
        if self._worker is None or not self._worker.is_alive() or self._stop.is_set():
            return
        now = time.monotonic()
        delta = max(0.0, now - self._analytics_runtime_anchor)
        self._analytics_runtime_anchor = now
        if delta > 0:
            analytics_store.add_runtime_seconds(delta)
        self._schedule_next_runtime_flush()

    def _flush_runtime_segment(self) -> None:
        if self._analytics_runtime_anchor <= 0:
            return
        now = time.monotonic()
        delta = max(0.0, now - self._analytics_runtime_anchor)
        self._analytics_runtime_anchor = 0.0
        if delta > 0:
            analytics_store.add_runtime_seconds(delta)

    def _fill_control_panel(self, card: ctk.CTkFrame | ctk.CTkScrollableFrame) -> None:
        card.grid_columnconfigure(0, weight=1)
        p = self._UI_PAD

        self._lbl_interval = ctk.CTkLabel(
            card,
            text=self._t("interval_label"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
        )
        self._lbl_interval.grid(row=0, column=0, sticky="w", padx=p, pady=(p, p))
        row1 = ctk.CTkFrame(card, fg_color="transparent")
        row1.grid(row=1, column=0, sticky="ew", padx=p, pady=(0, p))
        self.var_minutes = tk.StringVar(value=str(int(self.DEFAULT_MINUTES)))
        self.entry_minutes = ctk.CTkEntry(
            row1,
            textvariable=self.var_minutes,
            width=120,
            height=40,
            corner_radius=_R,
            font=self._font_body,
            fg_color=self._ENTRY_BG,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            border_width=1,
            border_color=self._ENTRY_BORDER,
        )
        self.entry_minutes.pack(side="left")
        _try_takefocus(self.entry_minutes, 1)
        self.seg_interval_unit = ctk.CTkSegmentedButton(
            row1,
            values=[self._t("interval_unit_min"), self._t("interval_unit_sec")],
            command=self._on_interval_unit_seg,
            corner_radius=_R,
            font=self._font_body,
            height=38,
            fg_color=self._SURFACE_SUBTLE,
            selected_color=self._ACCENT,
            selected_hover_color=self._ACCENT_HOVER,
            unselected_color=self._SURFACE_SUBTLE,
            unselected_hover_color=self._SURFACE_SUBTLE_HOVER,
            text_color=(self._TEXT_BODY, self._TEXT_ON_ACCENT),
            text_color_disabled=(self._TEXT_DISABLED, self._TEXT_DISABLED),
        )
        _try_takefocus(self.seg_interval_unit, 1)
        self.seg_interval_unit.pack(side="left", padx=(8, 0))
        self._sync_interval_unit_seg()
        self._lbl_interval_hint = ctk.CTkLabel(
            row1, font=self._font_body, text_color=self._TEXT_MUTED
        )
        self._lbl_interval_hint.pack(side="left", padx=(12, 0))
        self._set_interval_hint()
        self._a11y_label_focus_entry(self._lbl_interval, self.entry_minutes)

        self._lbl_interval_presets = ctk.CTkLabel(
            card,
            text=self._t("interval_presets_caption"),
            font=self._font_body,
            text_color=(self._TEXT_MUTED, self._TEXT_MUTED),
            anchor="w",
        )
        self._lbl_interval_presets.grid(row=2, column=0, sticky="w", padx=p, pady=(0, 2))
        preset_row = ctk.CTkFrame(card, fg_color="transparent")
        preset_row.grid(row=3, column=0, sticky="w", padx=p, pady=(0, p))
        self._interval_preset_specs = [
            "interval_preset_30s",
            "interval_preset_1m",
            "interval_preset_5m",
            "interval_preset_10m",
        ]
        self._interval_preset_btns = []
        for spec, (pv, punit) in zip(
            self._interval_preset_specs,
            (("30", "sec"), ("1", "min"), ("5", "min"), ("10", "min")),
            strict=True,
        ):
            b = self._btn(
                preset_row,
                text=self._t(spec),
                width=60,
                height=34,
                font=self._font_body,
                fg_color=self._SURFACE_SUBTLE,
                hover_color=self._SURFACE_SUBTLE_HOVER,
                text_color=(self._TEXT_BODY, self._TEXT_BODY),
                command=lambda v=pv, u=punit: self._apply_interval_preset(v, u),
            )
            b.pack(side="left", padx=(0, 6))
            self._interval_preset_btns.append(b)

        self._lbl_interval_jitter = ctk.CTkLabel(
            card,
            text=self._t("interval_jitter_label"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
        )
        self._lbl_interval_jitter.grid(row=4, column=0, sticky="w", padx=p, pady=(p, p))
        row_jitter = ctk.CTkFrame(card, fg_color="transparent")
        row_jitter.grid(row=5, column=0, sticky="ew", padx=p, pady=(0, p))
        self.var_interval_jitter = tk.StringVar(value="0")
        self.entry_interval_jitter = ctk.CTkEntry(
            row_jitter,
            textvariable=self.var_interval_jitter,
            width=120,
            height=40,
            corner_radius=_R,
            font=self._font_body,
            fg_color=self._ENTRY_BG,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            border_width=1,
            border_color=self._ENTRY_BORDER,
        )
        self.entry_interval_jitter.pack(side="left")
        _try_takefocus(self.entry_interval_jitter, 1)
        self._lbl_interval_jitter_hint = ctk.CTkLabel(
            row_jitter,
            text=self._t("interval_jitter_hint", max=self.MAX_INTERVAL_JITTER_SEC),
            font=self._font_body,
            text_color=self._TEXT_MUTED,
        )
        self._lbl_interval_jitter_hint.pack(side="left", padx=(12, 0))
        self._a11y_label_focus_entry(self._lbl_interval_jitter, self.entry_interval_jitter)

        self._lbl_pixels = ctk.CTkLabel(
            card,
            text=self._t("pixels_label"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
        )
        self._lbl_pixels.grid(row=6, column=0, sticky="w", padx=p, pady=(p, p))
        row3 = ctk.CTkFrame(card, fg_color="transparent")
        row3.grid(row=7, column=0, sticky="ew", padx=p, pady=(0, p))
        self.var_pixels = tk.StringVar(value=str(self.DEFAULT_PIXELS))
        self.entry_pixels = ctk.CTkEntry(
            row3,
            textvariable=self.var_pixels,
            width=120,
            height=40,
            corner_radius=_R,
            font=self._font_body,
            fg_color=self._ENTRY_BG,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            border_width=1,
            border_color=self._ENTRY_BORDER,
        )
        self.entry_pixels.pack(side="left")
        _try_takefocus(self.entry_pixels, 1)
        self._lbl_pixels_hint = ctk.CTkLabel(
            row3,
            text=self._t("pixels_hint", lo=self.MIN_PIXELS, hi=self.MAX_PIXELS),
            font=self._font_body,
            text_color=self._TEXT_MUTED,
        )
        self._lbl_pixels_hint.pack(side="left", padx=(12, 0))
        self._a11y_label_focus_entry(self._lbl_pixels, self.entry_pixels)

        self._lbl_path_speed = ctk.CTkLabel(
            card,
            text=self._t("path_speed_label"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
        )
        self._lbl_path_speed.grid(row=8, column=0, sticky="w", padx=p, pady=(p, p))
        row_path_speed = ctk.CTkFrame(card, fg_color="transparent")
        row_path_speed.grid(row=9, column=0, sticky="ew", padx=p, pady=(0, p))
        self.var_path_speed = tk.StringVar(value=str(int(self.DEFAULT_PATH_SPEED)))
        self.entry_path_speed = ctk.CTkEntry(
            row_path_speed,
            textvariable=self.var_path_speed,
            width=120,
            height=40,
            corner_radius=_R,
            font=self._font_body,
            fg_color=self._ENTRY_BG,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            border_width=1,
            border_color=self._ENTRY_BORDER,
        )
        self.entry_path_speed.pack(side="left")
        _try_takefocus(self.entry_path_speed, 1)
        self._lbl_path_speed_hint = ctk.CTkLabel(
            row_path_speed,
            text=self._t(
                "path_speed_hint",
                lo=self.MIN_PATH_SPEED,
                hi=self.MAX_PATH_SPEED,
            ),
            font=self._font_body,
            text_color=self._TEXT_MUTED,
        )
        self._lbl_path_speed_hint.pack(side="left", padx=(12, 0))
        self._a11y_label_focus_entry(self._lbl_path_speed, self.entry_path_speed)

        self._lbl_motion_pattern = ctk.CTkLabel(
            card,
            text=self._t("motion_pattern_label"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
        )
        self._lbl_motion_pattern.grid(row=10, column=0, sticky="w", padx=p, pady=(p, p))
        row_pattern = ctk.CTkFrame(card, fg_color="transparent")
        row_pattern.grid(row=11, column=0, sticky="ew", padx=p, pady=(0, p))
        self.seg_motion_pattern = ctk.CTkSegmentedButton(
            row_pattern,
            values=[
                self._t("motion_pattern_line"),
                self._t("motion_pattern_circle"),
                self._t("motion_pattern_square"),
            ],
            command=self._on_motion_pattern_seg,
            corner_radius=10,
            font=self._font_body,
            height=36,
            fg_color=self._SURFACE_SUBTLE,
            selected_color=self._ACCENT,
            selected_hover_color=self._ACCENT_HOVER,
            unselected_color=self._BTN_SECONDARY,
            unselected_hover_color=self._BTN_SECONDARY_HOVER,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            text_color_disabled=(self._TEXT_DISABLED, self._TEXT_DISABLED),
        )
        _try_takefocus(self.seg_motion_pattern, 1)
        self.seg_motion_pattern.pack(side="left")
        self._sync_motion_pattern_seg()
        self._a11y_label_focus_entry(self._lbl_motion_pattern, self.seg_motion_pattern)

        schedule_row = ctk.CTkFrame(card, fg_color="transparent")
        schedule_row.grid(row=8, column=0, sticky="ew", padx=p, pady=(p, p))
        schedule_row.grid_columnconfigure(0, weight=1)
        self._lbl_schedule_sw = ctk.CTkLabel(
            schedule_row,
            text=self._t("schedule_window_title"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            anchor="w",
        )
        self._lbl_schedule_sw.grid(row=0, column=0, sticky="w")
        self.var_schedule_window = tk.BooleanVar(value=False)
        self.swt_schedule = ctk.CTkSwitch(
            schedule_row,
            text="",
            variable=self.var_schedule_window,
            width=52,
            switch_width=40,
            switch_height=22,
            fg_color=self._BORDER,
            progress_color=self._ACCENT,
            button_color="#FFFFFF",
            button_hover_color="#F3F4F6",
            font=self._font_body,
        )
        self.swt_schedule.grid(row=0, column=1, sticky="e", padx=(16, 0))
        _try_takefocus(self.swt_schedule, 1)
        self._hint_schedule = ctk.CTkLabel(
            card,
            text=self._t("schedule_window_hint"),
            font=self._font_hint,
            text_color=self._TEXT_MUTED,
            anchor="w",
            justify="left",
            wraplength=520,
        )
        self._hint_schedule.grid(row=9, column=0, sticky="ew", padx=p, pady=(0, 8))

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.grid(row=12, column=0, sticky="w", padx=p, pady=(p, p))

        self.btn_start = self._btn(
            btn_row,
            text=self._t("btn_start"),
            width=120,
            fg_color=self._ACCENT,
            hover_color=self._ACCENT_HOVER,
            text_color=(self._TEXT_ON_ACCENT, self._TEXT_ON_ACCENT),
            font=self._font_body_bold,
            command=self._on_start,
        )
        self.btn_start.pack(side="left", padx=(0, 12))

        self.btn_stop = self._btn(
            btn_row,
            text=self._t("btn_stop"),
            width=120,
            fg_color="transparent",
            hover_color=self._NAV_HOVER,
            text_color=(self._NAV_TEXT, self._NAV_TEXT),
            state="disabled",
            command=self._on_stop,
        )
        self.btn_stop.pack(side="left")

    def _fill_log_panel(self, card: ctk.CTkFrame) -> None:
        p = self._UI_PAD
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)

        self._lbl_log_title = ctk.CTkLabel(
            card,
            text=self._t("log_title"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
        )
        self._lbl_log_title.grid(row=0, column=0, sticky="w", padx=p, pady=(p, p))

        self.log_text = ctk.CTkTextbox(
            card,
            corner_radius=_R,
            font=self._font_mono,
            fg_color=self._ENTRY_BG,
            text_color=(self._TEXT_LOG, self._TEXT_LOG),
            border_width=1,
            border_color=self._ENTRY_BORDER,
        )
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=p, pady=(0, p))
        self.log_text.configure(state="disabled")
        _try_takefocus(self.log_text, 1)

    def _on_segment(self, value: str) -> None:
        self._segment_mode = self._mode_from_segment_value(value)
        self._apply_view()

    def _nav_to_mode(self, mode: Literal["control", "log"]) -> None:
        self._segment_mode = mode
        self.segmented.set(self._segment_text(mode))
        self._apply_view()

    def _apply_view(self) -> None:
        if self._segment_mode == "control":
            self.frame_control.grid(row=0, column=0, sticky="nsew")
            self.frame_log.grid_remove()
        else:
            self.frame_log.grid(row=0, column=0, sticky="nsew")
            self.frame_control.grid_remove()

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
            self.status.set(self._t("status_schedule_wait", cd=countdown_str))
            self._apply_status_chrome("schedule")
        elif self._countdown_phase == "burst":
            self.status.set(self._t("status_motion_burst", cd=countdown_str))
            self._apply_status_chrome("burst")
        else:
            self.status.set(self._t_status_running(countdown_str))
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
        self.root.after(0, lambda m=message: self._log_ui(m))

    def _log_ui(self, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {message}\n"
        self._append_log_line_trim(self.log_text, line)
        self._append_log_line_trim(self.analytics_log, line)

    def _parse_interval(self) -> tuple[float, nudge_logic.IntervalUnit] | None:
        raw = self.var_minutes.get()
        u = self._interval_unit
        if u == "min":
            m = nudge_logic.parse_minutes_string(raw, min_minutes=self.MIN_MINUTES)
            if m is None:
                return None
            return (m, "min")
        s = nudge_logic.parse_seconds_string(raw, min_seconds=nudge_logic.MIN_SECONDS)
        if s is None:
            return None
        return (s, "sec")

    def _parse_interval_jitter(self) -> float | None:
        return nudge_logic.parse_interval_jitter_seconds_string(
            self.var_interval_jitter.get(),
            max_jitter=float(self.MAX_INTERVAL_JITTER_SEC),
        )

    def _parse_pixels(self) -> int | None:
        return nudge_logic.parse_pixels_string(
            self.var_pixels.get(), min_px=self.MIN_PIXELS, max_px=self.MAX_PIXELS
        )

    def _parse_path_speed(self) -> int | None:
        return nudge_logic.parse_path_speed_string(
            self.var_path_speed.get(),
            min_sp=self.MIN_PATH_SPEED,
            max_sp=self.MAX_PATH_SPEED,
        )

    def _nudge_tick(
        self,
        pixels: int,
        pattern: MotionPattern,
        path_speed: int,
        *,
        log_success: bool = True,
    ) -> None:
        try:
            jiggle_mouse(pixels, pattern, path_speed=path_speed)
            if not log_success:
                return
            analytics_store.record_nudge(pattern)
            if pixels > 0:
                self._log(self._t("log_nudge"))
            else:
                self._log(self._t("log_nudge_zero"))
        except OSError as e:
            self._log(self._t("log_nudge_fail", err=e))

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
            if schedule_window.is_within_work_window(now):
                if waited:
                    self.root.after(0, lambda: self._log(self._t("log_schedule_resumed")))
                return not self._stop.is_set()
            waited = True
            resume_at = schedule_window.next_window_start(now)
            self.root.after(0, lambda ra=resume_at: self._ui_schedule_wait_begin(ra))
            end_mono = time.monotonic() + max(0.0, (resume_at - now).total_seconds())
            while time.monotonic() < end_mono and not self._stop.is_set():
                left = end_mono - time.monotonic()
                if left <= 0:
                    break
                step = min(30.0, left)
                if self._stop.wait(timeout=step):
                    return False
                if not self._run_schedule_window:
                    self.root.after(0, self._ui_exit_schedule_wait)
                    return not self._stop.is_set()
            if self._stop.is_set():
                return False
        return False

    def _on_start(self) -> None:
        parsed = self._parse_interval()
        if parsed is None:
            if self._interval_unit == "min":
                err_body = self._t("err_minutes", min=self.MIN_MINUTES)
            else:
                err_body = self._t("err_seconds", min=nudge_logic.MIN_SECONDS)
            messagebox.showerror(
                self._t("err_title"),
                err_body,
                parent=self.root,
            )
            self._log(self._t("log_start_fail_interval"))
            return
        ival, iu = parsed
        jitter_sec = self._parse_interval_jitter()
        if jitter_sec is None:
            messagebox.showerror(
                self._t("err_title"),
                self._t("err_jitter", max=self.MAX_INTERVAL_JITTER_SEC),
                parent=self.root,
            )
            self._log(self._t("log_start_fail_jitter"))
            return
        pixels = self._parse_pixels()
        if pixels is None:
            messagebox.showerror(
                self._t("err_title"),
                self._t("err_pixels", lo=self.MIN_PIXELS, hi=self.MAX_PIXELS),
                parent=self.root,
            )
            self._log(self._t("log_start_fail_pixels"))
            return
        path_speed = self._parse_path_speed()
        if path_speed is None:
            messagebox.showerror(
                self._t("err_title"),
                self._t("err_path_speed", lo=self.MIN_PATH_SPEED, hi=self.MAX_PATH_SPEED),
                parent=self.root,
            )
            self._log(self._t("log_start_fail_path_speed"))
            return
        if self._worker is not None and self._worker.is_alive():
            return

        self._stop.clear()
        self._run_schedule_window = bool(self.var_schedule_window.get())
        interval_sec = ival * 60.0 if iu == "min" else ival
        self._running_interval_value = ival
        self._running_interval_unit = iu
        self._current_interval_sec = interval_sec
        self._next_jiggle_monotonic = time.monotonic() + interval_sec
        run_pattern: MotionPattern = self._motion_pattern

        self._worker = threading.Thread(
            target=self._run_loop,
            args=(interval_sec, jitter_sec, pixels, path_speed, run_pattern),
            daemon=True,
        )
        self._worker.start()

        self._analytics_runtime_anchor = time.monotonic()
        self._schedule_next_runtime_flush()

        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.entry_minutes.configure(state="disabled")
        self.entry_pixels.configure(state="disabled")
        self.entry_path_speed.configure(state="disabled")
        self.entry_interval_jitter.configure(state="disabled")
        self._set_interval_preset_widgets_state("disabled")
        try:
            self.seg_interval_unit.configure(state="disabled")
        except (tk.TclError, AttributeError):
            pass
        try:
            self.seg_motion_pattern.configure(state="disabled")
        except (tk.TclError, AttributeError):
            pass
        try:
            self.swt_schedule.configure(state="disabled")
        except (tk.TclError, AttributeError):
            pass
        self.status.set(self._t_status_running("—"))
        self._apply_status_chrome("interval")
        self._schedule_countdown_tick()
        pat = self._pattern_log_label()
        if iu == "min":
            if jitter_sec > 0.0:
                self._log(
                    self._t(
                        "log_started_min_jitter",
                        v=ival,
                        sec=interval_sec,
                        j=jitter_sec,
                        pat=pat,
                        px=pixels,
                        ps=path_speed,
                    )
                )
            else:
                self._log(
                    self._t(
                        "log_started_min",
                        v=ival,
                        sec=interval_sec,
                        pat=pat,
                        px=pixels,
                        ps=path_speed,
                    )
                )
        elif jitter_sec > 0.0:
            self._log(
                self._t(
                    "log_started_sec_jitter",
                    v=ival,
                    j=jitter_sec,
                    pat=pat,
                    px=pixels,
                    ps=path_speed,
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
                )
            )
        if self._run_schedule_window:
            self._log(self._t("log_start_schedule"))

    def _on_stop(self) -> None:
        self._flush_runtime_segment()
        self._cancel_analytics_runtime_flush()
        self._stop.set()
        self._cancel_countdown_tick()
        self._current_interval_sec = 0.0
        self._countdown_phase = "interval"
        self._schedule_resume_at = None
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.entry_minutes.configure(state="normal")
        self.entry_pixels.configure(state="normal")
        self.entry_path_speed.configure(state="normal")
        self.entry_interval_jitter.configure(state="normal")
        self._set_interval_preset_widgets_state("normal")
        try:
            self.seg_interval_unit.configure(state="normal")
        except (tk.TclError, AttributeError):
            pass
        try:
            self.seg_motion_pattern.configure(state="normal")
        except (tk.TclError, AttributeError):
            pass
        try:
            self.swt_schedule.configure(state="normal")
        except (tk.TclError, AttributeError):
            pass
        self.status.set(self._t("status_stopped"))
        self._apply_status_chrome("stopped")
        self._log(self._t("log_stopped"))

    def _run_loop(
        self,
        interval_sec: float,
        jitter_sec: float,
        pixels: int,
        path_speed: int,
        pattern: MotionPattern,
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
            self._nudge_tick(pixels, pattern, path_speed, log_success=True)
            last_nudge_monotonic = now
            active_interval = nudge_logic.next_wait_seconds(interval_sec, jitter_sec)

    def _start_tray(self) -> None:
        self._tray.start(
            tooltip=self._t("window_title"),
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

        self._cancel_analytics_runtime_flush()
        self._flush_runtime_segment()

        self._stop.set()
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
