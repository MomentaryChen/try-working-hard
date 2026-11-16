"""Dark/light palettes and re-applying them to live widgets."""

from __future__ import annotations

import customtkinter as ctk

from .ui_common import (
    UiTheme,
)

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


class ThemeMixin:
    """Mixin for :class:`mouse_jiggler.app.MouseJigglerApp`; relies on its shared state."""

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
            "entry_motion_duration",
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

        if hasattr(self, "btn_run_toggle"):
            self.btn_run_toggle.configure(
                fg_color=self._ACCENT,
                hover_color=self._ACCENT_HOVER,
                text_color=(self._TEXT_ON_ACCENT, self._TEXT_ON_ACCENT),
                border_width=2,
                border_color=self._ACCENT_HOVER,
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
            "_lbl_motion_duration",
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
            "_lbl_motion_duration_hint",
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
        if getattr(self, "_lbl_analytics_loading", None) is not None:
            self._lbl_analytics_loading.configure(text_color=self._TEXT_MUTED)
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
