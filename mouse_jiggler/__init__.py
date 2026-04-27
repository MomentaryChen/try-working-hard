"""
Periodic mouse nudge (idle prevention) — Windows only.
GUI: CustomTkinter; mouse: ctypes; system tray: pystray + Pillow.
"""

from __future__ import annotations

import ctypes
import sys
import threading
import time
import tkinter as tk
from ctypes import wintypes
from datetime import datetime
from tkinter import messagebox
from typing import Any, Literal

import customtkinter as ctk

if sys.platform != "win32":
    print("This application supports Windows only.")
    sys.exit(1)

try:
    import pystray  # noqa: F401
except ImportError:
    HAS_TRAY = False
else:
    HAS_TRAY = True

user32 = ctypes.windll.user32

# macOS-style fonts: SF Pro Display on macOS, Segoe UI elsewhere
_FONT_FAMILY_TITLE = "SF Pro Display" if sys.platform == "darwin" else "Segoe UI"
_FONT_FAMILY_BODY = _FONT_FAMILY_TITLE

Lang = Literal["zh", "en"]

STRINGS: dict[Lang, dict[str, str]] = {
    "zh": {
        "window_title": "滑鼠定時微動",
        "app_subtitle": "滑鼠定時微動",
        "seg_control": "控制面板",
        "seg_log": "紀錄",
        "theme_hint": "深色主題 · dark-blue",
        "lang_ui": "介面語言",
        "dashboard": "主控台",
        "interval_label": "間隔（分鐘）",
        "interval_hint": "≥ 0.1，可小數",
        "pixels_label": "位移（像素）",
        "pixels_hint": "水平再還原 · {lo}–{hi}",
        "btn_start": "開始",
        "btn_stop": "停止",
        "tray_checkbox": "關閉視窗時縮到系統匣（排程繼續）",
        "tray_no_pystray": "（未安裝 pystray）",
        "status_stopped": "狀態：已停止",
        "status_running": "狀態：執行中 · 每 {m:g} 分鐘 · 下次約 {cd}",
        "log_title": "活動紀錄",
        "log_ready": "程式已就緒。",
        "log_start_fail_interval": "開始失敗：間隔設定無效。",
        "log_start_fail_pixels": "開始失敗：位移設定無效。",
        "log_started": "已開始，間隔 {m:g} 分鐘（約 {sec:.0f} 秒）、位移 {px} px。",
        "log_stopped": "已手動停止。",
        "log_nudge": "已執行游標微動。",
        "log_nudge_zero": "已觸發排程（位移 0，未移動游標）。",
        "log_nudge_fail": "微動失敗：{err}",
        "log_exit": "結束程式。",
        "log_tray_minimize": "已縮至系統匣（排程仍執行，可從圖示還原或結束）。",
        "err_title": "輸入錯誤",
        "err_minutes": "請輸入有效的分鐘數（數字，且 ≥ {min}）。",
        "err_pixels": "請輸入有效的位移像素（整數，{lo}–{hi}）。",
        "tray_show": "顯示主視窗",
        "tray_quit": "結束程式",
    },
    "en": {
        "window_title": "Mouse nudge",
        "app_subtitle": "Mouse nudge",
        "seg_control": "Control",
        "seg_log": "Log",
        "theme_hint": "Dark theme · dark-blue",
        "lang_ui": "Language",
        "dashboard": "Dashboard",
        "interval_label": "Interval (minutes)",
        "interval_hint": "≥ 0.1, decimals allowed",
        "pixels_label": "Nudge (pixels)",
        "pixels_hint": "Horizontal move & restore · {lo}–{hi}",
        "btn_start": "Start",
        "btn_stop": "Stop",
        "tray_checkbox": "Close to system tray (schedule continues)",
        "tray_no_pystray": "(pystray not installed)",
        "status_stopped": "Status: stopped",
        "status_running": "Status: running · every {m:g} min · next in {cd}",
        "log_title": "Activity log",
        "log_ready": "Ready.",
        "log_start_fail_interval": "Start failed: invalid interval.",
        "log_start_fail_pixels": "Start failed: invalid nudge size.",
        "log_started": "Started: every {m:g} min (~{sec:.0f} s), nudge {px} px.",
        "log_stopped": "Stopped manually.",
        "log_nudge": "Cursor nudge executed.",
        "log_nudge_zero": "Tick fired (0 px — cursor not moved).",
        "log_nudge_fail": "Nudge failed: {err}",
        "log_exit": "Exiting.",
        "log_tray_minimize": "Minimized to tray (schedule still running).",
        "err_title": "Invalid input",
        "err_minutes": "Enter a valid interval in minutes (number, ≥ {min}).",
        "err_pixels": "Enter a valid nudge size (integer, {lo}–{hi}).",
        "tray_show": "Show window",
        "tray_quit": "Quit",
    },
}


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
user32.GetCursorPos.restype = wintypes.BOOL
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.SetCursorPos.restype = wintypes.BOOL


def jiggle_mouse(delta_pixels: int) -> None:
    """Move cursor right by delta_pixels horizontally, then restore. If delta is 0 or less, do nothing."""
    d = int(delta_pixels)
    if d <= 0:
        return
    pt = POINT()
    if not user32.GetCursorPos(ctypes.byref(pt)):
        return
    x, y = int(pt.x), int(pt.y)
    user32.SetCursorPos(x + d, y)
    time.sleep(0.05)
    user32.SetCursorPos(x, y)


class MouseJigglerApp:
    MIN_MINUTES = 0.1
    DEFAULT_MINUTES = 5.0
    MIN_PIXELS = 0
    MAX_PIXELS = 500
    DEFAULT_PIXELS = 100
    _LOG_TRIM_LINES = 48

    # macOS-like dark layering (sidebar vs content on top of dark-blue theme)
    _SIDEBAR_BG = "#121826"
    _MAIN_BG = "#1a2233"
    _CARD_BG = "#232d42"
    _ACCENT = "#3b7dd6"
    _ACCENT_HOVER = "#5a9dee"
    _BTN_SECONDARY = "#2a3548"
    _BTN_SECONDARY_HOVER = "#3d4d66"
    _MUTED_TEXT = "#94a3b8"

    def __init__(self) -> None:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self._lang: Lang = "zh"
        self._segment_mode: Literal["control", "log"] = "control"

        # CTkFont requires an existing Tk root or tkinter raises RuntimeError
        self.root = ctk.CTk()
        self._font_title = ctk.CTkFont(family=_FONT_FAMILY_TITLE, size=24, weight="bold")
        self._font_body = ctk.CTkFont(family=_FONT_FAMILY_BODY, size=12)
        self._font_body_bold = ctk.CTkFont(family=_FONT_FAMILY_BODY, size=12, weight="bold")

        self.root.title(self._t("window_title"))
        self.root.geometry("920x640")
        self.root.minsize(860, 580)
        self.root.configure(fg_color=self._MAIN_BG)

        self._stop = threading.Event()
        self._worker: threading.Thread | None = None
        self._next_jiggle_monotonic = 0.0
        self._running_minutes = 0.0
        self._current_interval_sec = 0.0
        self._countdown_after_id: str | None = None

        self._tray_icon: Any = None
        self._tray_thread: threading.Thread | None = None
        self._shutting_down = False

        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._log(self._t("log_ready"))

    def _t(self, key: str, **kwargs: Any) -> str:
        s = STRINGS[self._lang][key]
        return s.format(**kwargs) if kwargs else s

    def _segment_text(self, mode: Literal["control", "log"]) -> str:
        return self._t("seg_control") if mode == "control" else self._t("seg_log")

    def _mode_from_segment_value(self, value: str) -> Literal["control", "log"]:
        if value == self._t("seg_control"):
            return "control"
        return "log"

    def _on_lang_switch(self, label: str) -> None:
        self._lang = "zh" if label == "繁中" else "en"
        self._apply_language()

    def _apply_language(self) -> None:
        self.root.title(self._t("window_title"))
        self._lbl_subtitle.configure(text=self._t("app_subtitle"))
        self._lbl_lang.configure(text=self._t("lang_ui"))
        self._hint.configure(text=self._t("theme_hint"))
        self._lbl_dashboard.configure(text=self._t("dashboard"))
        self._lbl_interval.configure(text=self._t("interval_label"))
        self._lbl_interval_hint.configure(text=self._t("interval_hint"))
        self._lbl_pixels.configure(text=self._t("pixels_label"))
        self._lbl_pixels_hint.configure(
            text=self._t("pixels_hint", lo=self.MIN_PIXELS, hi=self.MAX_PIXELS)
        )
        self.btn_start.configure(text=self._t("btn_start"))
        self.btn_stop.configure(text=self._t("btn_stop"))
        tray = self._t("tray_checkbox")
        if not HAS_TRAY:
            tray += self._t("tray_no_pystray")
        self.chk_tray.configure(text=tray)
        self._lbl_log_title.configure(text=self._t("log_title"))

        self._sidebar_nav_control.configure(text=f"  {self._t('seg_control')}")
        self._sidebar_nav_log.configure(text=f"  {self._t('seg_log')}")

        self.segmented.configure(values=[self._t("seg_control"), self._t("seg_log")])
        self.segmented.set(self._segment_text(self._segment_mode))
        self._sync_sidebar_highlight()

        if self._stop.is_set() or not (self._worker and self._worker.is_alive()):
            self.status.set(self._t("status_stopped"))
        else:
            self._refresh_running_status_from_countdown()

    def _refresh_running_status_from_countdown(self) -> None:
        if self._current_interval_sec <= 0:
            return
        rem = max(0.0, self._next_jiggle_monotonic - time.monotonic())
        total_sec = int(rem + 0.5)
        mm, ss = divmod(total_sec, 60)
        if mm >= 60:
            hh, mm = divmod(mm, 60)
            cd = f"{hh}:{mm:02d}:{ss:02d}"
        else:
            cd = f"{mm}:{ss:02d}"
        self.status.set(self._t("status_running", m=self._running_minutes, cd=cd))

    def _btn(self, master: Any, **kwargs: Any) -> ctk.CTkButton:
        """Rounded buttons (radius 10) with hover_color (solid hover approximates a gradient)."""
        kw = dict(corner_radius=10, font=self._font_body, height=36)
        kw.update(kwargs)
        return ctk.CTkButton(master, **kw)

    def _build_sidebar(self) -> None:
        sidebar = ctk.CTkFrame(self.root, width=220, corner_radius=0, fg_color=self._SIDEBAR_BG)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)

        brand = ctk.CTkLabel(
            sidebar,
            text="try-working-hard",
            font=self._font_title,
            text_color=("#e2e8f0", "#e2e8f0"),
            anchor="w",
        )
        brand.pack(anchor="w", padx=24, pady=(28, 4))

        self._lbl_subtitle = ctk.CTkLabel(
            sidebar,
            text=self._t("app_subtitle"),
            font=self._font_body,
            text_color=self._MUTED_TEXT,
            anchor="w",
        )
        self._lbl_subtitle.pack(anchor="w", padx=24, pady=(0, 20))

        self._sidebar_nav_control = self._btn(
            sidebar,
            text=f"  {self._t('seg_control')}",
            anchor="w",
            fg_color=self._ACCENT,
            hover_color=self._ACCENT_HOVER,
            command=lambda: self._nav_to_mode("control"),
        )
        self._sidebar_nav_control.pack(fill="x", padx=16, pady=(0, 8))

        self._sidebar_nav_log = self._btn(
            sidebar,
            text=f"  {self._t('seg_log')}",
            anchor="w",
            fg_color=self._BTN_SECONDARY,
            hover_color=self._BTN_SECONDARY_HOVER,
            command=lambda: self._nav_to_mode("log"),
        )
        self._sidebar_nav_log.pack(fill="x", padx=16, pady=(0, 16))

        self._lbl_lang = ctk.CTkLabel(
            sidebar,
            text=self._t("lang_ui"),
            font=self._font_body_bold,
            text_color=("#e2e8f0", "#e2e8f0"),
            anchor="w",
        )
        self._lbl_lang.pack(anchor="w", padx=24, pady=(0, 8))

        self._lang_seg = ctk.CTkSegmentedButton(
            sidebar,
            values=["繁中", "English"],
            command=self._on_lang_switch,
            corner_radius=10,
            font=self._font_body_bold,
            height=32,
            fg_color=self._CARD_BG,
            selected_color=self._ACCENT,
            selected_hover_color=self._ACCENT_HOVER,
            unselected_color=self._BTN_SECONDARY,
            unselected_hover_color=self._BTN_SECONDARY_HOVER,
            text_color=("#e2e8f0", "#e2e8f0"),
        )
        self._lang_seg.pack(fill="x", padx=16, pady=(0, 8))
        self._lang_seg.set("繁中")

        spacer = ctk.CTkFrame(sidebar, fg_color="transparent")
        spacer.pack(expand=True, fill="both")

        self._hint = ctk.CTkLabel(
            sidebar,
            text=self._t("theme_hint"),
            font=ctk.CTkFont(family=_FONT_FAMILY_BODY, size=11),
            text_color=self._MUTED_TEXT,
        )
        self._hint.pack(anchor="w", padx=24, pady=(0, 24))

    def _build_main(self) -> None:
        main = ctk.CTkFrame(self.root, corner_radius=0, fg_color=self._MAIN_BG)
        main.grid(row=0, column=1, sticky="nsew", padx=(0, 0), pady=0)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(2, weight=1)

        head = ctk.CTkFrame(main, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 12))
        head.grid_columnconfigure(0, weight=1)

        self._lbl_dashboard = ctk.CTkLabel(
            head,
            text=self._t("dashboard"),
            font=self._font_title,
            text_color=("#f1f5f9", "#f1f5f9"),
        )
        self._lbl_dashboard.grid(row=0, column=0, sticky="w")

        self.segmented = ctk.CTkSegmentedButton(
            head,
            values=[self._t("seg_control"), self._t("seg_log")],
            command=self._on_segment,
            corner_radius=10,
            font=self._font_body_bold,
            height=36,
            fg_color=self._CARD_BG,
            selected_color=self._ACCENT,
            selected_hover_color=self._ACCENT_HOVER,
            unselected_color=self._BTN_SECONDARY,
            unselected_hover_color=self._BTN_SECONDARY_HOVER,
            text_color=("#e2e8f0", "#e2e8f0"),
            text_color_disabled=("#64748b", "#64748b"),
        )
        self.segmented.grid(row=0, column=1, sticky="e")
        self.segmented.set(self._segment_text(self._segment_mode))

        self.progress = ctk.CTkProgressBar(
            main,
            corner_radius=10,
            height=12,
            fg_color=self._CARD_BG,
            progress_color=self._ACCENT,
        )
        self.progress.grid(row=1, column=0, sticky="ew", padx=28, pady=(0, 12))
        self.progress.set(0)

        self.content_host = ctk.CTkFrame(main, fg_color="transparent")
        self.content_host.grid(row=2, column=0, sticky="nsew", padx=28, pady=(0, 24))
        self.content_host.grid_columnconfigure(0, weight=1)
        self.content_host.grid_rowconfigure(0, weight=1)

        self.frame_control = ctk.CTkFrame(self.content_host, fg_color=self._CARD_BG, corner_radius=14)
        self.frame_control.grid(row=0, column=0, sticky="nsew")
        self._fill_control_panel(self.frame_control)

        self.frame_log = ctk.CTkFrame(self.content_host, fg_color=self._CARD_BG, corner_radius=14)
        self._fill_log_panel(self.frame_log)
        self.frame_log.grid_remove()

        self._sync_sidebar_highlight()

    def _fill_control_panel(self, card: ctk.CTkFrame) -> None:
        card.grid_columnconfigure(0, weight=1)

        pad = {"padx": 24, "pady": (16, 8)}
        self._lbl_interval = ctk.CTkLabel(
            card, text=self._t("interval_label"), font=self._font_body_bold, text_color=("#e2e8f0", "#e2e8f0")
        )
        self._lbl_interval.grid(row=0, column=0, sticky="w", **pad)
        row1 = ctk.CTkFrame(card, fg_color="transparent")
        row1.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 8))
        self.var_minutes = tk.StringVar(value=str(int(self.DEFAULT_MINUTES)))
        self.entry_minutes = ctk.CTkEntry(
            row1,
            textvariable=self.var_minutes,
            width=120,
            height=36,
            corner_radius=10,
            font=self._font_body,
            fg_color=self._MAIN_BG,
            border_color=self._BTN_SECONDARY,
        )
        self.entry_minutes.pack(side="left")
        self._lbl_interval_hint = ctk.CTkLabel(
            row1, text=self._t("interval_hint"), font=self._font_body, text_color=self._MUTED_TEXT
        )
        self._lbl_interval_hint.pack(side="left", padx=(12, 0))

        self._lbl_pixels = ctk.CTkLabel(
            card, text=self._t("pixels_label"), font=self._font_body_bold, text_color=("#e2e8f0", "#e2e8f0")
        )
        self._lbl_pixels.grid(row=2, column=0, sticky="w", padx=24, pady=(12, 8))
        row3 = ctk.CTkFrame(card, fg_color="transparent")
        row3.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 8))
        self.var_pixels = tk.StringVar(value=str(self.DEFAULT_PIXELS))
        self.entry_pixels = ctk.CTkEntry(
            row3,
            textvariable=self.var_pixels,
            width=120,
            height=36,
            corner_radius=10,
            font=self._font_body,
            fg_color=self._MAIN_BG,
            border_color=self._BTN_SECONDARY,
        )
        self.entry_pixels.pack(side="left")
        self._lbl_pixels_hint = ctk.CTkLabel(
            row3,
            text=self._t("pixels_hint", lo=self.MIN_PIXELS, hi=self.MAX_PIXELS),
            font=self._font_body,
            text_color=self._MUTED_TEXT,
        )
        self._lbl_pixels_hint.pack(side="left", padx=(12, 0))

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.grid(row=4, column=0, sticky="w", padx=24, pady=(16, 8))

        self.btn_start = self._btn(
            btn_row,
            text=self._t("btn_start"),
            width=120,
            fg_color=self._ACCENT,
            hover_color=self._ACCENT_HOVER,
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
            state="disabled",
            command=self._on_stop,
        )
        self.btn_stop.pack(side="left")

        tray = self._t("tray_checkbox")
        if not HAS_TRAY:
            tray += self._t("tray_no_pystray")
        self.var_tray_close = tk.BooleanVar(value=False)
        self.chk_tray = ctk.CTkCheckBox(
            card,
            text=tray,
            variable=self.var_tray_close,
            font=self._font_body,
            text_color=("#e2e8f0", "#e2e8f0"),
            fg_color=self._ACCENT,
            hover_color=self._ACCENT_HOVER,
            border_width=1,
            corner_radius=6,
        )
        self.chk_tray.grid(row=5, column=0, sticky="w", padx=24, pady=(16, 8))
        if not HAS_TRAY:
            self.chk_tray.configure(state="disabled")

        self.status = tk.StringVar(value=self._t("status_stopped"))
        ctk.CTkLabel(
            card,
            textvariable=self.status,
            font=self._font_body,
            text_color=self._MUTED_TEXT,
            anchor="w",
        ).grid(row=6, column=0, sticky="ew", padx=24, pady=(8, 20))

    def _fill_log_panel(self, card: ctk.CTkFrame) -> None:
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)

        self._lbl_log_title = ctk.CTkLabel(
            card,
            text=self._t("log_title"),
            font=self._font_body_bold,
            text_color=("#e2e8f0", "#e2e8f0"),
        )
        self._lbl_log_title.grid(row=0, column=0, sticky="w", padx=24, pady=(20, 8))

        self.log_text = ctk.CTkTextbox(
            card,
            corner_radius=10,
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color=self._MAIN_BG,
            text_color=("#cbd5e1", "#cbd5e1"),
            border_width=1,
            border_color=self._BTN_SECONDARY,
        )
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 20))
        self.log_text.configure(state="disabled")

    def _on_segment(self, value: str) -> None:
        self._segment_mode = self._mode_from_segment_value(value)
        self._apply_view()
        self._sync_sidebar_highlight()

    def _nav_to_mode(self, mode: Literal["control", "log"]) -> None:
        self._segment_mode = mode
        self.segmented.set(self._segment_text(mode))
        self._apply_view()
        self._sync_sidebar_highlight()

    def _apply_view(self) -> None:
        if self._segment_mode == "control":
            self.frame_control.grid(row=0, column=0, sticky="nsew")
            self.frame_log.grid_remove()
        else:
            self.frame_log.grid(row=0, column=0, sticky="nsew")
            self.frame_control.grid_remove()

    def _sync_sidebar_highlight(self) -> None:
        if self._segment_mode == "control":
            self._sidebar_nav_control.configure(fg_color=self._ACCENT, hover_color=self._ACCENT_HOVER)
            self._sidebar_nav_log.configure(fg_color=self._BTN_SECONDARY, hover_color=self._BTN_SECONDARY_HOVER)
        else:
            self._sidebar_nav_control.configure(fg_color=self._BTN_SECONDARY, hover_color=self._BTN_SECONDARY_HOVER)
            self._sidebar_nav_log.configure(fg_color=self._ACCENT, hover_color=self._ACCENT_HOVER)

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
            self.progress.set(0)
            return

        rem = max(0.0, self._next_jiggle_monotonic - time.monotonic())
        if self._current_interval_sec > 0:
            prog = 1.0 - (rem / self._current_interval_sec)
            self.progress.set(max(0.0, min(1.0, prog)))
        total_sec = int(rem + 0.5)
        mm, ss = divmod(total_sec, 60)
        if mm >= 60:
            hh, mm = divmod(mm, 60)
            countdown_str = f"{hh}:{mm:02d}:{ss:02d}"
        else:
            countdown_str = f"{mm}:{ss:02d}"

        m = self._running_minutes
        self.status.set(self._t("status_running", m=m, cd=countdown_str))
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
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line)
        try:
            idx = self.log_text.index("end-1c")
            total = int(str(idx).split(".")[0])
        except (tk.TclError, ValueError, AttributeError):
            body = self.log_text.get("0.0", "end-1c")
            total = len(body.splitlines()) if body else 0
        excess = total - self._LOG_TRIM_LINES
        if excess > 0:
            self.log_text.delete("1.0", f"{excess + 1}.0")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _parse_minutes(self) -> float | None:
        raw = self.var_minutes.get().strip().replace(",", ".")
        try:
            m = float(raw)
        except ValueError:
            return None
        if m < self.MIN_MINUTES:
            return None
        return m

    def _parse_pixels(self) -> int | None:
        raw = self.var_pixels.get().strip().replace(",", ".")
        try:
            p = int(float(raw))
        except ValueError:
            return None
        if p < self.MIN_PIXELS or p > self.MAX_PIXELS:
            return None
        return p

    def _on_start(self) -> None:
        minutes = self._parse_minutes()
        if minutes is None:
            messagebox.showerror(
                self._t("err_title"),
                self._t("err_minutes", min=self.MIN_MINUTES),
                parent=self.root,
            )
            self._log(self._t("log_start_fail_interval"))
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
        if self._worker is not None and self._worker.is_alive():
            return

        self._stop.clear()
        interval_sec = minutes * 60.0
        self._running_minutes = minutes
        self._current_interval_sec = interval_sec
        self._next_jiggle_monotonic = time.monotonic() + interval_sec

        self._worker = threading.Thread(
            target=self._run_loop,
            args=(interval_sec, pixels),
            daemon=True,
        )
        self._worker.start()

        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.entry_minutes.configure(state="disabled")
        self.entry_pixels.configure(state="disabled")
        self.status.set(self._t("status_running", m=minutes, cd="—"))
        self.progress.set(0)
        self._schedule_countdown_tick()
        self._log(self._t("log_started", m=minutes, sec=interval_sec, px=pixels))

    def _on_stop(self) -> None:
        self._stop.set()
        self._cancel_countdown_tick()
        self.progress.set(0)
        self._current_interval_sec = 0.0
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.entry_minutes.configure(state="normal")
        self.entry_pixels.configure(state="normal")
        self.status.set(self._t("status_stopped"))
        self._log(self._t("log_stopped"))

    def _run_loop(self, interval_sec: float, pixels: int) -> None:
        while not self._stop.is_set():
            self._next_jiggle_monotonic = time.monotonic() + interval_sec
            if self._stop.wait(timeout=interval_sec):
                break
            try:
                jiggle_mouse(pixels)
                if pixels > 0:
                    self._log(self._t("log_nudge"))
                else:
                    self._log(self._t("log_nudge_zero"))
            except OSError as e:
                self._log(self._t("log_nudge_fail", err=e))

    def _build_tray_image(self) -> Any:
        from PIL import Image, ImageDraw

        w, h = 64, 64
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse((6, 6, w - 6, h - 6), fill=(59, 125, 214, 255))
        return img

    def _tray_on_show(self, icon: Any, item: Any) -> None:
        self.root.after(0, self._show_from_tray)

    def _tray_on_quit(self, icon: Any, item: Any) -> None:
        self.root.after(0, self._quit_from_tray)

    def _tray_run(self) -> None:
        import pystray

        image = self._build_tray_image()
        menu = pystray.Menu(
            pystray.MenuItem(self._t("tray_show"), self._tray_on_show, default=True),
            pystray.MenuItem(self._t("tray_quit"), self._tray_on_quit),
        )
        icon = pystray.Icon("try-working-hard", image, self._t("window_title"), menu)
        self._tray_icon = icon
        try:
            icon.run()
        finally:
            self._tray_icon = None

    def _start_tray(self) -> None:
        if not HAS_TRAY:
            return
        if self._tray_thread is not None and self._tray_thread.is_alive():
            return
        self._tray_thread = threading.Thread(target=self._tray_run, daemon=True)
        self._tray_thread.start()

    def _stop_tray(self) -> None:
        icon = self._tray_icon
        if icon is not None:
            try:
                icon.stop()
            except Exception:
                pass
        self._tray_icon = None

    def _full_shutdown(self) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True

        self._stop.set()
        self._cancel_countdown_tick()

        w = self._worker
        if w is not None and w.is_alive():
            w.join(timeout=3.0)

        self._stop_tray()
        t = self._tray_thread
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
    MouseJigglerApp().run()
