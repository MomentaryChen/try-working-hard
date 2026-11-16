"""Update checks, update banner and installer download."""

from __future__ import annotations

import os
import threading
import time
import tkinter as tk
import webbrowser
from pathlib import Path

import customtkinter as ctk

from . import (
    local_config,
    updater,
)
from .ui_common import (
    _R,
)


class UpdatesMixin:
    """Mixin for :class:`mouse_jiggler.app.MouseJigglerApp`; relies on its shared state."""

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
        approved = self._ask_yes_no_dialog(title, body)
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
        if not checksum_url:
            # Never download (let alone run) an installer that cannot be verified.
            self._show_checksum_error(updater.ChecksumError("missing_asset"))
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
                try:
                    digest = updater.verify_installer_checksum(
                        out, installer_name=installer_name, checksum_url=checksum_url
                    )
                except updater.ChecksumError as exc:
                    updater.discard_file(out)
                    checksum_err = exc
                    self.root.after(0, lambda: self._on_installer_checksum_failed(checksum_err))
                    return
                except Exception:
                    # Fail closed: never leave an unverified installer behind.
                    updater.discard_file(out)
                    raise
                self.root.after(
                    0,
                    lambda: self._on_installer_download_done(path=out, checksum_digest=digest),
                )
            except updater.DownloadCancelledError:
                self.root.after(0, self._on_installer_download_cancelled)
            except Exception as exc:
                # Bind the message now: Python unbinds ``exc`` when the except block ends,
                # long before Tk runs this callback on the main thread.
                err = str(exc)
                self.root.after(0, lambda: self._on_installer_download_failed(err=err))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_installer_download_done(
        self,
        *,
        path: Path,
        checksum_digest: str,
    ) -> None:
        self._update_download_in_progress = False
        self._close_installer_progress_dialog()
        if self._shutting_down:
            return
        digest_hint = self._t(
            "update_checksum_verified_hint",
            digest=self._short_digest(checksum_digest),
        )
        approved = self._ask_yes_no_dialog(
            self._t("update_install_prompt_title"),
            self._t("update_install_prompt_body", path=str(path), verify_hint=digest_hint),
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
            self._show_error_dialog(
                self._t("update_install_prompt_title"),
                self._t("update_install_failed", err=str(exc)),
            )

    def _on_installer_download_failed(self, *, err: str) -> None:
        self._update_download_in_progress = False
        self._close_installer_progress_dialog()
        if self._shutting_down:
            return
        self._show_error_dialog(
            self._t("update_download_failed_title"),
            self._t("update_download_failed_body", err=err),
        )

    def _on_installer_checksum_failed(self, exc: updater.ChecksumError) -> None:
        self._update_download_in_progress = False
        self._close_installer_progress_dialog()
        if self._shutting_down:
            return
        self._show_checksum_error(exc)

    def _show_checksum_error(self, exc: updater.ChecksumError) -> None:
        if exc.reason == "mismatch":
            detail = self._t(
                "update_checksum_mismatch_error",
                expected=self._short_digest(exc.expected),
                actual=self._short_digest(exc.actual),
            )
        else:
            detail = self._t(f"update_checksum_{exc.reason}_error")
        self._show_error_dialog(
            self._t("update_checksum_failed_title"),
            self._t("update_checksum_failed_body", detail=detail),
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
