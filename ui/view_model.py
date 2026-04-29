"""Simple view model for page routing state."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class NavigationViewModel(QObject):
    """Keeps the active page and emits updates."""

    page_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._active_page = "home"

    @property
    def active_page(self) -> str:
        return self._active_page

    def set_active_page(self, page_key: str) -> None:
        if page_key == self._active_page:
            return
        self._active_page = page_key
        self.page_changed.emit(page_key)
