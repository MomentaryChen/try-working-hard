"""Reusable one-time reminder dialog with dont-show-again option."""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QLabel, QVBoxLayout


class OneTimeReminderDialog(QDialog):
    def __init__(self, title: str, message: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(420, 220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        body = QLabel(message)
        body.setWordWrap(True)
        body.setObjectName("reminderText")
        layout.addWidget(body)

        self.dont_show_again = QCheckBox("Do not show this reminder again")
        layout.addWidget(self.dont_show_again)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
