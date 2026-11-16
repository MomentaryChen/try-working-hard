"""Home page widgets: Control and Log panels."""

from __future__ import annotations

import tkinter as tk
from typing import Literal

import customtkinter as ctk

from .ui_common import (
    _R,
    _try_takefocus,
)


class ControlPanelMixin:
    """Mixin for :class:`mouse_jiggler.app.MouseJigglerApp`; relies on its shared state."""

    def _fill_control_panel(self, card: ctk.CTkFrame | ctk.CTkScrollableFrame) -> None:
        card.grid_columnconfigure(0, weight=1)
        p = self._UI_PAD

        mode_top = ctk.CTkFrame(card, fg_color="transparent")
        mode_top.grid(row=0, column=0, sticky="ew", padx=p, pady=(p, p))

        self._lbl_activity_style = ctk.CTkLabel(
            mode_top,
            text=self._t("activity_style_label"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
        )
        self._lbl_activity_style.pack(anchor="w")
        row_activity = ctk.CTkFrame(mode_top, fg_color="transparent")
        row_activity.pack(anchor="w", pady=(4, 0), fill="x")
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

        self._lbl_activity_mode_params = ctk.CTkLabel(
            mode_top,
            text=self._t("activity_mode_params_fixed"),
            font=self._font_hint,
            text_color=self._TEXT_MUTED,
            justify="left",
            anchor="w",
            wraplength=640,
        )
        self._lbl_activity_mode_params.pack(anchor="w", pady=(4, 0), fill="x")

        self._extra_params_card = ctk.CTkFrame(
            card,
            corner_radius=12,
            fg_color=self._SURFACE_SUBTLE,
            border_width=1,
            border_color=self._ENTRY_BORDER,
        )
        self._extra_params_card.grid(row=6, column=0, sticky="ew", padx=p, pady=(0, p))
        self._extra_params_card.grid_columnconfigure(0, weight=1)
        self._lbl_extra_params_title = ctk.CTkLabel(
            self._extra_params_card,
            text=self._t("fixed_params_title"),
            font=self._font_hint,
            text_color=self._TEXT_MUTED,
            anchor="w",
        )
        self._lbl_extra_params_title.grid(row=0, column=0, sticky="w", padx=12, pady=(10, 0))
        params_host: ctk.CTkFrame | ctk.CTkScrollableFrame = self._extra_params_card

        self._lbl_interval = ctk.CTkLabel(
            params_host,
            text=self._t("interval_label"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
        )
        self._lbl_interval.grid(row=4, column=0, sticky="w", padx=12, pady=(p, p))
        row1 = ctk.CTkFrame(params_host, fg_color="transparent")
        row1.grid(row=5, column=0, sticky="ew", padx=p, pady=(0, p))
        self.var_minutes = tk.StringVar(value=str(int(self.DEFAULT_MINUTES * 60)))
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
        self._lbl_interval_hint = ctk.CTkLabel(
            row1, font=self._font_body, text_color=self._TEXT_MUTED
        )
        self._lbl_interval_hint.pack(side="left", padx=(12, 0))
        self._set_interval_hint()
        self._a11y_label_focus_entry(self._lbl_interval, self.entry_minutes)

        self._lbl_interval_presets = ctk.CTkLabel(
            params_host,
            text=self._t("interval_presets_caption"),
            font=self._font_body,
            text_color=(self._TEXT_MUTED, self._TEXT_MUTED),
            anchor="w",
        )
        self._lbl_interval_presets.grid(row=6, column=0, sticky="w", padx=p, pady=(0, 2))
        preset_row = ctk.CTkFrame(params_host, fg_color="transparent")
        preset_row.grid(row=7, column=0, sticky="w", padx=p, pady=(0, p))
        self._interval_preset_specs = [
            "interval_preset_10s",
            "interval_preset_30s",
            "interval_preset_1m",
            "interval_preset_5m",
        ]
        self._interval_preset_btns = []
        for spec, pv in zip(
            self._interval_preset_specs,
            ("10", "30", "60", "300"),
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
                command=lambda v=pv: self._apply_interval_preset(v),
            )
            b.pack(side="left", padx=(0, 6))
            self._interval_preset_btns.append(b)

        self._lbl_interval_jitter = ctk.CTkLabel(
            params_host,
            text=self._t("interval_jitter_label"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
        )
        self._lbl_interval_jitter.grid(row=8, column=0, sticky="w", padx=p, pady=(p, p))
        row_jitter = ctk.CTkFrame(params_host, fg_color="transparent")
        row_jitter.grid(row=9, column=0, sticky="ew", padx=p, pady=(0, p))
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
            params_host,
            text=self._t("pixels_label"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
        )
        self._lbl_pixels.grid(row=10, column=0, sticky="w", padx=p, pady=(p, p))
        row3 = ctk.CTkFrame(params_host, fg_color="transparent")
        row3.grid(row=11, column=0, sticky="ew", padx=p, pady=(0, p))
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
            text=self._t("pixels_hint", lo=self.MIN_PIXELS, hi=self._pixels_cap_for_activity()),
            font=self._font_body,
            text_color=self._TEXT_MUTED,
        )
        self._lbl_pixels_hint.pack(side="left", padx=(12, 0))
        self._a11y_label_focus_entry(self._lbl_pixels, self.entry_pixels)

        self._lbl_path_speed = ctk.CTkLabel(
            params_host,
            text=self._t("path_speed_label"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
        )
        self._lbl_path_speed.grid(row=12, column=0, sticky="w", padx=p, pady=(p, p))
        row_path_speed = ctk.CTkFrame(params_host, fg_color="transparent")
        row_path_speed.grid(row=13, column=0, sticky="ew", padx=p, pady=(0, p))
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

        self._lbl_motion_duration = ctk.CTkLabel(
            params_host,
            text=self._t("motion_duration_label"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
        )
        self._lbl_motion_duration.grid(row=14, column=0, sticky="w", padx=p, pady=(p, p))
        row_motion_duration = ctk.CTkFrame(params_host, fg_color="transparent")
        row_motion_duration.grid(row=15, column=0, sticky="ew", padx=p, pady=(0, p))
        self.var_motion_duration = tk.StringVar(
            value=str(int(self.DEFAULT_MOTION_DURATION_SECONDS))
        )
        self.entry_motion_duration = ctk.CTkEntry(
            row_motion_duration,
            textvariable=self.var_motion_duration,
            width=120,
            height=40,
            corner_radius=_R,
            font=self._font_body,
            fg_color=self._ENTRY_BG,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            border_width=1,
            border_color=self._ENTRY_BORDER,
        )
        self.entry_motion_duration.pack(side="left")
        _try_takefocus(self.entry_motion_duration, 1)
        self._lbl_motion_duration_hint = ctk.CTkLabel(
            row_motion_duration,
            text=self._t(
                "motion_duration_hint",
                lo=self.MIN_MOTION_DURATION_SECONDS,
                hi=self.MAX_MOTION_DURATION_SECONDS,
            ),
            font=self._font_body,
            text_color=self._TEXT_MUTED,
        )
        self._lbl_motion_duration_hint.pack(side="left", padx=(12, 0))
        self._a11y_label_focus_entry(self._lbl_motion_duration, self.entry_motion_duration)

        self.var_natural_rare_click = tk.BooleanVar(value=False)
        self.var_natural_rare_scroll = tk.BooleanVar(value=False)

        self.row_natural_opts = ctk.CTkFrame(card, fg_color="transparent")
        self.row_natural_opts.grid(row=2, column=0, sticky="ew", padx=p, pady=(0, p))
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
        row_nat_intensity = ctk.CTkFrame(col_nat, fg_color="transparent")
        row_nat_intensity.pack(anchor="w", pady=(8, 0))
        self._lbl_natural_intensity = ctk.CTkLabel(
            row_nat_intensity,
            text=self._t("natural_intensity_label"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
        )
        self._lbl_natural_intensity.pack(side="left", padx=(0, 8))
        self.seg_natural_intensity = ctk.CTkSegmentedButton(
            row_nat_intensity,
            values=[
                self._t("natural_intensity_conservative"),
                self._t("natural_intensity_standard"),
                self._t("natural_intensity_strong"),
            ],
            command=self._on_natural_intensity_seg,
            corner_radius=10,
            font=self._font_body,
            height=32,
            fg_color=self._SURFACE_SUBTLE,
            selected_color=self._ACCENT,
            selected_hover_color=self._ACCENT_HOVER,
            unselected_color=self._BTN_SECONDARY,
            unselected_hover_color=self._BTN_SECONDARY_HOVER,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            text_color_disabled=(self._TEXT_DISABLED, self._TEXT_DISABLED),
        )
        self.seg_natural_intensity.pack(side="left")
        self._sync_natural_intensity_seg()
        self._bind_natural_intensity_tooltip_hover()
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
        self._lbl_motion_pattern.grid(row=3, column=0, sticky="w", padx=p, pady=(p, p))
        self._row_motion_pattern = ctk.CTkFrame(card, fg_color="transparent")
        self._row_motion_pattern.grid(row=4, column=0, sticky="ew", padx=p, pady=(0, p))
        self.seg_motion_pattern = ctk.CTkSegmentedButton(
            self._row_motion_pattern,
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
