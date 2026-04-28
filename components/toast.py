"""Simple toast notification widget for non-blocking feedback."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, Qt
from PySide6.QtWidgets import QLabel, QGraphicsOpacityEffect, QWidget


class Toast(QWidget):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("toast")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.hide()

        self.label = QLabel(self)
        self.label.setObjectName("toastLabel")
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity)
        self.opacity.setOpacity(0.0)

        self.fade = QPropertyAnimation(self.opacity, b"opacity", self)
        self.fade.setDuration(180)
        self.fade.setEasingCurve(QEasingCurve.OutCubic)

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self._start_fade_out)

    def show_message(self, message: str, duration_ms: int = 2200) -> None:
        self.label.setText(message)
        self._layout_toast()
        self._start_fade_in()
        self.hide_timer.start(duration_ms)

    def _layout_toast(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        max_width = min(420, parent.width() - 36)
        self.label.setFixedWidth(max_width - 28)
        self.label.adjustSize()
        height = self.label.height() + 20
        width = self.label.width() + 28
        self.setGeometry(parent.width() - width - 18, parent.height() - height - 18, width, height)
        self.label.move(14, 10)

    def _start_fade_in(self) -> None:
        self.show()
        self.fade.stop()
        self.fade.setStartValue(self.opacity.opacity())
        self.fade.setEndValue(1.0)
        self.fade.start()

    def _start_fade_out(self) -> None:
        self.fade.stop()
        self.fade.setStartValue(self.opacity.opacity())
        self.fade.setEndValue(0.0)
        self.fade.finished.connect(self._hide_when_transparent)
        self.fade.start()

    def _hide_when_transparent(self) -> None:
        if self.opacity.opacity() <= 0.01:
            self.hide()
        try:
            self.fade.finished.disconnect(self._hide_when_transparent)
        except RuntimeError:
            pass
