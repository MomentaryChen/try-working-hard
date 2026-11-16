"""Keyboard shortcuts and focus helpers (F1-F6, Enter/Esc)."""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk


class A11yMixin:
    """Mixin for :class:`mouse_jiggler.app.MouseJigglerApp`; relies on its shared state."""

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
        self._show_info_dialog(
            self._t("a11y_help_title"),
            self._t("a11y_help_body", version=self._pkg_version()),
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
            st = str(self.btn_run_toggle.cget("state")).lower()
        except (tk.TclError, AttributeError):
            return
        if st == "disabled" or (st.isdigit() and st == "0"):
            return
        if self._worker is not None and self._worker.is_alive() and not self._stop.is_set():
            return
        self._on_start()

    def _a11y_try_stop(self) -> None:
        if self._active_nav != "home" or self._segment_mode != "control":
            return
        try:
            st = str(self.btn_run_toggle.cget("state")).lower()
        except (tk.TclError, AttributeError):
            return
        if st == "disabled" or (st.isdigit() and st == "0"):
            return
        if self._worker is None or not self._worker.is_alive() or self._stop.is_set():
            return
        self._on_stop()
