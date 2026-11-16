"""Startup prompt, quick guide and the shared custom dialogs."""

from __future__ import annotations

import tkinter as tk
from typing import Literal

import customtkinter as ctk

from .ui_common import (
    _R,
)


class DialogsMixin:
    """Mixin for :class:`mouse_jiggler.app.MouseJigglerApp`; relies on its shared state."""

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

    def _dialog_layout_for_body(self, body: str) -> tuple[int, int, int]:
        lines = body.splitlines() or [body]
        line_count = max(1, len(lines))
        longest_line = max((len(line) for line in lines), default=0)
        body_len = len(body)

        width = 620 + min(260, max(0, longest_line - 60) * 3)
        height = 370 + min(220, max(0, line_count - 8) * 10) + min(90, body_len // 260 * 14)

        width = max(620, min(920, width))
        height = max(380, min(680, height))
        wraplength = max(560, width - 72)
        return width, height, wraplength

    def _fit_dialog_to_screen(
        self, dialog: ctk.CTkToplevel, width: int, height: int
    ) -> tuple[int, int]:
        try:
            screen_w = int(dialog.winfo_screenwidth())
            screen_h = int(dialog.winfo_screenheight())
        except tk.TclError:
            return width, height
        # ``width``/``height`` are CustomTkinter logical units (scaled by the window DPI
        # factor on apply), while Tk reports the screen in physical pixels once the
        # process is DPI aware before Tk starts (see win_dpi). Compare like with like.
        try:
            scale = float(dialog._get_window_scaling()) or 1.0
        except (AttributeError, TypeError, ValueError):
            scale = 1.0
        screen_w = int(screen_w / scale)
        screen_h = int(screen_h / scale)
        max_w = max(520, int(screen_w * 0.85))
        max_h = max(360, int(screen_h * 0.85))
        return min(width, max_w), min(height, max_h)

    def _show_custom_dialog(
        self,
        *,
        title: str,
        body: str,
        kind: Literal["info", "error"] = "info",
        confirm: bool = False,
    ) -> bool:
        if self._shutting_down:
            return False
        result = {"approved": False}
        try:
            width, height, wraplength = self._dialog_layout_for_body(body)
            dialog = ctk.CTkToplevel(self.root)
            dialog.title(title)
            dialog.transient(self.root)
            dialog.resizable(False, False)
            dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
            width, height = self._fit_dialog_to_screen(dialog, width, height)
            wraplength = max(420, width - 72)
            self._center_dialog(dialog, width, height)

            frame = ctk.CTkFrame(
                dialog,
                corner_radius=_R,
                fg_color=self._CARD_BG,
                border_width=1,
                border_color=self._BORDER,
            )
            frame.pack(fill="both", expand=True, padx=16, pady=(16, 24))
            frame.grid_columnconfigure(0, weight=1)

            title_color = self._STATUS_TEXT_ERROR if kind == "error" else self._TEXT_TITLE
            header = ctk.CTkLabel(
                frame,
                text=title,
                anchor="w",
                font=self._font_title,
                text_color=(title_color, title_color),
            )
            header.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))

            content = ctk.CTkLabel(
                frame,
                text=body,
                anchor="w",
                justify="left",
                wraplength=wraplength,
                font=self._font_body,
                text_color=(self._TEXT_BODY, self._TEXT_BODY),
            )
            content.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 16))

            actions = ctk.CTkFrame(frame, fg_color="transparent")
            actions.grid(row=2, column=0, sticky="", padx=16, pady=(6, 26))
            actions.grid_columnconfigure(0, weight=1)
            actions.grid_columnconfigure(1, weight=1)

            if confirm:
                btn_no = self._btn(
                    actions,
                    text=self._t("dialog_btn_no"),
                    command=dialog.destroy,
                    fg_color=self._BTN_SECONDARY,
                    hover_color=self._BTN_SECONDARY_HOVER,
                    text_color=(self._TEXT_BODY, self._TEXT_BODY),
                    border_width=2,
                    border_color=self._BORDER,
                    width=108,
                )
                btn_no.grid(row=0, column=0, padx=(0, 6), sticky="e")

                def _approve() -> None:
                    result["approved"] = True
                    dialog.destroy()

                btn_yes = self._btn(
                    actions,
                    text=self._t("dialog_btn_yes"),
                    command=_approve,
                    fg_color=self._ACCENT,
                    hover_color=self._ACCENT_HOVER,
                    text_color=(self._TEXT_ON_ACCENT, self._TEXT_ON_ACCENT),
                    width=108,
                )
                btn_yes.grid(row=0, column=1, padx=(6, 0), sticky="w")
                dialog.after(0, btn_yes.focus_set)
            else:
                btn_ok = self._btn(
                    actions,
                    text=self._t("dialog_btn_ok"),
                    command=dialog.destroy,
                    fg_color=self._ACCENT,
                    hover_color=self._ACCENT_HOVER,
                    text_color=(self._TEXT_ON_ACCENT, self._TEXT_ON_ACCENT),
                    width=108,
                )
                btn_ok.grid(row=0, column=0, columnspan=2)
                dialog.after(0, btn_ok.focus_set)

            dialog.after(0, dialog.lift)
            dialog.after(0, dialog.focus_force)
            dialog.grab_set()
            self.root.wait_window(dialog)
            return result["approved"] if confirm else True
        except tk.TclError:
            return False

    def _show_info_dialog(self, title: str, body: str) -> None:
        self._show_custom_dialog(title=title, body=body, kind="info", confirm=False)

    def _show_error_dialog(self, title: str, body: str) -> None:
        self._show_custom_dialog(title=title, body=body, kind="error", confirm=False)

    def _ask_yes_no_dialog(self, title: str, body: str) -> bool:
        return self._show_custom_dialog(title=title, body=body, kind="info", confirm=True)
