"""CustomTkinter UI and scheduling for the mouse nudge app."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
import time
import webbrowser
import tkinter as tk
from datetime import date, datetime, time as dtime
from importlib.metadata import PackageNotFoundError, version as pkg_version
from importlib.resources import files
from pathlib import Path
from tkinter import messagebox
from typing import Any, Literal

import customtkinter as ctk

from . import (
    analytics_charts,
    analytics_store,
    local_config,
    nudge_logic,
    schedule_window,
    updater,
)
from .app_icon import load_app_icon_rgba
from .cursor_nudge import ActivityStyle, MotionPattern
from .strings import Lang, STRINGS
from .tray import HAS_TRAY, TrayController
from .win32_mouse import get_seconds_since_last_user_input, jiggle_mouse, jiggle_natural

# Primary UI font (Inter). If missing, Tk picks a substitute.
_FONT_INTER = "Inter"
_LOG = logging.getLogger(__name__)

# Pro dark / light: unified corner radius; padding in class (see _UI_PAD).
_R = 12
_R_BTN = _R  # primary / secondary button radius (used by _btn)

UiTheme = Literal["dark", "light"]
_UI_PALETTES: dict[UiTheme, dict[str, str]] = {
    "dark": {
        "MAIN_BG": "#1E1E2E",
        "SIDEBAR_BG": "#181825",
        "CARD_BG": "#24273A",
        "CARD_BORDER": "#313244",
        "ENTRY_BG": "#24273A",
        "ENTRY_BORDER": "#313244",
        "ACCENT": "#89B4FA",
        "ACCENT_HOVER": "#74C7EC",
        "TEXT_ON_ACCENT": "#F5F7FF",
        "SURFACE_SUBTLE": "#24273A",
        "SURFACE_SUBTLE_HOVER": "#313244",
        "BORDER": "#313244",
        "TEXT_TITLE": "#CDD6F4",
        "TEXT_BODY": "#CDD6F4",
        "TEXT_MUTED": "#A6ADC8",
        "TEXT_DISABLED": "#6C7086",
        "TEXT_LOG": "#CDD6F4",
        "NAV_TEXT": "#A6ADC8",
        "NAV_HOVER": "#313244",
        "NAV_SELECTED": "#B4BEFE",
        "NAV_ON_SELECTED": "#1E1E2E",
        "BTN_SECONDARY": "#24273A",
        "BTN_SECONDARY_HOVER": "#313244",
        "STATUS_STRIP_BG_STOP": "#24273A",
        "STATUS_STRIP_BORDER_STOP": "#313244",
        "STATUS_LED_STOP": "#6C7086",
        "STATUS_STRIP_BG_RUN": "#1F2B24",
        "STATUS_STRIP_BORDER_RUN": "#A6E3A1",
        "STATUS_LED_RUN": "#A6E3A1",
        "STATUS_TEXT_RUN": "#A6E3A1",
        "STATUS_STRIP_BG_BURST": "#2E2A1F",
        "STATUS_STRIP_BORDER_BURST": "#F9E2AF",
        "STATUS_LED_BURST": "#F9E2AF",
        "STATUS_TEXT_BURST": "#F9E2AF",
        "STATUS_STRIP_BG_SCHEDULE": "#1D2930",
        "STATUS_STRIP_BORDER_SCHEDULE": "#89DCEB",
        "STATUS_LED_SCHEDULE": "#89DCEB",
        "STATUS_TEXT_SCHEDULE": "#89DCEB",
    },
    "light": {
        "MAIN_BG": "#F7F9FC",
        "SIDEBAR_BG": "#FFFFFF",
        "CARD_BG": "#FFFFFF",
        "CARD_BORDER": "#D8E0EA",
        "ENTRY_BG": "#FFFFFF",
        "ENTRY_BORDER": "#C7D2DF",
        "ACCENT": "#5C7FA8",
        "ACCENT_HOVER": "#4F7095",
        "TEXT_ON_ACCENT": "#FFFFFF",
        "SURFACE_SUBTLE": "#F0F4F8",
        "SURFACE_SUBTLE_HOVER": "#E5EBF2",
        "BORDER": "#D2DBE6",
        "TEXT_TITLE": "#0F172A",
        "TEXT_BODY": "#243244",
        "TEXT_MUTED": "#6A7A8D",
        "TEXT_DISABLED": "#96A4B5",
        "TEXT_LOG": "#243244",
        "NAV_TEXT": "#5A6B80",
        "NAV_HOVER": "#E7EDF4",
        "NAV_SELECTED": "#4F7095",
        "NAV_ON_SELECTED": "#FFFFFF",
        "BTN_SECONDARY": "#ECF2F8",
        "BTN_SECONDARY_HOVER": "#DFE8F2",
        "STATUS_STRIP_BG_STOP": "#FFFFFF",
        "STATUS_STRIP_BORDER_STOP": "#D2DBE6",
        "STATUS_LED_STOP": "#96A4B5",
        "STATUS_STRIP_BG_RUN": "#F1F7F3",
        "STATUS_STRIP_BORDER_RUN": "#5C9B79",
        "STATUS_LED_RUN": "#5C9B79",
        "STATUS_TEXT_RUN": "#4D8266",
        "STATUS_STRIP_BG_BURST": "#FCF8F1",
        "STATUS_STRIP_BORDER_BURST": "#B7925D",
        "STATUS_LED_BURST": "#B7925D",
        "STATUS_TEXT_BURST": "#96774A",
        "STATUS_STRIP_BG_SCHEDULE": "#EEF3F8",
        "STATUS_STRIP_BORDER_SCHEDULE": "#6A89A8",
        "STATUS_LED_SCHEDULE": "#6A89A8",
        "STATUS_TEXT_SCHEDULE": "#5D7996",
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
    _AUTO_UPDATE_STARTUP_DELAY_MS = 1500
    _AUTO_UPDATE_INTERVAL_MS = 1 * 60 * 60 * 1000
    _AUTO_UPDATE_RETRY_MS = 15 * 60 * 1000

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
        if hasattr(self, "page_analytics"):
            self.page_analytics.configure(
                fg_color="transparent",
            )
        if hasattr(self, "page_settings"):
            self.page_settings.configure(
                fg_color="transparent",
            )
        if hasattr(self, "_settings_scroll"):
            self._settings_scroll.configure(
                fg_color=self._CARD_BG,
                border_color=self._CARD_BORDER,
                scrollbar_button_color=self._BTN_SECONDARY,
                scrollbar_button_hover_color=self._BTN_SECONDARY_HOVER,
            )
        if hasattr(self, "analytics_scroll"):
            self.analytics_scroll.configure(
                fg_color=self._CARD_BG,
                border_color=self._CARD_BORDER,
                scrollbar_button_color=self._BTN_SECONDARY,
                scrollbar_button_hover_color=self._BTN_SECONDARY_HOVER,
            )

        for w in (
            "entry_minutes",
            "entry_pixels",
            "entry_path_speed",
            "entry_interval_jitter",
            "entry_schedule_start",
            "entry_schedule_end",
        ):
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
        if hasattr(self, "seg_activity_style"):
            self.seg_activity_style.configure(
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
                border_width=2,
                border_color=self._ACCENT_HOVER,
            )
        if hasattr(self, "btn_stop"):
            self.btn_stop.configure(
                fg_color=self._BTN_SECONDARY,
                hover_color=self._BTN_SECONDARY_HOVER,
                text_color=(self._TEXT_BODY, self._TEXT_BODY),
                border_width=2,
                border_color=self._BORDER,
            )
        if hasattr(self, "btn_open_config"):
            self.btn_open_config.configure(
                fg_color="transparent",
                hover_color=self._NAV_HOVER,
                text_color=(self._NAV_TEXT, self._NAV_TEXT),
            )
        if hasattr(self, "btn_contact_us"):
            self.btn_contact_us.configure(
                fg_color="transparent",
                hover_color=self._NAV_HOVER,
                text_color=(self._NAV_TEXT, self._NAV_TEXT),
            )
        if hasattr(self, "btn_check_updates"):
            self.btn_check_updates.configure(
                fg_color=self._ACCENT,
                hover_color=self._ACCENT_HOVER,
                text_color=(self._TEXT_ON_ACCENT, self._TEXT_ON_ACCENT),
                border_width=2,
                border_color=self._ACCENT_HOVER,
            )
        if hasattr(self, "btn_update_notice_open"):
            self.btn_update_notice_open.configure(
                fg_color=self._ACCENT,
                hover_color=self._ACCENT_HOVER,
                text_color=(self._TEXT_ON_ACCENT, self._TEXT_ON_ACCENT),
                border_width=2,
                border_color=self._ACCENT_HOVER,
            )
        if hasattr(self, "btn_update_notice_close"):
            self.btn_update_notice_close.configure(
                fg_color=self._BTN_SECONDARY,
                hover_color=self._BTN_SECONDARY_HOVER,
                text_color=(self._TEXT_BODY, self._TEXT_BODY),
                border_width=2,
                border_color=self._BORDER,
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
                    button_hover_color="#E2E8F0",
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
                    button_hover_color="#E2E8F0",
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
                    button_hover_color="#E2E8F0",
                )
        if hasattr(self, "swt_auto_updates"):
            if self._ui_theme == "dark":
                self.swt_auto_updates.configure(
                    fg_color=self._BORDER,
                    progress_color=self._ACCENT,
                    button_color="#C9D1D9",
                    button_hover_color="#8B949E",
                )
            else:
                self.swt_auto_updates.configure(
                    fg_color=self._BORDER,
                    progress_color=self._ACCENT,
                    button_color="#FFFFFF",
                    button_hover_color="#E2E8F0",
                )
        for _swt_name in ("swt_natural_click", "swt_natural_scroll"):
            if hasattr(self, _swt_name):
                _swt = getattr(self, _swt_name)
                if self._ui_theme == "dark":
                    _swt.configure(
                        fg_color=self._BORDER,
                        progress_color=self._ACCENT,
                        button_color="#C9D1D9",
                        button_hover_color="#8B949E",
                    )
                else:
                    _swt.configure(
                        fg_color=self._BORDER,
                        progress_color=self._ACCENT,
                        button_color="#FFFFFF",
                        button_hover_color="#E2E8F0",
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
            "_lbl_activity_style",
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
            "_lbl_schedule_time_start",
            "_lbl_schedule_time_end",
            "_lbl_about_updates",
            "_lbl_auto_updates_sw",
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
            "_hint_auto_updates",
            "_lbl_natural_opts_hint",
        ):
            if hasattr(self, name):
                getattr(self, name).configure(text_color=self._TEXT_MUTED)
        if hasattr(self, "_lbl_schedule_banner"):
            self._lbl_schedule_banner.configure(
                text_color=self._TEXT_MUTED,
                fg_color=self._SURFACE_SUBTLE,
            )
        if hasattr(self, "_update_notice"):
            self._update_notice.configure(
                fg_color=self._STATUS_STRIP_BG_SCHEDULE,
                border_color=self._STATUS_STRIP_BORDER_SCHEDULE,
            )
        if hasattr(self, "_lbl_update_notice"):
            self._lbl_update_notice.configure(
                text_color=(self._STATUS_TEXT_SCHEDULE, self._STATUS_TEXT_SCHEDULE)
            )
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
        self._interval_unit: nudge_logic.IntervalUnit = "min"
        self._running_interval_value = 0.0
        self._running_interval_unit: nudge_logic.IntervalUnit = "min"
        self._current_interval_sec = 0.0
        self._countdown_after_id: str | None = None
        self._countdown_phase: Literal["interval", "burst", "schedule"] = "interval"
        self.status = tk.StringVar(value=self._t("status_stopped"))
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
        self._update_notice_after_id: str | None = None
        self._update_notice_anim_after_id: str | None = None
        self._update_notice_target_h = 72
        self._activity_style: ActivityStyle = "pattern"

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
            return pkg_version("try-working-hard")
        except PackageNotFoundError:
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
            if hasattr(self, "seg_motion_pattern"):
                self.seg_motion_pattern.configure(state="disabled" if natural else "normal")
            if hasattr(self, "row_natural_opts"):
                if natural:
                    self.row_natural_opts.grid()
                else:
                    self.row_natural_opts.grid_remove()
        except (tk.TclError, AttributeError):
            pass
        self._sync_path_speed_labels_for_mode()
        self._sync_motion_pattern_label_for_mode()

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

    def _on_natural_pref_changed(self) -> None:
        if self._shutting_down or self._config_loading:
            return
        self._schedule_save_config()

    def _pattern_log_label(self) -> str:
        if self._activity_style == "natural":
            return self._t("motion_pattern_log_natural")
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
        ast = cfg.get("activity_style", "pattern")
        self._activity_style = ast if ast in ("pattern", "natural") else "pattern"
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
            "interval_unit": self._interval_unit,
            "interval_jitter_text": self.var_interval_jitter.get(),
            "pixels_text": self.var_pixels.get(),
            "path_speed_text": self.var_path_speed.get(),
            "motion_pattern": self._motion_pattern,
            "activity_style": self._activity_style,
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
        choice = self._show_startup_choice_dialog()
        if choice == "skip_forever":
            self._intro_acknowledged = True
            self._save_config_now()
            return
        if choice != "guide":
            return
        self._show_operation_flow_guide()
        self._reapply_start_maximized()
        self._intro_acknowledged = True
        self._save_config_now()

    def _show_startup_choice_dialog(self) -> Literal["guide", "skip_forever", "dismiss"]:
        result: Literal["guide", "skip_forever", "dismiss"] = "dismiss"
        try:
            dialog = ctk.CTkToplevel(self.root)
        except tk.TclError:
            return result

        dialog.title(self._t("startup_choice_title"))
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.configure(fg_color=self._MAIN_BG)
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(0, weight=1)
        self._center_dialog(dialog, 620, 420)

        container = ctk.CTkFrame(
            dialog,
            fg_color=self._CARD_BG,
            border_width=1,
            border_color=self._CARD_BORDER,
            corner_radius=_R,
        )
        container.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        container.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(
            container,
            text=self._t("startup_choice_title"),
            font=self._font_title,
            text_color=(self._TEXT_TITLE, self._TEXT_TITLE),
            anchor="w",
        )
        title_label.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 8))

        lang_card = ctk.CTkFrame(
            container,
            fg_color=self._SURFACE_SUBTLE,
            border_width=1,
            border_color=self._BORDER,
            corner_radius=_R,
        )
        lang_card.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))
        lang_card.grid_columnconfigure(1, weight=1)
        lang_label = ctk.CTkLabel(
            lang_card,
            text=self._t("startup_lang_label"),
            font=self._font_hint,
            text_color=(self._TEXT_TITLE, self._TEXT_TITLE),
            anchor="w",
        )
        lang_label.grid(row=0, column=0, sticky="w", padx=(12, 10), pady=(10, 2))
        lang_hint = ctk.CTkLabel(
            lang_card,
            text=self._t("startup_lang_hint"),
            font=self._font_hint,
            text_color=(self._TEXT_MUTED, self._TEXT_MUTED),
            anchor="w",
            justify="left",
        )
        lang_hint.grid(row=1, column=0, columnspan=2, sticky="w", padx=12, pady=(0, 10))
        syncing_lang_choice = False

        body_label = ctk.CTkLabel(
            container,
            text=self._t("startup_choice_body", version=self._pkg_version()),
            font=self._font_body,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            anchor="w",
            justify="left",
            wraplength=560,
        )
        body_label.grid(row=2, column=0, sticky="ew", padx=20)

        note_label = ctk.CTkLabel(
            container,
            text=self._t("startup_choice_note"),
            font=self._font_hint,
            text_color=(self._TEXT_MUTED, self._TEXT_MUTED),
            anchor="w",
            justify="left",
            wraplength=560,
        )
        note_label.grid(row=3, column=0, sticky="ew", padx=20, pady=(8, 12))

        actions = ctk.CTkFrame(container, fg_color="transparent")
        actions.grid(row=4, column=0, sticky="ew", padx=20, pady=(0, 20))
        actions.grid_columnconfigure((0, 1), weight=1)

        def _close_with(value: Literal["guide", "skip_forever", "dismiss"]) -> None:
            nonlocal result
            result = value
            try:
                dialog.grab_release()
            except tk.TclError:
                pass
            dialog.destroy()

        def _refresh_startup_copy() -> None:
            title_label.configure(text=self._t("startup_choice_title"))
            lang_label.configure(text=self._t("startup_lang_label"))
            lang_hint.configure(text=self._t("startup_lang_hint"))
            body_label.configure(text=self._t("startup_choice_body", version=self._pkg_version()))
            note_label.configure(text=self._t("startup_choice_note"))
            btn_guide.configure(text=self._t("startup_choice_cta_guide"))
            btn_skip.configure(text=self._t("startup_choice_cta_skip_forever"))

        def _on_startup_lang_switch(label: str) -> None:
            nonlocal syncing_lang_choice
            if syncing_lang_choice:
                return
            self._on_lang_switch(label)
            self._schedule_save_config()
            _refresh_startup_copy()

        lang_seg = ctk.CTkSegmentedButton(
            lang_card,
            values=["繁中", "English"],
            selected_color=self._ACCENT,
            selected_hover_color=self._ACCENT_HOVER,
            unselected_color=self._SURFACE_SUBTLE,
            unselected_hover_color=self._SURFACE_SUBTLE_HOVER,
            text_color=(self._TEXT_BODY, self._TEXT_ON_ACCENT),
            command=lambda label: _on_startup_lang_switch(str(label)),
        )
        lang_seg.grid(row=0, column=1, sticky="e", padx=(0, 12), pady=(8, 0))
        syncing_lang_choice = True
        try:
            lang_seg.set("繁中" if self._lang == "zh" else "English")
        finally:
            syncing_lang_choice = False

        btn_guide = self._btn(
            actions,
            text=self._t("startup_choice_cta_guide"),
            command=lambda: _close_with("guide"),
            fg_color=self._ACCENT,
            hover_color=self._ACCENT_HOVER,
            text_color=(self._TEXT_ON_ACCENT, self._TEXT_ON_ACCENT),
        )
        btn_guide.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        btn_skip = self._btn(
            actions,
            text=self._t("startup_choice_cta_skip_forever"),
            command=lambda: _close_with("skip_forever"),
            fg_color=self._BTN_SECONDARY,
            hover_color=self._BTN_SECONDARY_HOVER,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
        )
        btn_skip.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        dialog.protocol("WM_DELETE_WINDOW", lambda: _close_with("dismiss"))
        dialog.after(0, dialog.lift)
        dialog.after(0, dialog.focus_force)
        try:
            dialog.grab_set()
            self.root.wait_window(dialog)
        except tk.TclError:
            return "dismiss"
        return result

    def _show_operation_flow_guide(self) -> None:
        def _steps_for_current_lang() -> list[tuple[str, str]]:
            return [
                (
                    self._t("guide_step_1_title"),
                    self._t("guide_step_1_body"),
                ),
                (
                    self._t("guide_step_2_title"),
                    self._t("guide_step_2_body"),
                ),
                (
                    self._t("guide_step_3_title"),
                    self._t("guide_step_3_body"),
                ),
            ]
        try:
            dialog = ctk.CTkToplevel(self.root)
        except tk.TclError:
            return
        dialog.title(self._t("guide_window_title"))
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.configure(fg_color=self._MAIN_BG)
        self._center_dialog(dialog, 760, 560)
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(0, weight=1)

        shell = ctk.CTkFrame(
            dialog,
            fg_color=self._CARD_BG,
            border_width=1,
            border_color=self._CARD_BORDER,
            corner_radius=_R,
        )
        shell.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        shell.grid_columnconfigure(0, weight=1)
        shell.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            shell,
            text=self._t("guide_window_title"),
            font=self._font_title,
            text_color=(self._TEXT_TITLE, self._TEXT_TITLE),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 12))

        feature_box = ctk.CTkFrame(
            shell,
            fg_color=self._SURFACE_SUBTLE,
            border_width=1,
            border_color=self._BORDER,
            corner_radius=_R,
        )
        feature_box.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))
        feature_box.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            feature_box,
            text=self._t("guide_features_title"),
            font=self._font_body_bold,
            text_color=(self._TEXT_TITLE, self._TEXT_TITLE),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 4))
        ctk.CTkLabel(
            feature_box,
            text=self._t("guide_features_body"),
            font=self._font_hint,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            anchor="w",
            justify="left",
            wraplength=680,
        ).grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 12))

        content = ctk.CTkFrame(shell, fg_color="transparent")
        content.grid(row=2, column=0, sticky="nsew", padx=20)
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(2, weight=1)

        progress_row = ctk.CTkFrame(content, fg_color="transparent")
        progress_row.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        progress_row.grid_columnconfigure(0, weight=1)
        progress_bar = ctk.CTkProgressBar(
            progress_row,
            progress_color=self._ACCENT,
            fg_color=self._BORDER,
            corner_radius=6,
            height=10,
        )
        progress_bar.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        progress_bar.set(0)
        progress_text = ctk.CTkLabel(
            progress_row,
            text="",
            font=self._font_hint,
            text_color=(self._TEXT_MUTED, self._TEXT_MUTED),
            anchor="e",
            width=76,
        )
        progress_text.grid(row=0, column=1, sticky="e")

        step_meta = ctk.CTkLabel(
            content,
            text="",
            font=self._font_hint,
            text_color=(self._TEXT_MUTED, self._TEXT_MUTED),
            anchor="w",
        )
        step_meta.grid(row=1, column=0, sticky="ew", pady=(0, 8))

        card = ctk.CTkFrame(
            content,
            fg_color=self._SURFACE_SUBTLE,
            border_width=1,
            border_color=self._BORDER,
            corner_radius=_R,
        )
        card.grid(row=2, column=0, sticky="nsew")
        card.grid_columnconfigure(1, weight=1)
        card.grid_rowconfigure(1, weight=1)

        step_badge = ctk.CTkLabel(
            card,
            text="1",
            width=34,
            height=34,
            font=self._font_body_bold,
            text_color=(self._TEXT_ON_ACCENT, self._TEXT_ON_ACCENT),
            fg_color=self._ACCENT,
            corner_radius=17,
        )
        step_badge.grid(row=0, column=0, rowspan=2, padx=(14, 12), pady=14, sticky="n")

        step_title = ctk.CTkLabel(
            card,
            text="",
            font=self._font_body_bold,
            text_color=(self._TEXT_TITLE, self._TEXT_TITLE),
            anchor="w",
        )
        step_title.grid(row=0, column=1, sticky="ew", padx=(0, 14), pady=(14, 6))

        step_body = ctk.CTkLabel(
            card,
            text="",
            font=self._font_body,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            anchor="nw",
            justify="left",
            wraplength=620,
        )
        step_body.grid(row=1, column=1, sticky="nsew", padx=(0, 14), pady=(0, 14))

        footer = ctk.CTkFrame(shell, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew", padx=20, pady=(10, 20))
        footer.grid_columnconfigure(1, weight=1)

        current_idx = 0

        btn_prev = self._btn(
            footer,
            text=self._t("guide_cta_prev"),
            command=lambda: _set_step(current_idx - 1),
            fg_color=self._BTN_SECONDARY,
            hover_color=self._BTN_SECONDARY_HOVER,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            width=120,
        )
        btn_prev.grid(row=0, column=0, sticky="w")

        btn_next = self._btn(
            footer,
            text=self._t("guide_cta_next"),
            command=lambda: _set_step(current_idx + 1),
            fg_color=self._ACCENT,
            hover_color=self._ACCENT_HOVER,
            text_color=(self._TEXT_ON_ACCENT, self._TEXT_ON_ACCENT),
            width=140,
        )
        btn_next.grid(row=0, column=2, sticky="e")

        def _set_step(idx: int) -> None:
            nonlocal current_idx
            steps = _steps_for_current_lang()
            max_idx = len(steps) - 1
            idx = max(0, min(idx, max_idx))
            current_idx = idx
            title, body = steps[idx]
            step_badge.configure(text=str(idx + 1))
            step_title.configure(text=title)
            step_body.configure(text=body)
            step_meta.configure(
                text=self._t("guide_step_counter", current=idx + 1, total=len(steps))
            )
            progress = float(idx + 1) / float(len(steps))
            progress_bar.set(progress)
            progress_text.configure(
                text=self._t("guide_progress_percent", percent=int(round(progress * 100)))
            )
            btn_prev.configure(state="disabled" if idx == 0 else "normal")
            if idx == max_idx:
                btn_next.configure(
                    text=self._t("guide_cta_done"),
                    command=dialog.destroy,
                )
            else:
                btn_next.configure(
                    text=self._t("guide_cta_next"),
                    command=lambda: _set_step(current_idx + 1),
                )
            btn_next.configure(state="normal")

        _set_step(0)

        dialog.after(0, dialog.lift)
        dialog.after(0, dialog.focus_force)
        try:
            dialog.grab_set()
            self.root.wait_window(dialog)
        except tk.TclError:
            return

    def _center_dialog(self, dialog: ctk.CTkToplevel, width: int, height: int) -> None:
        try:
            dialog.update_idletasks()
            parent = self.root
            parent.update_idletasks()
            parent_w = max(1, int(parent.winfo_width()))
            parent_h = max(1, int(parent.winfo_height()))
            parent_x = int(parent.winfo_rootx())
            parent_y = int(parent.winfo_rooty())
            x = parent_x + max(0, (parent_w - width) // 2) - max(20, parent_w // 20)
            y = parent_y + max(0, (parent_h - height) // 2) - max(24, parent_h // 10)
            screen_w = int(dialog.winfo_screenwidth())
            screen_h = int(dialog.winfo_screenheight())
            x = min(max(0, x), max(0, screen_w - width))
            y = min(max(0, y), max(0, screen_h - height))
            dialog.geometry(f"{width}x{height}+{x}+{y}")
        except tk.TclError:
            dialog.geometry(f"{width}x{height}")

    def _register_config_persistence(self) -> None:
        def _on_write(*_a: object) -> None:
            self._schedule_save_config()

        def _on_schedule_flag(*_a: object) -> None:
            self._run_schedule_window = bool(self.var_schedule_window.get())
            self._sync_schedule_times_from_vars()
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

    def _on_contact_us(self) -> None:
        url = "https://github.com/MomentaryChen/try-working-hard/issues/new/choose"
        messagebox.showinfo(
            self._t("btn_contact_us"),
            self._t("contact_us_body", url=url),
            parent=self.root,
        )
        webbrowser.open(url, new=2)

    def _maybe_auto_check_updates(self) -> None:
        if self._shutting_down:
            return
        if not bool(self.var_auto_check_updates.get()):
            return
        self._check_updates(manual=False)

    def _cancel_auto_update_check(self) -> None:
        if self._update_check_after_id is None:
            return
        try:
            self.root.after_cancel(self._update_check_after_id)
        except tk.TclError:
            pass
        self._update_check_after_id = None

    def _schedule_auto_update_check(self, delay_ms: int | None = None) -> None:
        if self._shutting_down:
            return
        if not hasattr(self, "var_auto_check_updates"):
            return
        if not bool(self.var_auto_check_updates.get()):
            self._cancel_auto_update_check()
            return
        self._cancel_auto_update_check()
        next_delay = delay_ms if delay_ms is not None else self._AUTO_UPDATE_INTERVAL_MS
        self._update_check_after_id = self.root.after(next_delay, self._run_auto_update_check)

    def _run_auto_update_check(self) -> None:
        self._update_check_after_id = None
        if self._shutting_down:
            return
        if self._update_check_in_progress:
            self._schedule_auto_update_check(self._AUTO_UPDATE_RETRY_MS)
            return
        self._maybe_auto_check_updates()

    def _on_check_updates(self) -> None:
        self._check_updates(manual=True)

    def _show_update_banner(
        self,
        *,
        latest_tag: str,
        current: str,
        latest_url: str,
        summary: str,
        installer_url: str,
        installer_name: str,
        checksum_url: str,
        checksum_name: str,
    ) -> None:
        if self._shutting_down:
            return
        self._update_notice_url = latest_url
        self._update_notice_latest_tag = latest_tag
        self._update_notice_installer_url = installer_url
        self._update_notice_installer_name = installer_name
        self._update_notice_checksum_url = checksum_url
        self._update_notice_checksum_name = checksum_name
        self.btn_update_notice_open.configure(state="normal")
        msg = [self._t("update_banner_new_version", latest=latest_tag, current=current)]
        if summary:
            msg.append(self._t("update_banner_summary", summary=summary))
        msg.append(self._t("update_banner_rollback_hint"))
        self._lbl_update_notice.configure(text="\n".join(msg))
        self._animate_update_banner(show=True)
        if self._update_notice_after_id is not None:
            try:
                self.root.after_cancel(self._update_notice_after_id)
            except tk.TclError:
                pass
            self._update_notice_after_id = None
        self._update_notice_after_id = self.root.after(12000, self._hide_update_banner)

    def _show_info_banner(self, text: str) -> None:
        if self._shutting_down:
            return
        self._update_notice_url = ""
        self._update_notice_latest_tag = ""
        self._update_notice_installer_url = ""
        self._update_notice_installer_name = ""
        self._update_notice_checksum_url = ""
        self._update_notice_checksum_name = ""
        self.btn_update_notice_open.configure(state="disabled")
        self._lbl_update_notice.configure(text=text)
        self._animate_update_banner(show=True)
        if self._update_notice_after_id is not None:
            try:
                self.root.after_cancel(self._update_notice_after_id)
            except tk.TclError:
                pass
            self._update_notice_after_id = None
        self._update_notice_after_id = self.root.after(7000, self._hide_update_banner)

    def _hide_update_banner(self) -> None:
        self._update_notice_after_id = None
        if self._shutting_down:
            return
        self._animate_update_banner(show=False)

    def _animate_update_banner(self, *, show: bool) -> None:
        if self._update_notice_anim_after_id is not None:
            try:
                self.root.after_cancel(self._update_notice_anim_after_id)
            except tk.TclError:
                pass
            self._update_notice_anim_after_id = None

        if show:
            self._update_notice_shell.grid()
            return

        def _tick_hide() -> None:
            self._update_notice_shell.grid_remove()
            self._update_notice_anim_after_id = None

        _tick_hide()

    def _open_update_from_banner(self) -> None:
        if self._update_download_in_progress:
            self._show_info_banner(self._t("update_download_in_progress"))
            return
        if self._update_notice_installer_url and self._update_notice_installer_name:
            self._prompt_download_latest_installer(
                latest_tag=self._update_notice_latest_tag,
                installer_name=self._update_notice_installer_name,
                installer_url=self._update_notice_installer_url,
                checksum_url=self._update_notice_checksum_url,
            )
            return
        if self._update_notice_url:
            webbrowser.open(self._update_notice_url, new=2)
        self._hide_update_banner()

    def _default_installer_target_path(self, installer_name: str) -> Path:
        downloads_dir = Path.home() / "Downloads"
        if downloads_dir.exists() and downloads_dir.is_dir():
            return downloads_dir / installer_name
        return Path(local_config.default_config_path().parent) / installer_name

    def _prompt_download_latest_installer(
        self,
        *,
        latest_tag: str,
        installer_name: str,
        installer_url: str,
        checksum_url: str,
    ) -> None:
        if self._shutting_down:
            return
        current = self._pkg_version()
        title = self._t("update_download_prompt_title")
        body = self._t(
            "update_download_prompt_body",
            current=current,
            latest=latest_tag,
            installer=installer_name,
        )
        approved = messagebox.askyesno(title, body, parent=self.root)
        if not approved:
            return
        self._start_installer_download(
            installer_name=installer_name,
            installer_url=installer_url,
            checksum_url=checksum_url,
        )

    def _open_installer_progress_dialog(self) -> None:
        try:
            dialog = ctk.CTkToplevel(self.root)
            dialog.title(self._t("update_download_progress_title"))
            dialog.transient(self.root)
            dialog.grab_set()
            dialog.resizable(False, False)
            dialog.geometry("500x230")
            dialog.protocol("WM_DELETE_WINDOW", self._request_cancel_installer_download)
            frame = ctk.CTkFrame(dialog, fg_color="transparent")
            frame.pack(fill="both", expand=True, padx=18, pady=18)
            self._update_download_label = ctk.CTkLabel(
                frame,
                text=self._t("update_download_progress_starting"),
                anchor="w",
                justify="left",
                font=self._font_body,
            )
            self._update_download_label.pack(fill="x", pady=(0, 10))
            self._update_download_bar = ctk.CTkProgressBar(frame, mode="determinate")
            self._update_download_bar.set(0.0)
            self._update_download_bar.pack(fill="x")
            self._update_download_percent = ctk.CTkLabel(
                frame, text="0%", anchor="w", font=self._font_hint
            )
            self._update_download_percent.pack(fill="x", pady=(8, 0))
            self._update_download_meta = ctk.CTkLabel(
                frame, text="", anchor="w", justify="left", font=self._font_hint
            )
            self._update_download_meta.pack(fill="x", pady=(6, 0))
            self._btn_update_download_cancel = self._btn(
                frame,
                text=self._t("update_download_cancel"),
                command=self._request_cancel_installer_download,
                fg_color=self._BTN_SECONDARY,
                hover_color=self._BTN_SECONDARY_HOVER,
                text_color=(self._TEXT_BODY, self._TEXT_BODY),
            )
            self._btn_update_download_cancel.pack(anchor="e", pady=(12, 0))
            self._update_download_dialog = dialog
        except tk.TclError:
            self._update_download_dialog = None
            self._update_download_label = None
            self._update_download_bar = None
            self._update_download_percent = None
            self._update_download_meta = None
            self._btn_update_download_cancel = None

    def _close_installer_progress_dialog(self) -> None:
        dialog = self._update_download_dialog
        self._update_download_dialog = None
        self._update_download_label = None
        self._update_download_bar = None
        self._update_download_percent = None
        self._update_download_meta = None
        self._btn_update_download_cancel = None
        if dialog is None:
            return
        try:
            dialog.grab_release()
        except tk.TclError:
            pass
        try:
            dialog.destroy()
        except tk.TclError:
            pass

    def _update_installer_progress(self, downloaded: int, total: int | None) -> None:
        if self._shutting_down:
            return
        if self._update_download_bar is None or self._update_download_percent is None:
            return
        if total and total > 0:
            ratio = max(0.0, min(1.0, downloaded / total))
            self._update_download_bar.set(ratio)
            pct = int(ratio * 100)
            self._update_download_percent.configure(text=f"{pct}%")
            elapsed = max(0.001, time.monotonic() - self._update_download_started_at)
            speed_bps = downloaded / elapsed
            remain_sec = int(max(0.0, (total - downloaded) / speed_bps)) if speed_bps > 0 else 0
            if self._update_download_meta is not None:
                self._update_download_meta.configure(
                    text=self._t(
                        "update_download_progress_stats",
                        speed=self._format_speed(speed_bps),
                        eta=self._format_eta(remain_sec),
                    )
                )
            if self._update_download_label is not None:
                self._update_download_label.configure(
                    text=self._t("update_download_progress_running_pct", pct=pct)
                )
        else:
            self._update_download_bar.set(0.0)
            self._update_download_percent.configure(
                text=self._t("update_download_progress_bytes", bytes=downloaded)
            )
            if self._update_download_meta is not None:
                elapsed = max(0.001, time.monotonic() - self._update_download_started_at)
                speed_bps = downloaded / elapsed
                self._update_download_meta.configure(
                    text=self._t(
                        "update_download_progress_speed_only",
                        speed=self._format_speed(speed_bps),
                    )
                )

    def _format_speed(self, speed_bps: float) -> str:
        if speed_bps < 1024:
            return f"{int(speed_bps)} B/s"
        if speed_bps < 1024 * 1024:
            return f"{speed_bps / 1024:.1f} KB/s"
        return f"{speed_bps / (1024 * 1024):.2f} MB/s"

    def _format_eta(self, sec: int) -> str:
        if sec < 60:
            return f"{sec}s"
        m, s = divmod(sec, 60)
        if m < 60:
            return f"{m}m {s}s"
        h, m = divmod(m, 60)
        return f"{h}h {m}m"

    def _request_cancel_installer_download(self) -> None:
        if not self._update_download_in_progress:
            return
        self._update_download_cancel_requested = True
        if self._update_download_label is not None:
            self._update_download_label.configure(text=self._t("update_download_cancelling"))
        if self._btn_update_download_cancel is not None:
            self._btn_update_download_cancel.configure(state="disabled")

    def _start_installer_download(
        self, *, installer_name: str, installer_url: str, checksum_url: str
    ) -> None:
        if self._update_download_in_progress:
            self._show_info_banner(self._t("update_download_in_progress"))
            return
        self._update_download_in_progress = True
        self._update_download_cancel_requested = False
        self._update_download_started_at = time.monotonic()
        target_path = self._default_installer_target_path(installer_name)
        self._open_installer_progress_dialog()

        def _progress(downloaded: int, total: int | None) -> None:
            self.root.after(0, lambda: self._update_installer_progress(downloaded, total))

        def _worker() -> None:
            try:
                out = updater.download_file(
                    url=installer_url,
                    target_path=target_path,
                    progress_cb=_progress,
                    cancel_cb=lambda: self._update_download_cancel_requested,
                )
                expected_sha256 = ""
                actual_sha256 = ""
                checksum_verified = False
                if checksum_url:
                    checksum_text = updater.fetch_text(checksum_url)
                    digest = updater.parse_sha256_from_text(checksum_text, installer_name)
                    if digest:
                        expected_sha256 = digest
                if expected_sha256:
                    actual_sha256 = updater.sha256_file(out)
                    if actual_sha256.lower() != expected_sha256.lower():
                        raise RuntimeError(
                            self._t(
                                "update_checksum_mismatch_error",
                                expected=self._short_digest(expected_sha256),
                                actual=self._short_digest(actual_sha256),
                            )
                        )
                    checksum_verified = True
                self.root.after(
                    0,
                    lambda: self._on_installer_download_done(
                        path=out,
                        checksum_verified=checksum_verified,
                        checksum_digest=(actual_sha256 or expected_sha256),
                    ),
                )
            except updater.DownloadCancelledError:
                self.root.after(0, self._on_installer_download_cancelled)
            except Exception as exc:
                self.root.after(0, lambda: self._on_installer_download_failed(err=str(exc)))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_installer_download_done(
        self,
        *,
        path: Path,
        checksum_verified: bool = False,
        checksum_digest: str = "",
    ) -> None:
        self._update_download_in_progress = False
        self._close_installer_progress_dialog()
        if self._shutting_down:
            return
        digest_hint = ""
        if checksum_verified and checksum_digest:
            digest_hint = self._t(
                "update_checksum_verified_hint",
                digest=self._short_digest(checksum_digest),
            )
        approved = messagebox.askyesno(
            self._t("update_install_prompt_title"),
            self._t("update_install_prompt_body", path=str(path), verify_hint=digest_hint),
            parent=self.root,
        )
        if not approved:
            return
        try:
            if hasattr(os, "startfile"):
                os.startfile(str(path.resolve()))
            else:
                webbrowser.open(path.resolve().as_uri(), new=2)
            self._show_info_banner(self._t("update_install_started"))
        except OSError as exc:
            messagebox.showerror(
                self._t("update_install_prompt_title"),
                self._t("update_install_failed", err=str(exc)),
                parent=self.root,
            )

    def _on_installer_download_failed(self, *, err: str) -> None:
        self._update_download_in_progress = False
        self._close_installer_progress_dialog()
        if self._shutting_down:
            return
        messagebox.showerror(
            self._t("update_download_failed_title"),
            self._t("update_download_failed_body", err=err),
            parent=self.root,
        )

    def _on_installer_download_cancelled(self) -> None:
        self._update_download_in_progress = False
        self._close_installer_progress_dialog()
        if self._shutting_down:
            return
        self._show_info_banner(self._t("update_download_cancelled"))

    def _short_digest(self, digest: str) -> str:
        d = digest.strip().lower()
        if len(d) <= 16:
            return d
        return f"{d[:12]}...{d[-8:]}"

    def _build_global_update_notice(self) -> None:
        self._update_notice_shell = ctk.CTkFrame(
            self.root,
            fg_color="transparent",
        )
        self._update_notice_shell.grid(row=0, column=0, columnspan=2, sticky="ew")
        self._update_notice_shell.grid_columnconfigure(0, weight=1)
        self._update_notice = ctk.CTkFrame(
            self._update_notice_shell,
            corner_radius=_R,
            fg_color=self._STATUS_STRIP_BG_SCHEDULE,
            border_width=1,
            border_color=self._STATUS_STRIP_BORDER_SCHEDULE,
        )
        self._update_notice.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        self._update_notice.grid_columnconfigure(0, weight=1)
        _update_inner = ctk.CTkFrame(self._update_notice, fg_color="transparent")
        _update_inner.grid(row=0, column=0, sticky="ew", padx=12, pady=10)
        _update_inner.grid_columnconfigure(0, weight=1)
        self._lbl_update_notice = ctk.CTkLabel(
            _update_inner,
            text="",
            font=self._font_body,
            text_color=(self._STATUS_TEXT_SCHEDULE, self._STATUS_TEXT_SCHEDULE),
            anchor="w",
            justify="left",
        )
        self._lbl_update_notice.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.btn_update_notice_open = self._btn(
            _update_inner,
            text=self._t("update_banner_open"),
            command=self._open_update_from_banner,
            height=34,
            fg_color=self._ACCENT,
            hover_color=self._ACCENT_HOVER,
            text_color=(self._TEXT_ON_ACCENT, self._TEXT_ON_ACCENT),
            border_width=2,
            border_color=self._ACCENT_HOVER,
        )
        self.btn_update_notice_open.grid(row=0, column=1, sticky="e", padx=(0, 8))
        self.btn_update_notice_close = self._btn(
            _update_inner,
            text=self._t("update_banner_close"),
            command=self._hide_update_banner,
            height=34,
            fg_color=self._BTN_SECONDARY,
            hover_color=self._BTN_SECONDARY_HOVER,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            border_width=2,
            border_color=self._BORDER,
        )
        self.btn_update_notice_close.grid(row=0, column=2, sticky="e")
        self._update_notice_shell.grid_remove()

    def _check_updates(self, *, manual: bool) -> None:
        if self._update_check_in_progress:
            if manual:
                self._show_info_banner(self._t("update_check_in_progress"))
            return

        self._update_check_in_progress = True
        if manual:
            self._show_info_banner(self._t("update_banner_checking"))

        def _worker() -> None:
            try:
                latest = updater.fetch_latest_release()
                latest_tag = latest["tag"]
                latest_url = latest["url"] or "https://github.com/MomentaryChen/try-working-hard/releases"
                installer = updater.choose_windows_installer_asset(latest)
                installer_url = installer["url"] if installer else ""
                installer_name = installer["name"] if installer else ""
                checksum = updater.choose_checksum_asset(latest)
                checksum_url = checksum["url"] if checksum else ""
                checksum_name = checksum["name"] if checksum else ""
                release_summary = updater.summarize_release_notes(latest.get("body", ""))
                if not release_summary and latest.get("name"):
                    release_summary = str(latest["name"]).strip()
                current = self._pkg_version()
                has_update = updater.is_newer_version(latest_tag, current)
                self.root.after(
                    0,
                    lambda: self._handle_update_check_result(
                        has_update=has_update,
                        latest_tag=latest_tag,
                        latest_url=latest_url,
                        installer_url=installer_url,
                        installer_name=installer_name,
                        checksum_url=checksum_url,
                        checksum_name=checksum_name,
                        release_summary=release_summary,
                        current=current,
                        manual=manual,
                    ),
                )
            except Exception:
                self.root.after(0, lambda: self._handle_update_check_error(manual=manual))

        threading.Thread(target=_worker, daemon=True).start()

    def _handle_update_check_result(
        self,
        *,
        has_update: bool,
        latest_tag: str,
        latest_url: str,
        installer_url: str,
        installer_name: str,
        checksum_url: str,
        checksum_name: str,
        release_summary: str,
        current: str,
        manual: bool,
    ) -> None:
        self._update_check_in_progress = False
        if not manual:
            self._schedule_auto_update_check()
        if self._shutting_down:
            return
        if has_update:
            self._show_update_banner(
                latest_tag=latest_tag,
                current=current,
                latest_url=latest_url,
                installer_url=installer_url,
                installer_name=installer_name,
                checksum_url=checksum_url,
                checksum_name=checksum_name,
                summary=release_summary,
            )
            return
        if manual:
            self._show_info_banner(
                self._t("update_banner_latest", current=current),
            )

    def _handle_update_check_error(self, *, manual: bool) -> None:
        self._update_check_in_progress = False
        if not manual:
            self._schedule_auto_update_check(self._AUTO_UPDATE_RETRY_MS)
        if self._shutting_down or not manual:
            return
        self._show_info_banner(
            self._t("update_banner_error"),
        )

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
        self._sync_motion_pattern_seg()
        if hasattr(self, "_lbl_activity_style"):
            self._lbl_activity_style.configure(text=self._t("activity_style_label"))
        self._sync_activity_style_seg()
        if hasattr(self, "swt_natural_click"):
            self.swt_natural_click.configure(text=self._t("natural_rare_click"))
        if hasattr(self, "swt_natural_scroll"):
            self.swt_natural_scroll.configure(text=self._t("natural_rare_scroll"))
        if hasattr(self, "_lbl_natural_opts_hint"):
            self._lbl_natural_opts_hint.configure(text=self._t("natural_opts_hint"))
        self._refresh_activity_dependent_widgets()
        self._lbl_pixels.configure(text=self._t("pixels_label"))
        self._lbl_pixels_hint.configure(
            text=self._t("pixels_hint", lo=self.MIN_PIXELS, hi=self.MAX_PIXELS)
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
        self._refresh_schedule_banner()

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
        self._sidebar.grid(row=1, column=0, sticky="nsew", padx=(p, 0), pady=p)
        self._sidebar.grid_propagate(False)
        sidebar = self._sidebar

        self._brand = ctk.CTkLabel(
            sidebar,
            text=self._app_title_with_version(),
            font=self._font_brand,
            text_color=(self._TEXT_TITLE, self._TEXT_TITLE),
            anchor="w",
        )
        self._brand.pack(anchor="w", padx=p, pady=(p, 4))

        sub = self._t("app_subtitle").strip()
        self._lbl_subtitle = ctk.CTkLabel(
            sidebar,
            text=sub,
            font=self._font_body,
            text_color=self._TEXT_BODY,
            anchor="w",
        )
        if sub:
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
        main.grid(row=1, column=1, sticky="nsew", padx=(0, p), pady=p)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(0, weight=1)

        self.pages_host = ctk.CTkFrame(main, corner_radius=_R, fg_color="transparent")
        self.pages_host.grid(row=0, column=0, sticky="nsew")
        self.pages_host.grid_columnconfigure(0, weight=1)
        self.pages_host.grid_rowconfigure(0, weight=1)

        self.page_home = ctk.CTkFrame(self.pages_host, corner_radius=_R, fg_color="transparent")
        self.page_home.grid(row=0, column=0, sticky="nsew")
        self.page_home.grid_columnconfigure(0, weight=1)
        self.page_home.grid_rowconfigure(2, weight=1)

        self._home_top_status = ctk.CTkFrame(self.page_home, fg_color="transparent")
        self._home_top_status.grid(row=0, column=0, sticky="ew", padx=p, pady=(p, 8))
        self._home_top_status.grid_columnconfigure(0, weight=1)

        self._status_strip = ctk.CTkFrame(
            self._home_top_status,
            corner_radius=_R,
            fg_color=self._STATUS_STRIP_BG_STOP,
            border_width=1,
            border_color=self._STATUS_STRIP_BORDER_STOP,
        )
        self._status_strip.grid(row=0, column=0, sticky="ew")
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

        self._lbl_schedule_banner = ctk.CTkLabel(
            self._home_top_status,
            text="",
            font=self._font_body,
            text_color=self._TEXT_MUTED,
            anchor="w",
            fg_color=self._SURFACE_SUBTLE,
            corner_radius=_R,
            height=36,
            padx=12,
            pady=6,
        )
        self._lbl_schedule_banner.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        self._lbl_schedule_banner.grid_remove()

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
        self.content_host.grid(row=2, column=0, sticky="nsew", padx=p, pady=(0, p))
        self.content_host.grid_columnconfigure(0, weight=1)
        self.content_host.grid_rowconfigure(0, weight=1)

        self.page_settings = ctk.CTkFrame(self.pages_host, corner_radius=_R, fg_color="transparent")
        self.page_settings.grid_columnconfigure(0, weight=1)
        self.page_settings.grid_rowconfigure(1, weight=1)

        _ps = self._UI_PAD
        settings_head = ctk.CTkFrame(self.page_settings, fg_color="transparent")
        settings_head.grid(row=0, column=0, sticky="ew", padx=_ps, pady=(_ps, _ps))
        settings_head.grid_columnconfigure(0, weight=1)
        self._lbl_settings_title = ctk.CTkLabel(
            settings_head,
            text=self._t("settings_title"),
            font=self._font_title,
            text_color=(self._TEXT_TITLE, self._TEXT_TITLE),
        )
        self._lbl_settings_title.grid(row=0, column=0, sticky="w")

        self._settings_scroll = ctk.CTkScrollableFrame(
            self.page_settings,
            fg_color=self._CARD_BG,
            corner_radius=_R,
            border_width=1,
            border_color=self._CARD_BORDER,
            scrollbar_button_color=self._BTN_SECONDARY,
            scrollbar_button_hover_color=self._BTN_SECONDARY_HOVER,
        )
        self._settings_scroll.grid(row=1, column=0, sticky="nsew", padx=_ps, pady=(0, _ps))
        self._settings_scroll.grid_columnconfigure(0, weight=1)
        self._fill_settings_panel(self._settings_scroll)

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

        self.page_analytics = ctk.CTkFrame(self.pages_host, corner_radius=_R, fg_color="transparent")
        self.page_analytics.grid_columnconfigure(0, weight=1)
        self.page_analytics.grid_rowconfigure(1, weight=1)

        analytics_head = ctk.CTkFrame(self.page_analytics, fg_color="transparent")
        analytics_head.grid(row=0, column=0, sticky="ew", padx=_ps, pady=(_ps, _ps))
        analytics_head.grid_columnconfigure(0, weight=1)
        self._lbl_analytics_title = ctk.CTkLabel(
            analytics_head,
            text=self._t("analytics_title"),
            font=self._font_title,
            text_color=(self._TEXT_TITLE, self._TEXT_TITLE),
        )
        self._lbl_analytics_title.grid(row=0, column=0, sticky="w")

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

    def _parsed_schedule_bounds_raw(self) -> tuple[dtime, dtime] | None:
        """Return parsed start/end, or ``None`` if strings are invalid."""
        a = schedule_window.parse_hhmm(self.var_schedule_start.get())
        b = schedule_window.parse_hhmm(self.var_schedule_end.get())
        if a is None or b is None:
            return None
        return (a, b)

    def _effective_schedule_bounds(self) -> tuple[dtime, dtime]:
        """Bounds used by the worker; falls back when labels are malformed."""
        p = self._parsed_schedule_bounds_raw()
        if p is None:
            return (
                schedule_window.DEFAULT_WORK_START,
                schedule_window.DEFAULT_WORK_END,
            )
        ws, we = p
        if ws < we:
            return ws, we
        return (
            schedule_window.DEFAULT_WORK_START,
            schedule_window.DEFAULT_WORK_END,
        )

    def _sync_schedule_times_from_vars(self) -> None:
        self._schedule_ws, self._schedule_we = self._effective_schedule_bounds()
        self._schedule_segments_text = (
            f"{self.var_schedule_start.get().strip()}-{self.var_schedule_end.get().strip()}"
        )

    def _build_schedule_spec(self) -> schedule_window.ScheduleSpec | None:
        return schedule_window.build_schedule_spec(
            window_segments_text=self._schedule_segments_text,
            include_weekends=self._schedule_include_weekends,
            cron_text=self._schedule_cron_text,
            weekday_text="mon-fri",
        )

    def _refresh_schedule_banner(self) -> None:
        if not hasattr(self, "_lbl_schedule_banner"):
            return
        if not bool(self.var_schedule_window.get()):
            self._lbl_schedule_banner.grid_remove()
            return
        p = self._parsed_schedule_bounds_raw()
        self._sync_schedule_times_from_vars()
        spec = self._build_schedule_spec()
        if spec is None:
            self._lbl_schedule_banner.configure(
                text=self._t("schedule_banner_need_valid_times"),
            )
        else:
            ws, we = p if p is not None and p[0] < p[1] else (
                schedule_window.DEFAULT_WORK_START,
                schedule_window.DEFAULT_WORK_END,
            )
            weekend_text = self._t("schedule_weekend_on") if self._schedule_include_weekends else self._t("schedule_weekend_off")
            cron_text = self._schedule_cron_text.strip() or self._t("schedule_cron_off")
            self._lbl_schedule_banner.configure(
                text=self._t(
                    "schedule_banner_active",
                    start=schedule_window.format_hhmm(ws),
                    end=schedule_window.format_hhmm(we),
                    weekend=weekend_text,
                    cron=cron_text,
                ),
            )
        self._lbl_schedule_banner.grid(row=1, column=0, sticky="ew", pady=(6, 0))

    def _fill_settings_panel(self, card: ctk.CTkScrollableFrame) -> None:
        p = self._UI_PAD
        card.grid_columnconfigure(0, weight=1)

        self._lbl_appearance = ctk.CTkLabel(
            card,
            text=self._t("theme_appearance"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            anchor="w",
        )
        self._lbl_appearance.grid(row=0, column=0, sticky="w", padx=p, pady=(0, p))

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
        self._seg_ui_theme.grid(row=1, column=0, sticky="ew", padx=p, pady=(0, p))
        self._sync_ui_theme_seg()
        _try_takefocus(self._seg_ui_theme, 1)

        self._hint_appearance = ctk.CTkLabel(
            card,
            text=self._theme_footer_text(),
            font=ctk.CTkFont(family=_FONT_INTER, size=11),
            text_color=self._TEXT_MUTED,
            anchor="w",
        )
        self._hint_appearance.grid(row=2, column=0, sticky="w", padx=p, pady=(p, p))

        self._lbl_lang = ctk.CTkLabel(
            card,
            text=self._t("lang_ui"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            anchor="w",
        )
        self._lbl_lang.grid(row=3, column=0, sticky="w", padx=p, pady=(0, p))

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
        self._lang_seg.grid(row=4, column=0, sticky="ew", padx=p, pady=(0, p))
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
        self.btn_open_config.grid(row=5, column=0, sticky="w", padx=p, pady=(0, p))
        _try_takefocus(self.btn_open_config, 1)

        self.var_schedule_window = tk.BooleanVar(value=False)
        self.var_schedule_start = tk.StringVar(value="09:00")
        self.var_schedule_end = tk.StringVar(value="18:00")

        schedule_row = ctk.CTkFrame(card, fg_color="transparent")
        schedule_row.grid(row=6, column=0, sticky="ew", padx=p, pady=(0, 8))
        schedule_row.grid_columnconfigure(0, weight=1)
        self._lbl_schedule_sw = ctk.CTkLabel(
            schedule_row,
            text=self._t("schedule_window_title"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            anchor="w",
        )
        self._lbl_schedule_sw.grid(row=0, column=0, sticky="w")
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
            button_hover_color="#E2E8F0",
            font=self._font_body,
        )
        self.swt_schedule.grid(row=0, column=1, sticky="e", padx=(16, 0))
        _try_takefocus(self.swt_schedule, 1)

        schedule_time_row = ctk.CTkFrame(card, fg_color="transparent")
        schedule_time_row.grid(row=7, column=0, sticky="ew", padx=p, pady=(0, p))
        self._lbl_schedule_time_start = ctk.CTkLabel(
            schedule_time_row,
            text=self._t("schedule_window_start_label"),
            font=self._font_body,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
        )
        self._lbl_schedule_time_start.pack(side="left")
        self.entry_schedule_start = ctk.CTkEntry(
            schedule_time_row,
            textvariable=self.var_schedule_start,
            width=96,
            height=40,
            corner_radius=_R,
            font=self._font_body,
            fg_color=self._ENTRY_BG,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            border_width=1,
            border_color=self._ENTRY_BORDER,
        )
        self.entry_schedule_start.pack(side="left", padx=(8, 20))
        _try_takefocus(self.entry_schedule_start, 1)
        self._lbl_schedule_time_end = ctk.CTkLabel(
            schedule_time_row,
            text=self._t("schedule_window_end_label"),
            font=self._font_body,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
        )
        self._lbl_schedule_time_end.pack(side="left")
        self.entry_schedule_end = ctk.CTkEntry(
            schedule_time_row,
            textvariable=self.var_schedule_end,
            width=96,
            height=40,
            corner_radius=_R,
            font=self._font_body,
            fg_color=self._ENTRY_BG,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            border_width=1,
            border_color=self._ENTRY_BORDER,
        )
        self.entry_schedule_end.pack(side="left", padx=(8, 0))
        _try_takefocus(self.entry_schedule_end, 1)

        self._hint_schedule = ctk.CTkLabel(
            card,
            text=self._t("schedule_window_hint"),
            font=self._font_hint,
            text_color=self._TEXT_MUTED,
            anchor="w",
            justify="left",
            wraplength=520,
        )
        self._hint_schedule.grid(row=8, column=0, sticky="ew", padx=p, pady=(0, p))

        self.var_tray_close = tk.BooleanVar(value=False)
        tray_row = ctk.CTkFrame(card, fg_color="transparent")
        tray_row.grid(row=9, column=0, sticky="ew", padx=p, pady=(0, 8))
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
            button_hover_color="#E2E8F0",
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
        self._hint_tray.grid(row=10, column=0, sticky="ew", padx=p, pady=(0, p))
        if not HAS_TRAY:
            self.swt_tray.configure(state="disabled")

        can_autowin = sys.platform == "win32" and HAS_TRAY
        self.var_autostart_win = tk.BooleanVar(
            value=bool(can_autowin and _windows_run_autostart_active())
        )
        autostart_row = ctk.CTkFrame(card, fg_color="transparent")
        autostart_row.grid(row=11, column=0, sticky="ew", padx=p, pady=(0, 8))
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
            button_hover_color="#E2E8F0",
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
        self._hint_autostart.grid(row=12, column=0, sticky="ew", padx=p, pady=(0, p))
        if not can_autowin:
            self.swt_autostart.configure(state="disabled")

        self._lbl_about_updates = ctk.CTkLabel(
            card,
            text=self._t("about_updates_title"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            anchor="w",
        )
        self._lbl_about_updates.grid(row=13, column=0, sticky="w", padx=p, pady=(0, 8))

        self._lbl_version_info = ctk.CTkLabel(
            card,
            text=self._t("version_info", version=self._pkg_version()),
            font=self._font_body,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            anchor="w",
        )
        self._lbl_version_info.grid(row=14, column=0, sticky="w", padx=p, pady=(0, 8))

        about_btn_row = ctk.CTkFrame(card, fg_color="transparent")
        about_btn_row.grid(row=15, column=0, sticky="w", padx=p, pady=(0, p))
        self.btn_contact_us = self._btn(
            about_btn_row,
            text=self._t("btn_contact_us"),
            command=self._on_contact_us,
            fg_color="transparent",
            hover_color=self._NAV_HOVER,
            text_color=(self._NAV_TEXT, self._NAV_TEXT),
            anchor="w",
        )
        self.btn_contact_us.pack(side="left", padx=(0, 8))
        _try_takefocus(self.btn_contact_us, 1)

        self.btn_check_updates = self._btn(
            about_btn_row,
            text=self._t("btn_check_updates"),
            command=self._on_check_updates,
            fg_color=self._ACCENT,
            hover_color=self._ACCENT_HOVER,
            text_color=(self._TEXT_ON_ACCENT, self._TEXT_ON_ACCENT),
            border_width=2,
            border_color=self._ACCENT_HOVER,
        )
        self.btn_check_updates.pack(side="left")
        _try_takefocus(self.btn_check_updates, 1)

        self.var_auto_check_updates = tk.BooleanVar(value=True)
        auto_updates_row = ctk.CTkFrame(card, fg_color="transparent")
        auto_updates_row.grid(row=16, column=0, sticky="ew", padx=p, pady=(0, 8))
        auto_updates_row.grid_columnconfigure(0, weight=1)
        self._lbl_auto_updates_sw = ctk.CTkLabel(
            auto_updates_row,
            text=self._t("auto_check_updates_title"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            anchor="w",
        )
        self._lbl_auto_updates_sw.grid(row=0, column=0, sticky="w")
        self.swt_auto_updates = ctk.CTkSwitch(
            auto_updates_row,
            text="",
            variable=self.var_auto_check_updates,
            width=52,
            switch_width=40,
            switch_height=22,
            fg_color=self._BORDER,
            progress_color=self._ACCENT,
            button_color="#FFFFFF",
            button_hover_color="#E2E8F0",
            font=self._font_body,
        )
        self.swt_auto_updates.grid(row=0, column=1, sticky="e", padx=(16, 0))
        _try_takefocus(self.swt_auto_updates, 1)
        self._hint_auto_updates = ctk.CTkLabel(
            card,
            text=self._t("auto_check_updates_hint"),
            font=self._font_hint,
            text_color=self._TEXT_MUTED,
            anchor="w",
            justify="left",
            wraplength=520,
        )
        self._hint_auto_updates.grid(row=17, column=0, sticky="ew", padx=p, pady=(0, p))

    def _fill_analytics_panel(self, card: ctk.CTkFrame) -> None:
        from matplotlib.figure import Figure

        p = self._UI_PAD
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)

        self.analytics_scroll = ctk.CTkScrollableFrame(
            card,
            fg_color=self._CARD_BG,
            corner_radius=_R,
            border_width=1,
            border_color=self._CARD_BORDER,
            scrollbar_button_color=self._BTN_SECONDARY,
            scrollbar_button_hover_color=self._BTN_SECONDARY_HOVER,
        )
        self.analytics_scroll.grid(row=1, column=0, sticky="nsew", padx=p, pady=(0, p))
        self.analytics_scroll.grid_columnconfigure(0, weight=1)

        self._lbl_analytics_sub = ctk.CTkLabel(
            self.analytics_scroll,
            text=self._t("analytics_subtitle"),
            font=self._font_body,
            text_color=self._TEXT_MUTED,
            anchor="w",
        )
        self._lbl_analytics_sub.grid(row=0, column=0, sticky="w", padx=p, pady=(p, p))

        self._analytics_trigger_mode = "today"

        self._lbl_chart_triggers = ctk.CTkLabel(
            self.analytics_scroll,
            text=self._t("analytics_chart_triggers"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            anchor="w",
        )
        self._lbl_chart_triggers.grid(row=1, column=0, sticky="w", padx=p, pady=(p, 4))

        seg_row = ctk.CTkFrame(self.analytics_scroll, fg_color="transparent")
        seg_row.grid(row=2, column=0, sticky="ew", padx=p, pady=(0, p))
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
        trig_host.grid(row=3, column=0, sticky="ew", padx=p, pady=(0, p))

        self._fig_trigger = Figure(figsize=(6.5, 2.85), dpi=100)
        self._mpl_canvas_trigger = analytics_charts.attach_canvas(self._fig_trigger, trig_host)

        self._lbl_chart_runtime = ctk.CTkLabel(
            self.analytics_scroll,
            text=self._t("analytics_chart_runtime"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            anchor="w",
        )
        self._lbl_chart_runtime.grid(row=4, column=0, sticky="w", padx=p, pady=(p, 4))

        run_host = tk.Frame(self.analytics_scroll, bg=self._CARD_BG)
        run_host.grid(row=5, column=0, sticky="ew", padx=p, pady=(0, p))

        self._fig_runtime = Figure(figsize=(6.5, 2.85), dpi=100)
        self._mpl_canvas_runtime = analytics_charts.attach_canvas(self._fig_runtime, run_host)

        self._lbl_chart_patterns = ctk.CTkLabel(
            self.analytics_scroll,
            text=self._t("analytics_chart_patterns"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            anchor="w",
        )
        self._lbl_chart_patterns.grid(row=6, column=0, sticky="w", padx=p, pady=(p, 4))

        pie_host = tk.Frame(self.analytics_scroll, bg=self._CARD_BG)
        pie_host.grid(row=7, column=0, sticky="ew", padx=p, pady=(0, p))

        self._fig_patterns = Figure(figsize=(6.5, 2.95), dpi=100)
        self._mpl_canvas_patterns = analytics_charts.attach_canvas(self._fig_patterns, pie_host)

        self.analytics_log = ctk.CTkTextbox(
            self.analytics_scroll,
            corner_radius=_R,
            font=self._font_mono,
            fg_color=self._ENTRY_BG,
            text_color=(self._TEXT_LOG, self._TEXT_LOG),
            border_width=1,
            border_color=self._ENTRY_BORDER,
            height=150,
        )
        self.analytics_log.grid(row=8, column=0, sticky="ew", padx=p, pady=(0, p))
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
        fp = analytics_charts.prepare_chart_font(self._lang)
        mode = self._analytics_trigger_mode
        analytics_charts.render_trigger_figure(
            self._fig_trigger,
            fp=fp,
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
            fp=fp,
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
            self._t("activity_style_natural"),
        )
        analytics_charts.render_patterns_figure(
            self._fig_patterns,
            fp=fp,
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
            except (OSError, RuntimeError, ValueError, tk.TclError):
                _LOG.exception("Failed to refresh analytics charts")
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

        self.var_natural_rare_click = tk.BooleanVar(value=False)
        self.var_natural_rare_scroll = tk.BooleanVar(value=False)

        self._lbl_activity_style = ctk.CTkLabel(
            card,
            text=self._t("activity_style_label"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
        )
        self._lbl_activity_style.grid(row=10, column=0, sticky="w", padx=p, pady=(p, p))
        row_activity = ctk.CTkFrame(card, fg_color="transparent")
        row_activity.grid(row=11, column=0, sticky="ew", padx=p, pady=(0, p))
        self.seg_activity_style = ctk.CTkSegmentedButton(
            row_activity,
            values=[
                self._t("activity_style_pattern"),
                self._t("activity_style_natural"),
            ],
            command=self._on_activity_style_seg,
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
        _try_takefocus(self.seg_activity_style, 1)
        self.seg_activity_style.pack(side="left")
        self._sync_activity_style_seg()
        self._a11y_label_focus_entry(self._lbl_activity_style, self.seg_activity_style)

        self.row_natural_opts = ctk.CTkFrame(card, fg_color="transparent")
        self.row_natural_opts.grid(row=12, column=0, sticky="ew", padx=p, pady=(0, p))
        col_nat = ctk.CTkFrame(self.row_natural_opts, fg_color="transparent")
        col_nat.pack(side="left", fill="x", expand=True)
        self.swt_natural_click = ctk.CTkSwitch(
            col_nat,
            text=self._t("natural_rare_click"),
            variable=self.var_natural_rare_click,
            font=self._font_body,
            command=self._on_natural_pref_changed,
            progress_color=self._ACCENT,
        )
        self.swt_natural_click.pack(anchor="w", pady=(0, 6))
        self.swt_natural_scroll = ctk.CTkSwitch(
            col_nat,
            text=self._t("natural_rare_scroll"),
            variable=self.var_natural_rare_scroll,
            font=self._font_body,
            command=self._on_natural_pref_changed,
            progress_color=self._ACCENT,
        )
        self.swt_natural_scroll.pack(anchor="w")
        self._lbl_natural_opts_hint = ctk.CTkLabel(
            self.row_natural_opts,
            text=self._t("natural_opts_hint"),
            font=self._font_hint,
            text_color=self._TEXT_MUTED,
            wraplength=380,
            justify="left",
        )
        self._lbl_natural_opts_hint.pack(side="left", padx=(16, 0), fill="x", expand=True)

        self._lbl_motion_pattern = ctk.CTkLabel(
            card,
            text=self._t("motion_pattern_label"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
        )
        self._lbl_motion_pattern.grid(row=13, column=0, sticky="w", padx=p, pady=(p, p))
        row_pattern = ctk.CTkFrame(card, fg_color="transparent")
        row_pattern.grid(row=14, column=0, sticky="ew", padx=p, pady=(0, p))
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

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.grid(row=15, column=0, sticky="w", padx=p, pady=(p, p))

        self.btn_start = self._btn(
            btn_row,
            text=self._t("btn_start"),
            width=120,
            fg_color=self._ACCENT,
            hover_color=self._ACCENT_HOVER,
            text_color=(self._TEXT_ON_ACCENT, self._TEXT_ON_ACCENT),
            border_width=2,
            border_color=self._ACCENT_HOVER,
            font=self._font_body_bold,
            command=self._on_start,
        )
        self.btn_start.pack(side="left", padx=(0, 12))

        self.btn_stop = self._btn(
            btn_row,
            text=self._t("btn_stop"),
            width=120,
            fg_color=self._BTN_SECONDARY,
            hover_color=self._BTN_SECONDARY_HOVER,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            border_width=2,
            border_color=self._BORDER,
            state="disabled",
            command=self._on_stop,
        )
        self.btn_stop.pack(side="left")
        self._refresh_activity_dependent_widgets()

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
        activity_style: ActivityStyle,
        natural_rare_click: bool,
        natural_rare_scroll: bool,
        log_success: bool = True,
    ) -> None:
        try:
            if activity_style == "natural":
                jiggle_natural(
                    pixels,
                    path_speed=path_speed,
                    rare_click=natural_rare_click,
                    rare_scroll=natural_rare_scroll,
                )
                rec_key = "natural"
            else:
                jiggle_mouse(pixels, pattern, path_speed=path_speed)
                rec_key = pattern
            if not log_success:
                return
            analytics_store.record_nudge(rec_key)
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

        if bool(self.var_schedule_window.get()):
            psched = self._build_schedule_spec()
            if psched is None:
                messagebox.showerror(
                    self._t("err_title"),
                    self._t("err_schedule_bounds"),
                    parent=self.root,
                )
                self._log(self._t("log_start_fail_schedule_bounds"))
                return

        self._stop.clear()
        self._run_schedule_window = bool(self.var_schedule_window.get())
        interval_sec = ival * 60.0 if iu == "min" else ival
        self._running_interval_value = ival
        self._running_interval_unit = iu
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
                run_activity,
                run_pattern,
                n_click,
                n_scroll,
            ),
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
            self.seg_activity_style.configure(state="disabled")
        except (tk.TclError, AttributeError):
            pass
        try:
            self.swt_natural_click.configure(state="disabled")
            self.swt_natural_scroll.configure(state="disabled")
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
            self.seg_activity_style.configure(state="normal")
        except (tk.TclError, AttributeError):
            pass
        try:
            self.swt_natural_click.configure(state="normal")
            self.swt_natural_scroll.configure(state="normal")
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
                activity_style=activity_style,
                natural_rare_click=natural_rare_click,
                natural_rare_scroll=natural_rare_scroll,
                log_success=True,
            )
            last_nudge_monotonic = now
            active_interval = nudge_logic.next_wait_seconds(interval_sec, jitter_sec)

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

        self._cancel_analytics_runtime_flush()
        self._cancel_auto_update_check()
        self._close_installer_progress_dialog()
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
