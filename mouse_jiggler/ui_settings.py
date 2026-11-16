"""Settings page widgets and schedule-window helpers."""

from __future__ import annotations

import os
import sys
import tkinter as tk
import webbrowser
from datetime import time as dtime

import customtkinter as ctk

from . import (
    local_config,
    schedule_window,
)
from .tray import HAS_TRAY
from .ui_common import (
    _R,
    _try_takefocus,
)
from .win_autostart import (
    _windows_run_autoset,
    _windows_run_autostart_active,
)


class SettingsMixin:
    """Mixin for :class:`mouse_jiggler.app.MouseJigglerApp`; relies on its shared state."""

    def _on_autostart_win_committed(self) -> None:
        if self._shutting_down or self._config_loading:
            return
        if sys.platform != "win32" or not HAS_TRAY:
            return
        _windows_run_autoset(bool(self.var_autostart_win.get()))

    def _on_open_config_file(self) -> None:
        path = local_config.default_config_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.is_file():
                self._save_config_now()
            if hasattr(os, "startfile"):
                os.startfile(str(path.resolve()))
            else:
                self._show_info_dialog(
                    self._t("settings_title"),
                    self._t("open_config_path_only", path=str(path.resolve())),
                )
        except OSError as e:
            self._show_error_dialog(
                self._t("err_title"),
                self._t("err_open_config_file", err=str(e)),
            )

    def _on_contact_us(self) -> None:
        url = "https://github.com/MomentaryChen/try-working-hard/issues/new/choose"
        should_open = self._ask_yes_no_dialog(
            self._t("btn_contact_us"),
            self._t(
                "contact_us_body",
                url=url,
                desc=self._t("contact_us_desc_default"),
                email="zzser15963",
                name="Momentary (Victor Chen)",
            ),
        )
        if should_open:
            webbrowser.open(url, new=2)

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
        before = (self._schedule_ws, self._schedule_we, self._schedule_segments_text)
        self._schedule_ws, self._schedule_we = self._effective_schedule_bounds()
        self._schedule_segments_text = (
            f"{self.var_schedule_start.get().strip()}-{self.var_schedule_end.get().strip()}"
        )
        if (self._schedule_ws, self._schedule_we, self._schedule_segments_text) != before:
            self._schedule_changed.set()

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

        self._lbl_lang = ctk.CTkLabel(
            card,
            text=self._t("lang_ui"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            anchor="w",
        )
        self._lbl_lang.grid(row=2, column=0, sticky="w", padx=p, pady=(0, p))

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
        self._lang_seg.grid(row=3, column=0, sticky="ew", padx=p, pady=(0, p))
        self._lang_seg.set("English")
        _try_takefocus(self._lang_seg, 1)

        self.var_schedule_window = tk.BooleanVar(value=False)
        self.var_schedule_start = tk.StringVar(value="09:00")
        self.var_schedule_end = tk.StringVar(value="18:00")

        schedule_row = ctk.CTkFrame(card, fg_color="transparent")
        schedule_row.grid(row=4, column=0, sticky="ew", padx=p, pady=(0, 8))
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
        schedule_time_row.grid(row=5, column=0, sticky="ew", padx=p, pady=(0, p))
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
        self._hint_schedule.grid(row=6, column=0, sticky="ew", padx=p, pady=(0, p))

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
        self._hint_autostart.grid(row=10, column=0, sticky="ew", padx=p, pady=(0, p))
        if not can_autowin:
            self.swt_autostart.configure(state="disabled")

        self._lbl_about_updates = ctk.CTkLabel(
            card,
            text=self._t("about_updates_title"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            anchor="w",
        )
        self._lbl_about_updates.grid(row=11, column=0, sticky="w", padx=p, pady=(0, 8))

        self._lbl_version_info = ctk.CTkLabel(
            card,
            text=self._t("version_info", version=self._pkg_version()),
            font=self._font_body,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            anchor="w",
        )
        self._lbl_version_info.grid(row=12, column=0, sticky="w", padx=p, pady=(0, 8))

        about_btn_row = ctk.CTkFrame(card, fg_color="transparent")
        about_btn_row.grid(row=13, column=0, sticky="w", padx=p, pady=(0, p))
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

        self.btn_open_config = self._btn(
            about_btn_row,
            text=self._t("btn_open_config_file"),
            command=self._on_open_config_file,
            fg_color="transparent",
            hover_color=self._NAV_HOVER,
            text_color=(self._NAV_TEXT, self._NAV_TEXT),
            anchor="w",
        )
        self.btn_open_config.pack(side="left", padx=(0, 8))
        _try_takefocus(self.btn_open_config, 1)

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
        auto_updates_row.grid(row=14, column=0, sticky="ew", padx=p, pady=(0, 8))
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
        self._hint_auto_updates.grid(row=15, column=0, sticky="ew", padx=p, pady=(0, p))

        self.var_keep_display_awake = tk.BooleanVar(value=True)
        keep_awake_row = ctk.CTkFrame(card, fg_color="transparent")
        keep_awake_row.grid(row=16, column=0, sticky="ew", padx=p, pady=(0, 8))
        keep_awake_row.grid_columnconfigure(0, weight=1)
        self._lbl_keep_awake_sw = ctk.CTkLabel(
            keep_awake_row,
            text=self._t("keep_display_awake_title"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            anchor="w",
        )
        self._lbl_keep_awake_sw.grid(row=0, column=0, sticky="w")
        self.swt_keep_awake = ctk.CTkSwitch(
            keep_awake_row,
            text="",
            variable=self.var_keep_display_awake,
            width=52,
            switch_width=40,
            switch_height=22,
            fg_color=self._BORDER,
            progress_color=self._ACCENT,
            button_color="#FFFFFF",
            button_hover_color="#E2E8F0",
            font=self._font_body,
        )
        self.swt_keep_awake.grid(row=0, column=1, sticky="e", padx=(16, 0))
        _try_takefocus(self.swt_keep_awake, 1)
        self._hint_keep_awake = ctk.CTkLabel(
            card,
            text=self._t("keep_display_awake_hint"),
            font=self._font_hint,
            text_color=self._TEXT_MUTED,
            anchor="w",
            justify="left",
            wraplength=520,
        )
        self._hint_keep_awake.grid(row=17, column=0, sticky="ew", padx=p, pady=(0, p))
