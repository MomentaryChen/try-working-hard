"""Home page (Control + Log) for PySide6 migration."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from mouse_jiggler import local_config, nudge_logic
from ui.jiggler_runtime import JigglerRuntime


class DashboardPage(QWidget):
    """Represents the old Home page semantics."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("pageRoot")
        self.runtime = JigglerRuntime()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)
        root.addWidget(self._build_status_strip())
        root.addWidget(self._build_segment())
        root.addWidget(self._build_content(), 1)

        self.runtime.status_changed.connect(self.status_text.setText)
        self.runtime.countdown_changed.connect(self.countdown_text.setText)
        self.runtime.log_emitted.connect(self._append_log)
        self.runtime.running_changed.connect(self._on_running_changed)
        self._load_config()
        self._on_running_changed(False)

    def _build_status_strip(self) -> QFrame:
        strip = QFrame()
        strip.setObjectName("statusStrip")
        h = QHBoxLayout(strip)
        h.setContentsMargins(12, 8, 12, 8)
        h.setSpacing(12)
        self.status_text = QLabel("Stopped")
        self.status_text.setObjectName("sectionTitle")
        self.countdown_text = QLabel("0:00")
        self.countdown_text.setObjectName("mutedText")
        h.addWidget(QLabel("Status:"))
        h.addWidget(self.status_text)
        h.addStretch(1)
        h.addWidget(QLabel("Next:"))
        h.addWidget(self.countdown_text)
        return strip

    def _build_segment(self) -> QFrame:
        row = QFrame()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        self.control_btn = QPushButton("Control")
        self.control_btn.setObjectName("primaryButton")
        self.log_btn = QPushButton("Log")
        self.log_btn.setObjectName("secondaryButton")
        self.control_btn.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        self.log_btn.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        h.addWidget(self.control_btn)
        h.addWidget(self.log_btn)
        h.addStretch(1)
        return row

    def _build_content(self) -> QWidget:
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_control_panel())
        self.stack.addWidget(self._build_log_panel())
        self.stack.currentChanged.connect(self._sync_segment_style)
        self._sync_segment_style(0)
        return self.stack

    def _build_control_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("settingsPanel")
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)
        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        self.interval_text = QLineEdit()
        self.interval_unit = QComboBox()
        self.interval_unit.addItems(["min", "sec"])
        unit_row = QWidget()
        unit_layout = QHBoxLayout(unit_row)
        unit_layout.setContentsMargins(0, 0, 0, 0)
        unit_layout.setSpacing(6)
        unit_layout.addWidget(self.interval_text, 1)
        unit_layout.addWidget(self.interval_unit)
        preset_row = QWidget()
        preset_layout = QHBoxLayout(preset_row)
        preset_layout.setContentsMargins(0, 0, 0, 0)
        preset_layout.setSpacing(6)
        self.preset_30s = QPushButton("30s")
        self.preset_1m = QPushButton("1m")
        self.preset_5m = QPushButton("5m")
        self.preset_10m = QPushButton("10m")
        for btn in (self.preset_30s, self.preset_1m, self.preset_5m, self.preset_10m):
            btn.setObjectName("secondaryButton")
            preset_layout.addWidget(btn)
        preset_layout.addStretch(1)

        self.interval_jitter = QLineEdit()
        self.pixels_text = QLineEdit()
        self.path_speed_text = QLineEdit()
        self.activity_style = QComboBox()
        self.activity_style.addItems(["pattern", "natural"])
        self.motion_pattern = QComboBox()
        self.motion_pattern.addItems(["horizontal", "circle", "square"])
        self.rare_click = QCheckBox("Occasional left click")
        self.rare_scroll = QCheckBox("Occasional wheel scroll")

        self.schedule_enabled = QCheckBox("Enable schedule window")
        self.schedule_segments = QLineEdit()
        self.schedule_segments.setPlaceholderText("09:00-18:00")
        self.schedule_weekends = QCheckBox("Include weekends")
        self.schedule_cron = QLineEdit()
        self.schedule_cron.setPlaceholderText("cron-like rules, separated by ';'")

        form.addRow("Interval", unit_row)
        form.addRow("", preset_row)
        form.addRow("Interval jitter (± sec)", self.interval_jitter)
        form.addRow("Nudge (pixels)", self.pixels_text)
        form.addRow("Path speed", self.path_speed_text)
        form.addRow("Activity style", self.activity_style)
        form.addRow("Path", self.motion_pattern)
        form.addRow("", self.rare_click)
        form.addRow("", self.rare_scroll)
        form.addRow("", self.schedule_enabled)
        form.addRow("Schedule segments", self.schedule_segments)
        form.addRow("", self.schedule_weekends)
        form.addRow("Schedule cron", self.schedule_cron)

        self.start_btn = QPushButton("Start")
        self.start_btn.setObjectName("primaryButton")
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setObjectName("secondaryButton")
        action_row = QWidget()
        action_layout = QHBoxLayout(action_row)
        action_layout.setContentsMargins(0, 4, 0, 0)
        action_layout.addWidget(self.start_btn)
        action_layout.addWidget(self.stop_btn)
        action_layout.addStretch(1)
        form.addRow("", action_row)
        outer.addLayout(form)
        self.schedule_hint = QLabel("Schedule summary: always on")
        self.schedule_hint.setObjectName("mutedText")
        outer.addWidget(self.schedule_hint)

        self.start_btn.clicked.connect(self.start_runtime)
        self.stop_btn.clicked.connect(self.stop_runtime)
        self.activity_style.currentTextChanged.connect(self._on_activity_style_changed)
        self.preset_30s.clicked.connect(lambda: self._apply_interval_preset("sec", "30"))
        self.preset_1m.clicked.connect(lambda: self._apply_interval_preset("min", "1"))
        self.preset_5m.clicked.connect(lambda: self._apply_interval_preset("min", "5"))
        self.preset_10m.clicked.connect(lambda: self._apply_interval_preset("min", "10"))
        self.schedule_enabled.toggled.connect(lambda _: self._refresh_schedule_hint())
        self.schedule_segments.textChanged.connect(lambda _: self._refresh_schedule_hint())
        self.schedule_weekends.toggled.connect(lambda _: self._refresh_schedule_hint())
        self.schedule_cron.textChanged.connect(lambda _: self._refresh_schedule_hint())
        return panel

    def _build_log_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("chartPlaceholder")
        v = QVBoxLayout(panel)
        v.setContentsMargins(16, 16, 16, 16)
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        v.addWidget(self.log_box, 1)
        return panel

    def _load_config(self) -> None:
        cfg = local_config.load_config()
        self.interval_text.setText(str(cfg.get("interval_text", "5")))
        self.interval_unit.setCurrentText(str(cfg.get("interval_unit", "min")))
        self.interval_jitter.setText(str(cfg.get("interval_jitter_text", "0")))
        self.pixels_text.setText(str(cfg.get("pixels_text", "100")))
        self.path_speed_text.setText(str(cfg.get("path_speed_text", "5")))
        self.activity_style.setCurrentText(str(cfg.get("activity_style", "pattern")))
        self.motion_pattern.setCurrentText(str(cfg.get("motion_pattern", "horizontal")))
        self.rare_click.setChecked(bool(cfg.get("natural_rare_click", False)))
        self.rare_scroll.setChecked(bool(cfg.get("natural_rare_scroll", False)))
        self.schedule_enabled.setChecked(bool(cfg.get("schedule_window", False)))
        self.schedule_segments.setText(str(cfg.get("schedule_window_segments_text", "09:00-18:00")))
        self.schedule_weekends.setChecked(bool(cfg.get("schedule_include_weekends", False)))
        self.schedule_cron.setText(str(cfg.get("schedule_cron_text", "")))
        self._on_activity_style_changed(self.activity_style.currentText())
        self._refresh_schedule_hint()

    def collect_config(self) -> dict[str, Any]:
        return {
            "interval_text": self.interval_text.text().strip(),
            "interval_unit": self.interval_unit.currentText(),
            "interval_jitter_text": self.interval_jitter.text().strip() or "0",
            "pixels_text": self.pixels_text.text().strip(),
            "path_speed_text": self.path_speed_text.text().strip(),
            "activity_style": self.activity_style.currentText(),
            "motion_pattern": self.motion_pattern.currentText(),
            "natural_rare_click": self.rare_click.isChecked(),
            "natural_rare_scroll": self.rare_scroll.isChecked(),
            "schedule_window": self.schedule_enabled.isChecked(),
            "schedule_window_segments_text": self.schedule_segments.text().strip() or "09:00-18:00",
            "schedule_include_weekends": self.schedule_weekends.isChecked(),
            "schedule_cron_text": self.schedule_cron.text().strip(),
        }

    def start_runtime(self) -> None:
        cfg = self.collect_config()
        if nudge_logic.parse_interval_to_seconds(cfg["interval_text"], cfg["interval_unit"]) is None:
            self._append_log("Invalid interval.")
            return
        if nudge_logic.parse_interval_jitter_seconds_string(cfg["interval_jitter_text"]) is None:
            self._append_log("Invalid interval jitter.")
            return
        if nudge_logic.parse_pixels_string(cfg["pixels_text"]) is None:
            self._append_log("Invalid pixels.")
            return
        if nudge_logic.parse_path_speed_string(cfg["path_speed_text"]) is None:
            self._append_log("Invalid path speed.")
            return
        persisted = local_config.load_config()
        persisted.update(cfg)
        local_config.save_config(persisted)
        self.runtime.start(cfg)
        self.status_text.setText("Running")

    def stop_runtime(self) -> None:
        self.runtime.stop()

    def _on_running_changed(self, running: bool) -> None:
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        if not running and self.status_text.text() != "Stopped":
            self.status_text.setText("Stopped")

    def _append_log(self, text: str) -> None:
        self.log_box.append(text)
        while self.log_box.document().blockCount() > nudge_logic.LOG_TRIM_LINES:
            cursor = self.log_box.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.select(cursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()

    def _on_activity_style_changed(self, value: str) -> None:
        natural = value == "natural"
        self.motion_pattern.setEnabled(not natural)
        self.rare_click.setEnabled(natural)
        self.rare_scroll.setEnabled(natural)

    def _sync_segment_style(self, idx: int) -> None:
        if idx == 0:
            self.control_btn.setObjectName("primaryButton")
            self.log_btn.setObjectName("secondaryButton")
        else:
            self.control_btn.setObjectName("secondaryButton")
            self.log_btn.setObjectName("primaryButton")
        self.control_btn.style().polish(self.control_btn)
        self.log_btn.style().polish(self.log_btn)

    def _apply_interval_preset(self, unit: str, value: str) -> None:
        self.interval_unit.setCurrentText(unit)
        self.interval_text.setText(value)

    def _refresh_schedule_hint(self) -> None:
        if not self.schedule_enabled.isChecked():
            self.schedule_hint.setText("Schedule summary: always on")
            return
        seg = self.schedule_segments.text().strip() or "09:00-18:00"
        weekend = "with weekends" if self.schedule_weekends.isChecked() else "weekdays only"
        cron = self.schedule_cron.text().strip()
        if cron:
            self.schedule_hint.setText(f"Schedule summary: {seg}, {weekend}, cron={cron}")
            return
        self.schedule_hint.setText(f"Schedule summary: {seg}, {weekend}")
