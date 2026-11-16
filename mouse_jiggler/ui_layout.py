"""Window chrome: sidebar, navigation and page hosts."""

from __future__ import annotations

from typing import Any, Literal

import customtkinter as ctk

from .ui_common import (
    _FONT_INTER,
    _R,
    _R_BTN,
    _load_pkg_nav_png,
    _tint_rgba_image,
    _try_takefocus,
)


class LayoutMixin:
    """Mixin for :class:`mouse_jiggler.app.MouseJigglerApp`; relies on its shared state."""

    def _btn(self, master: Any, **kwargs: Any) -> ctk.CTkButton:
        """Primary/secondary style buttons (12–16px corner radius)."""
        kw = dict(corner_radius=_R_BTN, font=self._font_body, height=40)
        kw.update(kwargs)
        kw.pop("takefocus", None)  # CTkButton rejects this in **kwargs
        w = ctk.CTkButton(master, **kw)
        return w

    def _build_nav_icons(self) -> dict[str, ctk.CTkImage]:
        """Sidebar nav icons; tint matches unselected nav (gray on light)."""
        specs: list[tuple[str, str]] = [
            ("home", "house"),
            ("settings", "settings"),
            ("analytics", "chart-column"),
        ]
        out: dict[str, ctk.CTkImage] = {}
        for key, stem in specs:
            im = _load_pkg_nav_png(stem)
            if im is not None:
                im = _tint_rgba_image(im, self._NAV_TEXT)
                out[key] = ctk.CTkImage(light_image=im, dark_image=im, size=(20, 20))
            else:
                out[key] = self._nav_icon_fallback(key, self._NAV_TEXT, self._TEXT_MUTED)
        return out

    def _one_nav_ctk_image(
        self, key: str, body_hex: str, muted_hex: str
    ) -> ctk.CTkImage:
        """Single nav icon for the given key and two-tone glyph colors."""
        stems = {
            "home": "house",
            "settings": "settings",
            "analytics": "chart-column",
        }
        stem = stems[key]
        im = _load_pkg_nav_png(stem)
        if im is not None:
            im = _tint_rgba_image(im, body_hex)
            return ctk.CTkImage(light_image=im, dark_image=im, size=(20, 20))
        return self._nav_icon_fallback(key, body_hex, muted_hex)

    def _nav_icon_fallback(self, key: str, ic_body: str, ic_muted: str) -> ctk.CTkImage:
        from PIL import Image, ImageDraw

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
            corner_radius=_R,
            height=44,
            font=self._font_body,
            fg_color="transparent",
            hover_color=self._NAV_HOVER,
            text_color=(self._NAV_TEXT, self._NAV_TEXT),
            command=command,
        )

    def _build_sidebar(self) -> None:
        p = self._UI_PAD
        self._sidebar = ctk.CTkFrame(
            self.root,
            width=self._SIDEBAR_WIDTH,
            corner_radius=_R,
            fg_color=self._SIDEBAR_BG,
        )
        self._sidebar.grid(row=1, column=0, sticky="nsew", padx=(p, 0), pady=p)
        self._sidebar.grid_propagate(False)
        sidebar = self._sidebar

        self._brand = ctk.CTkLabel(
            sidebar,
            text=self._app_title_with_version(),
            font=self._font_brand,
            text_color=(self._TEXT_TITLE, self._TEXT_TITLE),
            anchor="w",
        )
        self._brand.pack(anchor="w", padx=p, pady=(p, 4))

        sub = self._t("app_subtitle").strip()
        self._lbl_subtitle = ctk.CTkLabel(
            sidebar,
            text=sub,
            font=self._font_body,
            text_color=self._TEXT_BODY,
            anchor="w",
        )
        if sub:
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
            text=self._theme_footer_text(),
            font=ctk.CTkFont(family=_FONT_INTER, size=11),
            text_color=self._TEXT_MUTED,
        )
        self._hint.pack(anchor="w", padx=p, pady=(0, p))
        self._sync_nav_highlight()

    def _build_main(self) -> None:
        p = self._UI_PAD
        main = ctk.CTkFrame(self.root, corner_radius=_R, fg_color="transparent")
        main.grid(row=1, column=1, sticky="nsew", padx=(0, p), pady=p)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(0, weight=1)

        self.pages_host = ctk.CTkFrame(main, corner_radius=_R, fg_color="transparent")
        self.pages_host.grid(row=0, column=0, sticky="nsew")
        self.pages_host.grid_columnconfigure(0, weight=1)
        self.pages_host.grid_rowconfigure(0, weight=1)

        self.page_home = ctk.CTkFrame(self.pages_host, corner_radius=_R, fg_color="transparent")
        self.page_home.grid(row=0, column=0, sticky="nsew")
        self.page_home.grid_columnconfigure(0, weight=1)
        self.page_home.grid_rowconfigure(2, weight=1)

        self._home_top_status = ctk.CTkFrame(self.page_home, fg_color="transparent")
        self._home_top_status.grid(row=0, column=0, sticky="ew", padx=p, pady=(p, 8))
        self._home_top_status.grid_columnconfigure(0, weight=1)

        self._status_strip = ctk.CTkFrame(
            self._home_top_status,
            corner_radius=_R,
            fg_color=self._STATUS_STRIP_BG_STOP,
            border_width=1,
            border_color=self._STATUS_STRIP_BORDER_STOP,
        )
        self._status_strip.grid(row=0, column=0, sticky="ew")
        self._status_strip.grid_columnconfigure(0, weight=1)
        status_inner = ctk.CTkFrame(self._status_strip, fg_color="transparent")
        status_inner.grid(row=0, column=0, sticky="ew", padx=14, pady=12)
        status_inner.grid_columnconfigure(1, weight=1)
        self._status_led = ctk.CTkLabel(
            status_inner,
            text="\u25cf",
            font=ctk.CTkFont(family=_FONT_INTER, size=12, weight="bold"),
            text_color=(self._STATUS_LED_STOP, self._STATUS_LED_STOP),
            width=18,
        )
        self._status_led.grid(row=0, column=0, sticky="nw", padx=(0, 10), pady=2)
        self._lbl_status = ctk.CTkLabel(
            status_inner,
            textvariable=self.status,
            font=self._font_body,
            text_color=(self._TEXT_BODY, self._TEXT_BODY),
            anchor="w",
            justify="left",
        )
        self._lbl_status.grid(row=0, column=1, sticky="ew")
        self.btn_run_toggle = self._btn(
            status_inner,
            text=self._t("btn_start"),
            width=120,
            fg_color=self._ACCENT,
            hover_color=self._ACCENT_HOVER,
            text_color=(self._TEXT_ON_ACCENT, self._TEXT_ON_ACCENT),
            border_width=2,
            border_color=self._ACCENT_HOVER,
            font=self._font_body_bold,
            command=self._on_toggle_run,
        )
        self.btn_run_toggle.grid(row=0, column=2, sticky="e", padx=(16, 0))

        self._lbl_schedule_banner = ctk.CTkLabel(
            self._home_top_status,
            text="",
            font=self._font_body,
            text_color=self._TEXT_MUTED,
            anchor="w",
            fg_color=self._SURFACE_SUBTLE,
            corner_radius=_R,
            height=36,
            padx=12,
            pady=6,
        )
        self._lbl_schedule_banner.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        self._lbl_schedule_banner.grid_remove()

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
            corner_radius=_R,
            font=self._font_body_bold,
            height=38,
            fg_color=self._SURFACE_SUBTLE,
            selected_color=self._ACCENT,
            selected_hover_color=self._ACCENT_HOVER,
            unselected_color=self._SURFACE_SUBTLE,
            unselected_hover_color=self._SURFACE_SUBTLE_HOVER,
            text_color=(self._TEXT_BODY, self._TEXT_ON_ACCENT),
            text_color_disabled=(self._TEXT_DISABLED, self._TEXT_DISABLED),
        )
        _try_takefocus(self.segmented, 1)
        self.segmented.grid(row=0, column=1, sticky="e")
        self.segmented.set(self._segment_text(self._segment_mode))

        self.content_host = ctk.CTkFrame(self.page_home, fg_color="transparent")
        self.content_host.grid(row=2, column=0, sticky="nsew", padx=p, pady=(0, p))
        self.content_host.grid_columnconfigure(0, weight=1)
        self.content_host.grid_rowconfigure(0, weight=1)

        self.page_settings = ctk.CTkFrame(self.pages_host, corner_radius=_R, fg_color="transparent")
        self.page_settings.grid_columnconfigure(0, weight=1)
        self.page_settings.grid_rowconfigure(1, weight=1)

        _ps = self._UI_PAD
        settings_head = ctk.CTkFrame(self.page_settings, fg_color="transparent")
        settings_head.grid(row=0, column=0, sticky="ew", padx=_ps, pady=(_ps, _ps))
        settings_head.grid_columnconfigure(0, weight=1)
        self._lbl_settings_title = ctk.CTkLabel(
            settings_head,
            text=self._t("settings_title"),
            font=self._font_title,
            text_color=(self._TEXT_TITLE, self._TEXT_TITLE),
        )
        self._lbl_settings_title.grid(row=0, column=0, sticky="w")

        self._settings_scroll = ctk.CTkScrollableFrame(
            self.page_settings,
            fg_color=self._CARD_BG,
            corner_radius=_R,
            border_width=1,
            border_color=self._CARD_BORDER,
            scrollbar_button_color=self._BTN_SECONDARY,
            scrollbar_button_hover_color=self._BTN_SECONDARY_HOVER,
        )
        self._settings_scroll.grid(row=1, column=0, sticky="nsew", padx=_ps, pady=(0, _ps))
        self._settings_scroll.grid_columnconfigure(0, weight=1)
        self._fill_settings_panel(self._settings_scroll)

        self.frame_control = ctk.CTkScrollableFrame(
            self.content_host,
            fg_color=self._CARD_BG,
            corner_radius=_R,
            border_width=1,
            border_color=self._CARD_BORDER,
            scrollbar_button_color=self._BTN_SECONDARY,
            scrollbar_button_hover_color=self._BTN_SECONDARY_HOVER,
        )
        self.frame_control.grid(row=0, column=0, sticky="nsew")
        self.frame_control.grid_columnconfigure(0, weight=1)
        self._fill_control_panel(self.frame_control)

        self.frame_log = ctk.CTkFrame(
            self.content_host,
            fg_color=self._CARD_BG,
            corner_radius=_R,
            border_width=1,
            border_color=self._CARD_BORDER,
        )
        self._fill_log_panel(self.frame_log)
        self.frame_log.grid_remove()

        self.page_analytics = ctk.CTkFrame(self.pages_host, corner_radius=_R, fg_color="transparent")
        self.page_analytics.grid_columnconfigure(0, weight=1)
        self.page_analytics.grid_rowconfigure(1, weight=1)

        analytics_head = ctk.CTkFrame(self.page_analytics, fg_color="transparent")
        analytics_head.grid(row=0, column=0, sticky="ew", padx=_ps, pady=(_ps, _ps))
        analytics_head.grid_columnconfigure(0, weight=1)
        self._lbl_analytics_title = ctk.CTkLabel(
            analytics_head,
            text=self._t("analytics_title"),
            font=self._font_title,
            text_color=(self._TEXT_TITLE, self._TEXT_TITLE),
        )
        self._lbl_analytics_title.grid(row=0, column=0, sticky="w")

        # The chart panel (matplotlib import + three figures) is built on first visit.
        self._analytics_built = False
        self._analytics_build_pending = False
        self._lbl_analytics_loading: ctk.CTkLabel | None = None
        self._analytics_loading_key = "analytics_loading"

        self.page_settings.grid_remove()
        self.page_analytics.grid_remove()

    def _on_nav(self, page: Literal["home", "settings", "analytics"]) -> None:
        self._active_nav = page
        self._sync_nav_highlight()
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
            if not self._analytics_built:
                self._schedule_analytics_page_build()
                return
            self._sync_analytics_log_from_main()
            self._refresh_analytics_charts()

    def _sync_nav_highlight(self) -> None:
        for key, btn in (
            ("home", self._nav_home),
            ("settings", self._nav_settings),
            ("analytics", self._nav_analytics),
        ):
            if key == self._active_nav:
                icon = self._one_nav_ctk_image(
                    key, self._NAV_ON_SELECTED, self._TEXT_BODY
                )
                btn.configure(
                    image=icon,
                    fg_color=self._NAV_SELECTED,
                    hover_color=self._ACCENT_HOVER,
                    text_color=(self._NAV_ON_SELECTED, self._NAV_ON_SELECTED),
                )
            else:
                icon = self._one_nav_ctk_image(
                    key, self._NAV_TEXT, self._TEXT_MUTED
                )
                btn.configure(
                    image=icon,
                    fg_color="transparent",
                    hover_color=self._NAV_HOVER,
                    text_color=(self._NAV_TEXT, self._NAV_TEXT),
                )
