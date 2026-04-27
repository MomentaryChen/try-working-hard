"""
定時輕微移動滑鼠（避免閒置）— Windows 專用，僅使用 Python 標準庫 + ctypes。
"""

from __future__ import annotations

import ctypes
import sys
import threading
import time
import tkinter as tk
from ctypes import wintypes
from datetime import datetime
from tkinter import messagebox, ttk

if sys.platform != "win32":
    print("此程式僅支援 Windows。")
    sys.exit(1)

user32 = ctypes.windll.user32


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
user32.GetCursorPos.restype = wintypes.BOOL
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.SetCursorPos.restype = wintypes.BOOL


def jiggle_mouse() -> None:
    pt = POINT()
    if not user32.GetCursorPos(ctypes.byref(pt)):
        return
    x, y = int(pt.x), int(pt.y)
    user32.SetCursorPos(x + 1, y)
    time.sleep(0.05)
    user32.SetCursorPos(x, y)


class MouseJigglerApp:
    MIN_MINUTES = 0.1
    DEFAULT_MINUTES = 5.0
    _LOG_TRIM_LINES = 48
    _LOG_HEIGHT = 4

    # 版面配色（淺色、對比清楚）
    _BG = "#e8edf3"
    _CARD = "#ffffff"
    _TEXT = "#1e293b"
    _MUTED = "#64748b"
    _BORDER = "#cbd5e1"
    _ACCENT = "#4f46e5"
    _ACCENT_HOVER = "#6366f1"
    _ACCENT_DISABLED = "#a5b4fc"
    _LOG_BG = "#f1f5f9"
    _LOG_FG = "#334155"

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("滑鼠定時微動")
        self.root.resizable(False, False)
        self.root.configure(bg=self._BG)

        self._stop = threading.Event()
        self._worker: threading.Thread | None = None

        self._setup_style()

        outer = ttk.Frame(self.root, padding=(18, 14), style="App.TFrame")
        outer.grid(row=0, column=0, sticky="nsew")

        title = ttk.Label(outer, text="滑鼠定時微動", style="Title.TLabel")
        title.grid(row=0, column=0, sticky="w")
        sub = ttk.Label(
            outer,
            text="依間隔輕微移動游標後還原 · 關閉視窗即停止",
            style="Sub.TLabel",
        )
        sub.grid(row=1, column=0, sticky="w", pady=(2, 12))

        card = ttk.Frame(outer, padding=(14, 12), style="Card.TFrame")
        card.grid(row=2, column=0, sticky="ew")
        card.columnconfigure(1, weight=1)

        ttk.Label(card, text="間隔（分鐘）", style="Card.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 2)
        )
        interval_wrap = ttk.Frame(card, style="Card.TFrame")
        interval_wrap.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        self.var_minutes = tk.StringVar(value=str(int(self.DEFAULT_MINUTES)))
        self.entry_minutes = ttk.Entry(interval_wrap, textvariable=self.var_minutes, width=10, style="App.TEntry")
        self.entry_minutes.pack(side=tk.LEFT)
        ttk.Label(interval_wrap, text="≥ 0.1，可小數", style="Hint.TLabel").pack(side=tk.LEFT, padx=(8, 0))

        btn_row = ttk.Frame(card, style="Card.TFrame")
        btn_row.grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))

        self.btn_start = ttk.Button(btn_row, text="開始", style="Accent.TButton", command=self._on_start, width=10)
        self.btn_start.pack(side=tk.LEFT, padx=(0, 8))
        self.btn_stop = ttk.Button(
            btn_row, text="停止", style="Ghost.TButton", command=self._on_stop, state=tk.DISABLED, width=10
        )
        self.btn_stop.pack(side=tk.LEFT)

        self.status = tk.StringVar(value="狀態：已停止")
        ttk.Label(card, textvariable=self.status, style="Status.TLabel").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(12, 0)
        )

        log_wrap = ttk.LabelFrame(outer, text=" 紀錄 ", padding=(8, 6), style="Log.TLabelframe")
        log_wrap.grid(row=3, column=0, sticky="ew", pady=(14, 0))

        self.log_text = tk.Text(
            log_wrap,
            height=self._LOG_HEIGHT,
            width=46,
            font=("Consolas", 9),
            bg=self._LOG_BG,
            fg=self._LOG_FG,
            insertbackground=self._LOG_FG,
            relief="flat",
            padx=8,
            pady=6,
            wrap=tk.WORD,
            state=tk.DISABLED,
            highlightthickness=1,
            highlightbackground=self._BORDER,
            highlightcolor=self._BORDER,
        )
        self.log_text.grid(row=0, column=0, sticky="ew")

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._log("程式已就緒。")

    def _setup_style(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("App.TFrame", background=self._BG)
        style.configure("Card.TFrame", background=self._CARD)
        style.configure(
            "Title.TLabel",
            background=self._BG,
            foreground=self._TEXT,
            font=("Segoe UI", 15, "bold"),
        )
        style.configure("Sub.TLabel", background=self._BG, foreground=self._MUTED, font=("Segoe UI", 9))
        style.configure("Card.TLabel", background=self._CARD, foreground=self._TEXT, font=("Segoe UI", 10))
        style.configure("Hint.TLabel", background=self._CARD, foreground=self._MUTED, font=("Segoe UI", 9))
        style.configure("Status.TLabel", background=self._CARD, foreground=self._MUTED, font=("Segoe UI", 9))

        style.configure("App.TEntry", fieldbackground="#f8fafc", foreground=self._TEXT, padding=(8, 6))

        style.configure(
            "Accent.TButton",
            font=("Segoe UI", 9, "bold"),
            padding=(10, 8),
            background=self._ACCENT,
            foreground="#ffffff",
            borderwidth=0,
            focuscolor=self._ACCENT,
        )
        style.map(
            "Accent.TButton",
            background=[
                ("active", self._ACCENT_HOVER),
                ("pressed", self._ACCENT),
                ("disabled", self._ACCENT_DISABLED),
            ],
            foreground=[("disabled", "#f1f5f9")],
        )

        style.configure(
            "Ghost.TButton",
            font=("Segoe UI", 9),
            padding=(10, 8),
            background=self._CARD,
            foreground=self._TEXT,
            borderwidth=1,
        )
        style.map(
            "Ghost.TButton",
            background=[("active", "#f1f5f9"), ("disabled", "#f1f5f9")],
            foreground=[("disabled", "#94a3b8")],
        )

        style.configure(
            "Log.TLabelframe",
            background=self._BG,
            foreground=self._MUTED,
            bordercolor=self._BORDER,
            font=("Segoe UI", 9),
        )
        style.configure("Log.TLabelframe.Label", background=self._BG, foreground=self._MUTED, font=("Segoe UI", 9))

    def _log(self, message: str) -> None:
        """執行緒安全：從任何執行緒呼叫，會排程到主執行緒寫入。"""
        self.root.after(0, lambda m=message: self._log_ui(m))

    def _log_ui(self, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {message}\n"
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, line)
        total = int(self.log_text.index("end-1c").split(".")[0])
        excess = total - self._LOG_TRIM_LINES
        if excess > 0:
            self.log_text.delete("1.0", f"{excess + 1}.0")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _parse_minutes(self) -> float | None:
        raw = self.var_minutes.get().strip().replace(",", ".")
        try:
            m = float(raw)
        except ValueError:
            return None
        if m < self.MIN_MINUTES:
            return None
        return m

    def _on_start(self) -> None:
        minutes = self._parse_minutes()
        if minutes is None:
            messagebox.showerror(
                "輸入錯誤",
                f"請輸入有效的分鐘數（數字，且 ≥ {self.MIN_MINUTES}）。",
                parent=self.root,
            )
            self._log("開始失敗：間隔設定無效。")
            return
        if self._worker is not None and self._worker.is_alive():
            return

        self._stop.clear()
        interval_sec = minutes * 60.0
        self._worker = threading.Thread(
            target=self._run_loop,
            args=(interval_sec, minutes),
            daemon=True,
        )
        self._worker.start()

        self.btn_start.configure(state=tk.DISABLED)
        self.btn_stop.configure(state=tk.NORMAL)
        self.entry_minutes.configure(state=tk.DISABLED)
        self.status.set(f"狀態：執行中 · 每 {minutes:g} 分鐘微動")
        self._log(f"已開始，間隔 {minutes:g} 分鐘（約 {interval_sec:.0f} 秒）。")

    def _on_stop(self) -> None:
        self._stop.set()
        self.btn_start.configure(state=tk.NORMAL)
        self.btn_stop.configure(state=tk.DISABLED)
        self.entry_minutes.configure(state=tk.NORMAL)
        self.status.set("狀態：已停止")
        self._log("已手動停止。")

    def _run_loop(self, interval_sec: float, minutes: float) -> None:
        while not self._stop.wait(timeout=interval_sec):
            if self._stop.is_set():
                break
            try:
                jiggle_mouse()
                self._log("已執行游標微動。")
            except OSError as e:
                self._log(f"微動失敗：{e}")

    def _on_close(self) -> None:
        self._stop.set()
        try:
            self._log_ui("結束程式。")
        except tk.TclError:
            pass
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    MouseJigglerApp().run()
