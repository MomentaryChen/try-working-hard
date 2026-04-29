"""Settings page with real config bindings."""

from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from importlib.metadata import PackageNotFoundError, version as pkg_version
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from mouse_jiggler import local_config, updater


class SettingsPage(QWidget):
    reset_reminders_requested = Signal()
    settings_saved = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("pageRoot")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        panel = QFrame()
        panel.setObjectName("settingsPanel")
        p = QVBoxLayout(panel)
        p.setContentsMargins(16, 16, 16, 16)
        p.setSpacing(10)
        title = QLabel("Settings")
        title.setObjectName("sectionTitle")
        p.addWidget(title)
        hint = QLabel("Language, appearance, startup behavior, and schedule defaults.")
        hint.setObjectName("mutedText")
        p.addWidget(hint)

        general_title = QLabel("General")
        general_title.setObjectName("sectionTitle")
        p.addWidget(general_title)
        form = QFormLayout()
        self.lang = QComboBox()
        self.lang.addItems(["en", "zh"])
        self.theme = QComboBox()
        self.theme.addItems(["dark", "light"])
        self.interval_unit = QComboBox()
        self.interval_unit.addItems(["min", "sec"])
        self.close_to_tray = QCheckBox("Minimize to tray on close")
        self.auto_updates = QCheckBox("Auto-check updates on startup")
        self.schedule_window = QCheckBox("Enable schedule window")
        self.schedule_segments = QLineEdit()
        self.schedule_weekends = QCheckBox("Include weekends")
        self.schedule_cron = QLineEdit()
        form.addRow("Language", self.lang)
        form.addRow("Theme", self.theme)
        form.addRow("Interval unit", self.interval_unit)
        form.addRow("", self.close_to_tray)
        form.addRow("", self.auto_updates)
        form.addRow("", self.schedule_window)
        form.addRow("Schedule segments", self.schedule_segments)
        form.addRow("", self.schedule_weekends)
        form.addRow("Schedule cron", self.schedule_cron)
        p.addLayout(form)

        about_title = QLabel("About and updates")
        about_title.setObjectName("sectionTitle")
        p.addWidget(about_title)
        self.version_label = QLabel("Version: -")
        self.version_label.setObjectName("mutedText")
        p.addWidget(self.version_label)

        row = QHBoxLayout()
        self.open_btn = QPushButton("Open config file")
        self.open_btn.setObjectName("secondaryButton")
        self.check_updates_btn = QPushButton("Check for updates")
        self.check_updates_btn.setObjectName("secondaryButton")
        self.contact_btn = QPushButton("Contact us")
        self.contact_btn.setObjectName("secondaryButton")
        self.reset_btn = QPushButton("Reset one-time reminders")
        self.reset_btn.setObjectName("secondaryButton")
        self.save_btn = QPushButton("Save")
        self.save_btn.setObjectName("primaryButton")
        row.addWidget(self.open_btn)
        row.addWidget(self.check_updates_btn)
        row.addWidget(self.contact_btn)
        row.addWidget(self.reset_btn)
        row.addStretch(1)
        row.addWidget(self.save_btn)
        p.addLayout(row)
        root.addWidget(panel)
        root.addStretch(1)

        self.open_btn.clicked.connect(self._open_config_file)
        self.check_updates_btn.clicked.connect(self._check_updates)
        self.contact_btn.clicked.connect(self._open_contact)
        self.reset_btn.clicked.connect(self.reset_reminders_requested.emit)
        self.save_btn.clicked.connect(self.save)
        self.load()

    def load(self) -> None:
        cfg = local_config.load_config()
        self.lang.setCurrentText(str(cfg.get("lang", "en")))
        self.theme.setCurrentText(str(cfg.get("ui_theme", "dark")))
        self.interval_unit.setCurrentText(str(cfg.get("interval_unit", "min")))
        self.close_to_tray.setChecked(bool(cfg.get("close_to_tray", False)))
        self.auto_updates.setChecked(bool(cfg.get("auto_check_updates", True)))
        self.schedule_window.setChecked(bool(cfg.get("schedule_window", False)))
        self.schedule_segments.setText(str(cfg.get("schedule_window_segments_text", "09:00-18:00")))
        self.schedule_weekends.setChecked(bool(cfg.get("schedule_include_weekends", False)))
        self.schedule_cron.setText(str(cfg.get("schedule_cron_text", "")))
        self.version_label.setText(f"Version: {self._current_version()}")

    def save(self) -> None:
        cfg = local_config.load_config()
        cfg.update(
            {
                "lang": self.lang.currentText(),
                "ui_theme": self.theme.currentText(),
                "interval_unit": self.interval_unit.currentText(),
                "close_to_tray": self.close_to_tray.isChecked(),
                "auto_check_updates": self.auto_updates.isChecked(),
                "schedule_window": self.schedule_window.isChecked(),
                "schedule_window_segments_text": self.schedule_segments.text().strip() or "09:00-18:00",
                "schedule_include_weekends": self.schedule_weekends.isChecked(),
                "schedule_cron_text": self.schedule_cron.text().strip(),
            }
        )
        local_config.save_config(cfg)
        self.settings_saved.emit("Settings saved.")

    def _open_config_file(self) -> None:
        cfg = local_config.load_config()
        path = local_config.default_config_path()
        local_config.save_config(cfg, path)
        self._open_path(path)

    def _open_path(self, path: Path) -> None:
        try:
            if sys.platform == "win32":
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except OSError:
            self.settings_saved.emit(f"Config path: {path}")

    def _current_version(self) -> str:
        try:
            return pkg_version("try-working-hard")
        except (PackageNotFoundError, OSError):
            return "dev"

    def _check_updates(self) -> None:
        try:
            latest = updater.fetch_latest_release()
        except RuntimeError as exc:
            self.settings_saved.emit(str(exc))
            return
        current = self._current_version()
        tag = latest.get("tag", "")
        url = latest.get("url", "")
        if updater.is_newer_version(tag, current):
            self.settings_saved.emit(f"Update available: {tag} (current {current})")
            if url:
                webbrowser.open(url)
            return
        self.settings_saved.emit(f"You're up to date ({current}).")

    def _open_contact(self) -> None:
        webbrowser.open("https://github.com/MomentaryChen/try-working-hard/issues")
