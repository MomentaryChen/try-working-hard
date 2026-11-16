"""Analytics page (built lazily) and runtime accounting."""

from __future__ import annotations

import time
import tkinter as tk
from datetime import date
from typing import TYPE_CHECKING

import customtkinter as ctk

# analytics_charts pulls in matplotlib (~1.5 s of import time). It is imported lazily
# the first time the Analytics page is opened; see _build_analytics_page_deferred.
if TYPE_CHECKING:
    from . import analytics_charts

from . import (
    analytics_store,
)
from .ui_common import (
    _LOG,
    _R,
    _try_takefocus,
)


class AnalyticsMixin:
    """Mixin for :class:`mouse_jiggler.app.MouseJigglerApp`; relies on its shared state."""

    def _schedule_analytics_page_build(self) -> None:
        """Show a placeholder, then build the chart panel after the UI has repainted."""
        if self._analytics_build_pending:
            return
        self._analytics_build_pending = True
        self._analytics_loading_key = "analytics_loading"
        if self._lbl_analytics_loading is None:
            self._lbl_analytics_loading = ctk.CTkLabel(
                self.page_analytics,
                text=self._t("analytics_loading"),
                font=self._font_body,
                text_color=self._TEXT_MUTED,
            )
            self._lbl_analytics_loading.grid(row=1, column=0, sticky="n", pady=(self._UI_PAD * 2, 0))
        else:
            # Retrying after an earlier failure.
            self._lbl_analytics_loading.configure(text=self._t("analytics_loading"))
        # A short delay lets Tk paint the page and placeholder before the blocking import.
        self.root.after(30, self._build_analytics_page_deferred)

    def _build_analytics_page_deferred(self) -> None:
        self._analytics_build_pending = False
        if self._analytics_built or self._shutting_down:
            return
        try:
            self._fill_analytics_panel(self.page_analytics)
        except (ImportError, OSError, RuntimeError, ValueError, tk.TclError):
            _LOG.exception("Failed to build the Analytics page")
            self._discard_partial_analytics_panel()
            self._analytics_loading_key = "analytics_load_failed"
            if self._lbl_analytics_loading is not None:
                self._lbl_analytics_loading.configure(text=self._t(self._analytics_loading_key))
            return
        self._analytics_built = True
        if self._lbl_analytics_loading is not None:
            self._lbl_analytics_loading.destroy()
            self._lbl_analytics_loading = None
        self._sync_analytics_log_from_main()

    # Attributes created by _fill_analytics_panel; other code feature-tests them with hasattr.
    _ANALYTICS_PANEL_ATTRS = (
        "analytics_scroll",
        "_lbl_analytics_sub",
        "_lbl_chart_triggers",
        "_lbl_chart_runtime",
        "_lbl_chart_patterns",
        "_seg_analytics_range",
        "_fig_trigger",
        "_mpl_canvas_trigger",
        "_fig_runtime",
        "_mpl_canvas_runtime",
        "_fig_patterns",
        "_mpl_canvas_patterns",
        "analytics_log",
    )

    def _discard_partial_analytics_panel(self) -> None:
        """Undo a failed build so a later visit can retry cleanly."""
        scroll = getattr(self, "analytics_scroll", None)
        if scroll is not None:
            try:
                scroll.destroy()
            except tk.TclError:
                pass
        for name in self._ANALYTICS_PANEL_ATTRS:
            if name in self.__dict__:
                delattr(self, name)

    def _fill_analytics_panel(self, card: ctk.CTkFrame) -> None:
        from matplotlib.figure import Figure

        from . import analytics_charts

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
        from . import analytics_charts

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
        today_key = date.today().isoformat()
        # Skip re-reading JSON and redrawing all three figures when neither the data
        # nor anything that affects rendering has changed since the last draw.
        signature = (
            analytics_store.data_signature(),
            today_key,
            self._analytics_trigger_mode,
            self._lang,
            self._ui_theme,
        )
        if signature == getattr(self, "_analytics_chart_signature", None):
            return
        from . import analytics_charts

        self._analytics_chart_signature = None
        try:
            days_map = analytics_store.load_days_copy()
        except OSError:
            days_map = {}
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
        self._analytics_chart_signature = signature

    def _tick_analytics_charts_loop(self) -> None:
        if self._shutting_down:
            return
        if self._active_nav == "analytics" and self._is_main_window_visible():
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
