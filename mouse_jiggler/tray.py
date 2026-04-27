"""System tray icon (pystray) in a background thread."""

from __future__ import annotations

import threading
from typing import Any, Callable

try:
    import pystray  # noqa: F401
except ImportError:
    HAS_TRAY = False
else:
    HAS_TRAY = True


def build_tray_image() -> Any:
    from PIL import Image, ImageDraw

    from .app_icon import load_app_icon_rgba

    src = load_app_icon_rgba()
    if src is not None:
        w, h = 64, 64
        return src.resize((w, h), Image.Resampling.LANCZOS)

    w, h = 64, 64
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((6, 6, w - 6, h - 6), fill=(59, 125, 214, 255))
    return img


class TrayController:
    """Runs ``pystray.Icon.run()`` on a daemon thread; call ``stop()`` from the UI thread."""

    def __init__(self) -> None:
        self._icon: Any = None
        self._thread: threading.Thread | None = None

    def start(
        self,
        *,
        tooltip: str,
        label_show: str,
        label_quit: str,
        on_show: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        if not HAS_TRAY:
            return
        if self._thread is not None and self._thread.is_alive():
            return

        def run_tray() -> None:
            import pystray

            image = build_tray_image()
            menu = pystray.Menu(
                pystray.MenuItem(label_show, lambda icon, item: on_show(), default=True),
                pystray.MenuItem(label_quit, lambda icon, item: on_quit()),
            )
            icon = pystray.Icon("try-working-hard", image, tooltip, menu)
            self._icon = icon
            try:
                icon.run()
            finally:
                self._icon = None

        self._thread = threading.Thread(target=run_tray, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        icon = self._icon
        if icon is not None:
            try:
                icon.stop()
            except Exception:
                pass
        self._icon = None

    @property
    def thread(self) -> threading.Thread | None:
        return self._thread
