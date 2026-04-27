"""CustomTkinter UI and scheduling for the mouse nudge app."""

from __future__ import annotations

import os
import threading
import time
import tkinter as tk
from datetime import datetime
from importlib.metadata import version as pkg_version
from importlib.resources import files
from pathlib import Path
from tkinter import messagebox
from typing import Any, Literal

import customtkinter as ctk

from . import local_config, nudge_logic
from .app_icon import load_app_icon_rgba
from .strings import Lang, STRINGS
from .tray import HAS_TRAY, TrayController
from .win32_mouse import jiggle_mouse

# Primary UI font (Inter). If missing, Tk picks a substitute.
_FONT_INTER = "Inter"


def _try_takefocus(widget: Any, value: int | bool) -> None:
    """Set takefocus on CTk/Tk widgets; ignore if unsupported (keyboard / screen-reader support)."""
    # CTkButton: takefocus is not a valid **kwargs to CTkBaseClass / configure (CustomTkinter 5.x).
    if isinstance(widget, ctk.CTkButton):
        return
    try:
        widget.configure(takefocus=value)  # type: ignore[union-attr]
    except (tk.TclError, AttributeError, TypeError, ValueError):
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


class MouseJigglerApp:
    MIN_MINUTES = nudge_logic.MIN_MINUTES
    DEFAULT_MINUTES = nudge_logic.DEFAULT_MINUTES
    MIN_PIXELS = nudge_logic.MIN_PIXELS
    MAX_PIXELS = nudge_logic.MAX_PIXELS
    DEFAULT_PIXELS = nudge_logic.DEFAULT_PIXELS
    MIN_MOTION_BURST = nudge_logic.MIN_MOTION_BURST_SEC
    MAX_MOTION_BURST = nudge_logic.MAX_MOTION_BURST_SEC
    DEFAULT_MOTION_BURST = nudge_logic.DEFAULT_MOTION_BURST_SEC
    _LOG_TRIM_LINES = nudge_logic.LOG_TRIM_LINES

    # Deep gray palette; accent = soft purple (Discord-like)
    _MAIN_BG = "#1A1A1B"
    _SIDEBAR_BG = "#141415"
    _CARD_BG = "#2D2D2E"
    _ENTRY_BG = "#252526"
    _ACCENT = "#7289DA"
    _ACCENT_HOVER = "#8EA0E8"
    _BTN_SECONDARY = "#3F3F40"
    _BTN_SECONDARY_HOVER = "#4A4A4B"
    _BORDER = "#3F3F40"
    _TEXT_TITLE = "#F5F5F5"
    _TEXT_BODY = "#D1D1D1"
    _TEXT_MUTED = "#8A8A8B"
    _TEXT_DISABLED = "#6B6B6C"
    _TEXT_LOG = "#C8C8C8"
    _NAV_HOVER = "#3F3F40"
    _NAV_SELECTED = "#7289DA"
    _SIDEBAR_WIDTH = 200
    _UI_PAD = 20

    def __init__(self) -> None:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self._lang: Lang = "en"
        self._segment_mode: Literal["control", "log"] = "control"
        self._active_nav: Literal["home", "settings", "analytics"] = "home"

        # CTkFont requires an existing Tk root or tkinter raises RuntimeError
        self.root = ctk.CTk()
        self._font_title = ctk.CTkFont(family=_FONT_INTER, size=24, weight="bold")
        self._font_body = ctk.CTkFont(family=_FONT_INTER, size=13)
        self._font_body_bold = ctk.CTkFont(family=_FONT_INTER, size=13, weight="bold")
        self._font_hint = ctk.CTkFont(family=_FONT_INTER, size=12)
        self._font_mono = ctk.CTkFont(family="Consolas", size=13)

        self.root.title(self._t("window_title"))
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
        self._running_motion_burst_sec = 0.0
        self._countdown_after_id: str | None = None
        self._countdown_phase: Literal["interval", "burst"] = "interval"
        self.status = tk.StringVar(value=self._t("status_stopped"))

        self._tray = TrayController()
        self._shutting_down = False
        self._config_save_after_id: str | None = None
        self._config_loading = False
        self._intro_acknowledged = True

        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._config_loading = True
        try:
            self._apply_loaded_config(local_config.load_config())
        finally:
            self._config_loading = False
        self._register_config_persistence()

        self._log(self._t("log_ready"))
        self._setup_a11y()
        self.root.after(250, self._maybe_show_first_intro)

    def _pkg_version(self) -> str:
        try:
            return pkg_version("try-working-hard")
        except Exception:
            return "1.0.0"

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
        self.var_pixels.set(str(cfg.get("pixels_text", str(self.DEFAULT_PIXELS))))
        self.var_motion_burst.set(
            str(cfg.get("motion_burst_text", str(int(self.DEFAULT_MOTION_BURST))))
        )
        self.var_tray_close.set(bool(cfg.get("close_to_tray", False)))
        self._intro_acknowledged = bool(cfg.get("intro_acknowledged", True))
        self._lang_seg.set("繁中" if self._lang == "zh" else "English")
        self._apply_language()

    def _config_snapshot(self) -> dict[str, Any]:
        return {
            "lang": self._lang,
            "interval_text": self.var_minutes.get(),
            "interval_unit": self._interval_unit,
            "pixels_text": self.var_pixels.get(),
            "motion_burst_text": self.var_motion_burst.get(),
            "close_to_tray": bool(self.var_tray_close.get()),
            "intro_acknowledged": self._intro_acknowledged,
        }

    def _maybe_show_first_intro(self) -> None:
        if self._shutting_down:
            return
        if self._intro_acknowledged:
            return
        try:
            if not self.root.winfo_exists():
                return
        except tk.TclError:
            return
        messagebox.showinfo(
            self._t("intro_title"),
            self._t("intro_body", version=self._pkg_version()),
            parent=self.root,
        )
        self._intro_acknowledged = True
        self._save_config_now()

    def _register_config_persistence(self) -> None:
        def _on_write(*_a: object) -> None:
            self._schedule_save_config()

        try:
            self.var_tray_close.trace_add("write", _on_write)
            self.var_minutes.trace_add("write", _on_write)
            self.var_pixels.trace_add("write", _on_write)
            self.var_motion_burst.trace_add("write", _on_write)
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

    def _apply_language(self) -> None:
        self.root.title(self._t("window_title"))
        self._lbl_subtitle.configure(text=self._t("app_subtitle"))
        self._lbl_lang.configure(text=self._t("lang_ui"))
        self._hint.configure(text=self._t("theme_hint"))
        self._hint_settings.configure(text=self._t("theme_hint"))
        self._lbl_dashboard.configure(text=self._t("dashboard"))
        self._lbl_interval.configure(text=self._t("interval_label"))
        if hasattr(self, "seg_interval_unit"):
            self._sync_interval_unit_seg()
        self._set_interval_hint()
        self._lbl_pixels.configure(text=self._t("pixels_label"))
        self._lbl_pixels_hint.configure(
            text=self._t("pixels_hint", lo=self.MIN_PIXELS, hi=self.MAX_PIXELS)
        )
        self._lbl_motion_burst.configure(text=self._t("motion_burst_label"))
        self._lbl_motion_burst_hint.configure(
            text=self._t("motion_burst_hint", hi=self.MAX_MOTION_BURST)
        )
        self.btn_start.configure(text=self._t("btn_start"))
        self.btn_stop.configure(text=self._t("btn_stop"))
        self._lbl_tray_sw.configure(text=self._t("tray_switch_title"))
        tray_hint = self._t("tray_switch_hint")
        if not HAS_TRAY:
            tray_hint += self._t("tray_no_pystray")
        self._hint_tray.configure(text=tray_hint)
        self._lbl_log_title.configure(text=self._t("log_title"))
        self._lbl_settings_title.configure(text=self._t("settings_title"))
        if hasattr(self, "btn_open_config"):
            self.btn_open_config.configure(text=self._t("btn_open_config_file"))
        self._lbl_analytics_title.configure(text=self._t("analytics_title"))
        self._lbl_analytics_sub.configure(text=self._t("analytics_subtitle"))

        self._nav_home.configure(text=f"  {self._t('nav_home')}")
        self._nav_settings.configure(text=f"  {self._t('nav_settings')}")
        self._nav_analytics.configure(text=f"  {self._t('nav_analytics')}")

        self.segmented.configure(values=[self._t("seg_control"), self._t("seg_log")])
        self.segmented.set(self._segment_text(self._segment_mode))
        self.view_segmented.configure(
            values=[self._t("nav_home"), self._t("nav_settings"), self._t("nav_analytics")]
        )
        self._sync_view_segment()
        self._sync_nav_highlight()

        if self._stop.is_set() or not (self._worker and self._worker.is_alive()):
            self.status.set(self._t("status_stopped"))
        else:
            self._refresh_running_status_from_countdown()

    def _refresh_running_status_from_countdown(self) -> None:
        if self._current_interval_sec <= 0:
            return
        rem = self._next_jiggle_monotonic - time.monotonic()
        cd = nudge_logic.remaining_seconds_to_countdown_display(rem)
        if self._countdown_phase == "burst":
            self.status.set(self._t("status_motion_burst", cd=cd))
        else:
            self.status.set(self._t_status_running(cd))

    def _btn(self, master: Any, **kwargs: Any) -> ctk.CTkButton:
        """Rounded buttons (radius 10) with hover_color (solid hover approximates a gradient)."""
        kw = dict(corner_radius=10, font=self._font_body, height=36)
        kw.update(kwargs)
        kw.pop("takefocus", None)  # CTkButton rejects this in **kwargs
        w = ctk.CTkButton(master, **kw)
        return w

    def _build_nav_icons(self) -> dict[str, ctk.CTkImage]:
        """PNG icons in ``assets/icons`` (Lucide-style line art); Pillow tints to theme."""
        specs: list[tuple[str, str]] = [
            ("home", "house"),
            ("settings", "settings"),
            ("analytics", "chart-column"),
        ]
        out: dict[str, ctk.CTkImage] = {}
        for key, stem in specs:
            im = _load_pkg_nav_png(stem)
            if im is not None:
                im = _tint_rgba_image(im, self._TEXT_BODY)
                out[key] = ctk.CTkImage(light_image=im, dark_image=im, size=(20, 20))
            else:
                out[key] = self._nav_icon_fallback(key)
        return out

    def _nav_icon_fallback(self, key: str) -> ctk.CTkImage:
        from PIL import Image, ImageDraw

        ic_body = self._TEXT_BODY
        ic_muted = self._TEXT_MUTED

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
            corner_radius=10,
            height=40,
            font=self._font_body,
            fg_color="transparent",
            hover_color=self._NAV_HOVER,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            command=command,
        )

    def _build_sidebar(self) -> None:
        p = self._UI_PAD
        sidebar = ctk.CTkFrame(
            self.root,
            width=self._SIDEBAR_WIDTH,
            corner_radius=10,
            fg_color=self._SIDEBAR_BG,
        )
        sidebar.grid(row=0, column=0, sticky="nsew", padx=(p, 0), pady=p)
        sidebar.grid_propagate(False)

        brand = ctk.CTkLabel(
            sidebar,
            text="try-working-hard",
            font=self._font_title,
            text_color=(self._TEXT_TITLE, self._TEXT_TITLE),
            anchor="w",
        )
        brand.pack(anchor="w", padx=p, pady=(p, 4))

        self._lbl_subtitle = ctk.CTkLabel(
            sidebar,
            text=self._t("app_subtitle"),
            font=self._font_body,
            text_color=self._TEXT_MUTED,
            anchor="w",
        )
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
            text=self._t("theme_hint"),
            font=ctk.CTkFont(family=_FONT_INTER, size=11),
            text_color=self._TEXT_MUTED,
        )
        self._hint.pack(anchor="w", padx=p, pady=(0, p))
        self._sync_nav_highlight()

    def _build_main(self) -> None:
        p = self._UI_PAD
        main = ctk.CTkFrame(self.root, corner_radius=10, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=(0, p), pady=p)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        main_top = ctk.CTkFrame(main, fg_color="transparent")
        main_top.grid(row=0, column=0, sticky="ew", padx=p, pady=(0, 8))
        main_top.grid_columnconfigure(0, weight=1)

        self.view_segmented = ctk.CTkSegmentedButton(
            main_top,
            values=[self._t("nav_home"), self._t("nav_settings"), self._t("nav_analytics")],
            command=self._on_view_segment,
            corner_radius=10,
            font=self._font_body_bold,
            height=36,
            fg_color=self._CARD_BG,
            selected_color=self._ACCENT,
            selected_hover_color=self._ACCENT_HOVER,
            unselected_color=self._BTN_SECONDARY,
            unselected_hover_color=self._BTN_SECONDARY_HOVER,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            text_color_disabled=(self._TEXT_DISABLED, self._TEXT_DISABLED),
        )
        _try_takefocus(self.view_segmented, 1)
        self.view_segmented.grid(row=0, column=0, sticky="w")
        self.view_segmented.set(self._t("nav_home"))

        self.pages_host = ctk.CTkFrame(main, corner_radius=10, fg_color="transparent")
        self.pages_host.grid(row=1, column=0, sticky="nsew")
        self.pages_host.grid_columnconfigure(0, weight=1)
        self.pages_host.grid_rowconfigure(0, weight=1)

        self.page_home = ctk.CTkFrame(self.pages_host, corner_radius=10, fg_color="transparent")
        self.page_home.grid(row=0, column=0, sticky="nsew")
        self.page_home.grid_columnconfigure(0, weight=1)
        self.page_home.grid_rowconfigure(3, weight=1)

        self._lbl_status = ctk.CTkLabel(
            self.page_home,
            textvariable=self.status,
            font=self._font_body,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            anchor="w",
        )
        self._lbl_status.grid(row=0, column=0, sticky="ew", padx=p, pady=(p, 8))

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
            corner_radius=10,
            font=self._font_body_bold,
            height=36,
            fg_color=self._CARD_BG,
            selected_color=self._ACCENT,
            selected_hover_color=self._ACCENT_HOVER,
            unselected_color=self._BTN_SECONDARY,
            unselected_hover_color=self._BTN_SECONDARY_HOVER,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            text_color_disabled=(self._TEXT_DISABLED, self._TEXT_DISABLED),
        )
        _try_takefocus(self.segmented, 1)
        self.segmented.grid(row=0, column=1, sticky="e")
        self.segmented.set(self._segment_text(self._segment_mode))

        self.content_host = ctk.CTkFrame(self.page_home, fg_color="transparent")
        self.content_host.grid(row=3, column=0, sticky="nsew", padx=p, pady=(0, p))
        self.content_host.grid_columnconfigure(0, weight=1)
        self.content_host.grid_rowconfigure(0, weight=1)

        self.frame_control = ctk.CTkFrame(self.content_host, fg_color=self._CARD_BG, corner_radius=10)
        self.frame_control.grid(row=0, column=0, sticky="nsew")
        self._fill_control_panel(self.frame_control)

        self.frame_log = ctk.CTkFrame(self.content_host, fg_color=self._CARD_BG, corner_radius=10)
        self._fill_log_panel(self.frame_log)
        self.frame_log.grid_remove()

        self.page_settings = ctk.CTkFrame(self.pages_host, corner_radius=10, fg_color=self._CARD_BG)
        self._fill_settings_panel(self.page_settings)

        self.page_analytics = ctk.CTkFrame(self.pages_host, corner_radius=10, fg_color=self._CARD_BG)
        self._fill_analytics_panel(self.page_analytics)

        self.page_settings.grid_remove()
        self.page_analytics.grid_remove()

    def _on_view_segment(self, value: str) -> None:
        if value == self._t("nav_home"):
            self._on_nav("home")
        elif value == self._t("nav_settings"):
            self._on_nav("settings")
        else:
            self._on_nav("analytics")

    def _sync_view_segment(self) -> None:
        if self._active_nav == "home":
            label = self._t("nav_home")
        elif self._active_nav == "settings":
            label = self._t("nav_settings")
        else:
            label = self._t("nav_analytics")
        try:
            self.view_segmented.set(label)
        except (tk.TclError, AttributeError):
            pass

    def _on_nav(self, page: Literal["home", "settings", "analytics"]) -> None:
        self._active_nav = page
        self._sync_nav_highlight()
        self._sync_view_segment()
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

    def _sync_nav_highlight(self) -> None:
        for key, btn in (
            ("home", self._nav_home),
            ("settings", self._nav_settings),
            ("analytics", self._nav_analytics),
        ):
            if key == self._active_nav:
                btn.configure(fg_color=self._NAV_SELECTED, hover_color=self._ACCENT_HOVER)
            else:
                btn.configure(fg_color="transparent", hover_color=self._NAV_HOVER)

    def _fill_settings_panel(self, card: ctk.CTkFrame) -> None:
        p = self._UI_PAD
        card.grid_columnconfigure(0, weight=1)

        self._lbl_settings_title = ctk.CTkLabel(
            card,
            text=self._t("settings_title"),
            font=self._font_title,
            text_color=(self._TEXT_TITLE, self._TEXT_TITLE),
        )
        self._lbl_settings_title.grid(row=0, column=0, sticky="w", padx=p, pady=(p, p))

        self._lbl_lang = ctk.CTkLabel(
            card,
            text=self._t("lang_ui"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            anchor="w",
        )
        self._lbl_lang.grid(row=1, column=0, sticky="w", padx=p, pady=(0, p))

        self._lang_seg = ctk.CTkSegmentedButton(
            card,
            values=["繁中", "English"],
            command=self._on_lang_switch,
            corner_radius=10,
            font=self._font_body_bold,
            height=32,
            fg_color=self._MAIN_BG,
            selected_color=self._ACCENT,
            selected_hover_color=self._ACCENT_HOVER,
            unselected_color=self._BTN_SECONDARY,
            unselected_hover_color=self._BTN_SECONDARY_HOVER,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
        )
        self._lang_seg.grid(row=2, column=0, sticky="ew", padx=p, pady=(0, p))
        self._lang_seg.set("English")
        _try_takefocus(self._lang_seg, 1)

        self._hint_settings = ctk.CTkLabel(
            card,
            text=self._t("theme_hint"),
            font=ctk.CTkFont(family=_FONT_INTER, size=11),
            text_color=self._TEXT_MUTED,
            anchor="w",
        )
        self._hint_settings.grid(row=3, column=0, sticky="w", padx=p, pady=(p, p))

        self.btn_open_config = self._btn(
            card,
            text=self._t("btn_open_config_file"),
            command=self._on_open_config_file,
            fg_color=self._BTN_SECONDARY,
            hover_color=self._BTN_SECONDARY_HOVER,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            anchor="w",
        )
        self.btn_open_config.grid(row=4, column=0, sticky="w", padx=p, pady=(0, p))
        _try_takefocus(self.btn_open_config, 1)

        self.var_tray_close = tk.BooleanVar(value=False)
        tray_row = ctk.CTkFrame(card, fg_color="transparent")
        tray_row.grid(row=5, column=0, sticky="ew", padx=p, pady=(0, 8))
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
            fg_color=self._BTN_SECONDARY,
            progress_color=self._ACCENT,
            button_color=self._TEXT_TITLE,
            button_hover_color=self._TEXT_BODY,
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
        self._hint_tray.grid(row=6, column=0, sticky="ew", padx=p, pady=(0, p))
        if not HAS_TRAY:
            self.swt_tray.configure(state="disabled")

    def _fill_analytics_panel(self, card: ctk.CTkFrame) -> None:
        p = self._UI_PAD
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(2, weight=1)

        self._lbl_analytics_title = ctk.CTkLabel(
            card,
            text=self._t("analytics_title"),
            font=self._font_title,
            text_color=(self._TEXT_TITLE, self._TEXT_TITLE),
        )
        self._lbl_analytics_title.grid(row=0, column=0, sticky="w", padx=p, pady=(p, p))

        self._lbl_analytics_sub = ctk.CTkLabel(
            card,
            text=self._t("analytics_subtitle"),
            font=self._font_body,
            text_color=self._TEXT_MUTED,
            anchor="w",
        )
        self._lbl_analytics_sub.grid(row=1, column=0, sticky="w", padx=p, pady=(0, p))

        self.analytics_log = ctk.CTkTextbox(
            card,
            corner_radius=10,
            font=self._font_mono,
            fg_color=self._ENTRY_BG,
            text_color=(self._TEXT_LOG, self._TEXT_LOG),
            border_width=1,
            border_color=self._BORDER,
        )
        self.analytics_log.grid(row=2, column=0, sticky="nsew", padx=p, pady=(0, p))
        self.analytics_log.configure(state="disabled")
        _try_takefocus(self.analytics_log, 1)

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

    def _fill_control_panel(self, card: ctk.CTkFrame) -> None:
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
            height=36,
            corner_radius=10,
            font=self._font_body,
            fg_color=self._ENTRY_BG,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            border_width=1,
            border_color=self._BORDER,
        )
        self.entry_minutes.pack(side="left")
        _try_takefocus(self.entry_minutes, 1)
        self.seg_interval_unit = ctk.CTkSegmentedButton(
            row1,
            values=[self._t("interval_unit_min"), self._t("interval_unit_sec")],
            command=self._on_interval_unit_seg,
            corner_radius=10,
            font=self._font_body,
            height=36,
            fg_color=self._CARD_BG,
            selected_color=self._ACCENT,
            selected_hover_color=self._ACCENT_HOVER,
            unselected_color=self._BTN_SECONDARY,
            unselected_hover_color=self._BTN_SECONDARY_HOVER,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
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

        self._lbl_pixels = ctk.CTkLabel(
            card,
            text=self._t("pixels_label"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
        )
        self._lbl_pixels.grid(row=2, column=0, sticky="w", padx=p, pady=(p, p))
        row3 = ctk.CTkFrame(card, fg_color="transparent")
        row3.grid(row=3, column=0, sticky="ew", padx=p, pady=(0, p))
        self.var_pixels = tk.StringVar(value=str(self.DEFAULT_PIXELS))
        self.entry_pixels = ctk.CTkEntry(
            row3,
            textvariable=self.var_pixels,
            width=120,
            height=36,
            corner_radius=10,
            font=self._font_body,
            fg_color=self._ENTRY_BG,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            border_width=1,
            border_color=self._BORDER,
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

        self._lbl_motion_burst = ctk.CTkLabel(
            card,
            text=self._t("motion_burst_label"),
            font=self._font_body_bold,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
        )
        self._lbl_motion_burst.grid(row=4, column=0, sticky="w", padx=p, pady=(p, p))
        row_motion = ctk.CTkFrame(card, fg_color="transparent")
        row_motion.grid(row=5, column=0, sticky="ew", padx=p, pady=(0, p))
        self.var_motion_burst = tk.StringVar(value=str(int(self.DEFAULT_MOTION_BURST)))
        self.entry_motion_burst = ctk.CTkEntry(
            row_motion,
            textvariable=self.var_motion_burst,
            width=120,
            height=36,
            corner_radius=10,
            font=self._font_body,
            fg_color=self._ENTRY_BG,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            border_width=1,
            border_color=self._BORDER,
        )
        self.entry_motion_burst.pack(side="left")
        _try_takefocus(self.entry_motion_burst, 1)
        self._lbl_motion_burst_hint = ctk.CTkLabel(
            row_motion,
            text=self._t("motion_burst_hint", hi=self.MAX_MOTION_BURST),
            font=self._font_body,
            text_color=self._TEXT_MUTED,
        )
        self._lbl_motion_burst_hint.pack(side="left", padx=(12, 0))
        self._a11y_label_focus_entry(self._lbl_motion_burst, self.entry_motion_burst)

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.grid(row=6, column=0, sticky="w", padx=p, pady=(p, p))

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
            corner_radius=10,
            font=self._font_mono,
            fg_color=self._ENTRY_BG,
            text_color=(self._TEXT_LOG, self._TEXT_LOG),
            border_width=1,
            border_color=self._BORDER,
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
        if self._countdown_phase == "burst":
            self.status.set(self._t("status_motion_burst", cd=countdown_str))
        else:
            self.status.set(self._t_status_running(countdown_str))
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

    def _parse_pixels(self) -> int | None:
        return nudge_logic.parse_pixels_string(
            self.var_pixels.get(), min_px=self.MIN_PIXELS, max_px=self.MAX_PIXELS
        )

    def _parse_motion_burst_sec(self) -> float | None:
        return nudge_logic.parse_motion_burst_seconds_string(
            self.var_motion_burst.get(),
            min_sec=self.MIN_MOTION_BURST,
            max_sec=self.MAX_MOTION_BURST,
        )

    def _nudge_tick(self, pixels: int, *, log_success: bool = True) -> None:
        try:
            jiggle_mouse(pixels)
            if not log_success:
                return
            if pixels > 0:
                self._log(self._t("log_nudge"))
            else:
                self._log(self._t("log_nudge_zero"))
        except OSError as e:
            self._log(self._t("log_nudge_fail", err=e))

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
        pixels = self._parse_pixels()
        if pixels is None:
            messagebox.showerror(
                self._t("err_title"),
                self._t("err_pixels", lo=self.MIN_PIXELS, hi=self.MAX_PIXELS),
                parent=self.root,
            )
            self._log(self._t("log_start_fail_pixels"))
            return
        motion_burst = self._parse_motion_burst_sec()
        if motion_burst is None:
            messagebox.showerror(
                self._t("err_title"),
                self._t("err_motion_burst", hi=self.MAX_MOTION_BURST),
                parent=self.root,
            )
            self._log(self._t("log_start_fail_motion"))
            return
        if self._worker is not None and self._worker.is_alive():
            return

        self._stop.clear()
        self._countdown_phase = "interval"
        interval_sec = ival * 60.0 if iu == "min" else ival
        self._running_interval_value = ival
        self._running_interval_unit = iu
        self._current_interval_sec = interval_sec
        self._running_motion_burst_sec = motion_burst
        self._next_jiggle_monotonic = time.monotonic() + interval_sec

        self._worker = threading.Thread(
            target=self._run_loop,
            args=(interval_sec, pixels, motion_burst),
            daemon=True,
        )
        self._worker.start()

        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.entry_minutes.configure(state="disabled")
        self.entry_pixels.configure(state="disabled")
        self.entry_motion_burst.configure(state="disabled")
        try:
            self.seg_interval_unit.configure(state="disabled")
        except (tk.TclError, AttributeError):
            pass
        self.status.set(self._t_status_running("—"))
        self._schedule_countdown_tick()
        extra = (
            self._t("log_started_motion_extra", mb=motion_burst)
            if motion_burst > 0
            else ""
        )
        if iu == "min":
            self._log(
                self._t(
                    "log_started_min",
                    v=ival,
                    sec=interval_sec,
                    px=pixels,
                    extra=extra,
                )
            )
        else:
            self._log(
                self._t("log_started_sec", v=ival, px=pixels, extra=extra)
            )

    def _on_stop(self) -> None:
        self._stop.set()
        self._cancel_countdown_tick()
        self._current_interval_sec = 0.0
        self._running_motion_burst_sec = 0.0
        self._countdown_phase = "interval"
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.entry_minutes.configure(state="normal")
        self.entry_pixels.configure(state="normal")
        self.entry_motion_burst.configure(state="normal")
        try:
            self.seg_interval_unit.configure(state="normal")
        except (tk.TclError, AttributeError):
            pass
        self.status.set(self._t("status_stopped"))
        self._log(self._t("log_stopped"))

    def _run_loop(self, interval_sec: float, pixels: int, motion_burst_sec: float) -> None:
        while not self._stop.is_set():
            self._countdown_phase = "interval"
            self._next_jiggle_monotonic = time.monotonic() + interval_sec
            if self._stop.wait(timeout=interval_sec):
                break
            burst = motion_burst_sec if pixels > 0 else 0.0
            if burst <= 0:
                self._nudge_tick(pixels, log_success=True)
            else:
                self._countdown_phase = "burst"
                burst_end = time.monotonic() + burst
                self._next_jiggle_monotonic = burst_end
                self._log(self._t("log_motion_burst_start", sec=burst))
                while time.monotonic() < burst_end and not self._stop.is_set():
                    self._nudge_tick(pixels, log_success=False)
                    rem = burst_end - time.monotonic()
                    if rem <= 0:
                        break
                    delay = min(nudge_logic.MOTION_BURST_STEP_SEC, rem)
                    if self._stop.wait(timeout=delay):
                        break

    def _start_tray(self) -> None:
        self._tray.start(
            tooltip=self._t("window_title"),
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
    MouseJigglerApp().run()
