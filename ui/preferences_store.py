"""Persistent UI preferences for one-time reminders."""

from __future__ import annotations

from PySide6.QtCore import QSettings


class PreferencesStore:
    def __init__(self) -> None:
        self.settings = QSettings("TryWorkingHard", "ModernDashboard")

    def should_show_reminder(self, reminder_key: str) -> bool:
        return self.settings.value(f"reminders/{reminder_key}", True, bool)

    def remember_dismissed(self, reminder_key: str) -> None:
        self.settings.setValue(f"reminders/{reminder_key}", False)

    def reset_reminders(self) -> None:
        self.settings.remove("reminders")
