"""Sidebar navigation button component."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QPushButton


class SidebarButton(QPushButton):
    clicked_with_key = Signal(str)

    def __init__(self, label: str, page_key: str, icon: QIcon | None = None) -> None:
        super().__init__(label)
        self.page_key = page_key
        self.setCursor(Qt.PointingHandCursor)
        self.setCheckable(True)
        self.setObjectName("sidebarButton")
        if icon is not None:
            self.setIcon(icon)
            self.setIconSize(QSize(18, 18))
        self.clicked.connect(self._emit_key)

    def _emit_key(self) -> None:
        self.clicked_with_key.emit(self.page_key)
