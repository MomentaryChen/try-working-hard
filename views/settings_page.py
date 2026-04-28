"""Settings page with profile fields and toggle controls."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class SettingsPage(QWidget):
    reset_reminders_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("pageRoot")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        panel = QFrame()
        panel.setObjectName("settingsPanel")

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(16, 16, 16, 16)
        panel_layout.setSpacing(14)

        title = QLabel("Workspace Preferences")
        title.setObjectName("sectionTitle")
        panel_layout.addWidget(title)

        form = QFormLayout()
        form.setVerticalSpacing(12)
        form.setHorizontalSpacing(14)

        self.name_input = QLineEdit("Victor Chen")
        self.email_input = QLineEdit("victor@example.com")
        self.company_input = QLineEdit("Acme Labs")

        form.addRow("Display name", self.name_input)
        form.addRow("Email", self.email_input)
        form.addRow("Organization", self.company_input)
        panel_layout.addLayout(form)

        toggles = QHBoxLayout()
        toggles.setSpacing(24)

        self.notification_toggle = QCheckBox("Enable desktop notifications")
        self.notification_toggle.setChecked(True)
        self.auto_sync_toggle = QCheckBox("Enable automatic sync")
        self.auto_sync_toggle.setChecked(True)

        toggles.addWidget(self.notification_toggle)
        toggles.addWidget(self.auto_sync_toggle)
        toggles.addStretch(1)
        panel_layout.addLayout(toggles)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.reset_reminders_button = QPushButton("Reset One-Time Reminders")
        self.reset_reminders_button.setObjectName("secondaryButton")
        actions.addWidget(self.reset_reminders_button)
        actions.addStretch(1)
        panel_layout.addLayout(actions)

        layout.addWidget(panel)
        layout.addStretch(1)

        self.reset_reminders_button.clicked.connect(self.reset_reminders_requested.emit)
