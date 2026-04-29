"""Analytics page with trigger chart and summaries."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from mouse_jiggler import analytics_store


class TasksPage(QWidget):
    """Kept class name for compatibility; acts as Analytics page."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("pageRoot")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)
        cards_row.addWidget(self._build_summary_card(), 2)
        cards_row.addWidget(self._build_pattern_card(), 2)
        root.addLayout(cards_row)

        chart_meta_card = QFrame()
        chart_meta_card.setObjectName("chartPlaceholder")
        chart_layout = QVBoxLayout(chart_meta_card)
        chart_layout.setContentsMargins(16, 16, 16, 16)
        chart_layout.setSpacing(10)

        # Keep title/hint in a dedicated header block to avoid overlap with the plot area.
        chart_header = QFrame()
        chart_header.setObjectName("analyticsHeader")
        header_layout = QVBoxLayout(chart_header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)

        chart_title = QLabel("觸發次數")
        chart_title.setObjectName("sectionTitle")
        chart_font = self._preferred_cjk_font(point_size=16, bold=True)
        if chart_font is not None:
            chart_title.setFont(chart_font)
        header_layout.addWidget(chart_title)
        self.chart_hint = QLabel("資料來源為本機 analytics.json 下方紀錄與首頁紀錄同步")
        self.chart_hint.setObjectName("analyticsHint")
        self.chart_hint.setWordWrap(True)
        self.chart_hint.setTextFormat(Qt.TextFormat.PlainText)
        hint_font = self._preferred_cjk_font(point_size=12, bold=False)
        if hint_font is not None:
            self.chart_hint.setFont(hint_font)
        self.chart_hint.setMinimumHeight(22)
        header_layout.addWidget(self.chart_hint)
        chart_layout.addWidget(chart_header, 0)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        self.btn_today = QPushButton("今日")
        self.btn_today.setMinimumHeight(34)
        self.btn_today.setObjectName("primaryButton")
        self.btn_last7 = QPushButton("最近 7 天")
        self.btn_last7.setMinimumHeight(34)
        self.btn_last7.setObjectName("secondaryButton")
        self.btn_today.clicked.connect(lambda: self._set_trigger_mode(0))
        self.btn_last7.clicked.connect(lambda: self._set_trigger_mode(1))
        mode_row.addWidget(self.btn_today)
        mode_row.addWidget(self.btn_last7)
        mode_row.addStretch(1)
        chart_layout.addLayout(mode_row)
        root.addWidget(chart_meta_card, 0)

        chart_plot_card = QFrame()
        chart_plot_card.setObjectName("chartPlaceholder")
        chart_plot_layout = QVBoxLayout(chart_plot_card)
        chart_plot_layout.setContentsMargins(16, 12, 16, 16)
        chart_plot_layout.setSpacing(0)
        pg.setConfigOptions(antialias=True)
        self.trigger_plot = pg.PlotWidget()
        self.trigger_plot.setObjectName("triggerPlot")
        self.trigger_plot.setBackground("#24273a")
        self.trigger_plot.showGrid(x=True, y=True, alpha=0.25)
        self.trigger_plot.setMinimumHeight(220)
        chart_plot_layout.addWidget(self.trigger_plot, 1)
        root.addWidget(chart_plot_card, 2)

        details_card = QFrame()
        details_card.setObjectName("chartPlaceholder")
        details_layout = QVBoxLayout(details_card)
        details_layout.setContentsMargins(16, 16, 16, 16)
        details_layout.setSpacing(10)
        self.refresh_btn = QPushButton("Refresh analytics")
        self.refresh_btn.setObjectName("secondaryButton")
        self.refresh_btn.clicked.connect(self.refresh_analytics)
        details_layout.addWidget(self.refresh_btn)
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        details_layout.addWidget(self.details, 1)
        root.addWidget(details_card, 1)

        self._days: dict[str, dict] = {}
        self._trigger_mode = 0
        self.refresh_analytics()

    def _preferred_cjk_font(self, point_size: int, *, bold: bool) -> QFont | None:
        families = set(QFontDatabase.families())
        for name in (
            "Microsoft JhengHei",
            "Microsoft YaHei",
            "Noto Sans CJK TC",
            "PingFang TC",
            "Heiti TC",
        ):
            if name in families:
                f = QFont(name, point_size)
                f.setBold(bold)
                return f
        return None

    def _build_summary_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("settingsPanel")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        title = QLabel("Analytics")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        form = QFormLayout()
        self.total = QLabel("-")
        self.today = QLabel("-")
        self.runtime = QLabel("-")
        form.addRow("Total nudges", self.total)
        form.addRow("Today nudges", self.today)
        form.addRow("Runtime (14d)", self.runtime)
        layout.addLayout(form)
        return card

    def _build_pattern_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("settingsPanel")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        title = QLabel("Path usage")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        form = QFormLayout()
        self.p_horizontal = QLabel("-")
        self.p_circle = QLabel("-")
        self.p_square = QLabel("-")
        self.p_natural = QLabel("-")
        form.addRow("Horizontal", self.p_horizontal)
        form.addRow("Circle", self.p_circle)
        form.addRow("Square", self.p_square)
        form.addRow("Natural", self.p_natural)
        layout.addLayout(form)
        return card

    def refresh_analytics(self) -> None:
        self._days = analytics_store.load_days_copy()
        keys = sorted(self._days.keys())
        today_key = datetime.now().date().isoformat()
        total = 0
        today = 0
        runtime = 0.0
        pattern = {"horizontal": 0, "circle": 0, "square": 0, "natural": 0}
        lines: list[str] = []

        for k in keys:
            day = self._days.get(k, {})
            hourly = day.get("hourly_nudges", [0] * 24)
            count = sum(int(v) for v in hourly) if isinstance(hourly, list) else 0
            total += count
            if k == today_key:
                today = count
            pat = day.get("pattern", {})
            if isinstance(pat, dict):
                for pk in pattern:
                    pattern[pk] += int(pat.get(pk, 0) or 0)

        for k in keys[-14:]:
            day = self._days.get(k, {})
            day_runtime = float(day.get("runtime_sec", 0.0) or 0.0)
            runtime += day_runtime
            hourly = day.get("hourly_nudges", [0] * 24)
            count = sum(int(v) for v in hourly) if isinstance(hourly, list) else 0
            lines.append(f"{k}: nudges={count}, runtime={day_runtime/60.0:.1f}m")

        self.total.setText(str(total))
        self.today.setText(str(today))
        self.runtime.setText(f"{runtime / 60.0:.1f} min")
        self.p_horizontal.setText(str(pattern["horizontal"]))
        self.p_circle.setText(str(pattern["circle"]))
        self.p_square.setText(str(pattern["square"]))
        self.p_natural.setText(str(pattern["natural"]))
        self.details.setPlainText("\n".join(lines) if lines else "No data.")
        self._render_trigger_chart()

    def _render_trigger_chart(self) -> None:
        self.trigger_plot.clear()
        if self._trigger_mode == 0:
            self._render_today_hourly()
            return
        self._render_last_7_days()

    def _set_trigger_mode(self, mode: int) -> None:
        self._trigger_mode = 0 if mode == 0 else 1
        if self._trigger_mode == 0:
            self.btn_today.setObjectName("primaryButton")
            self.btn_last7.setObjectName("secondaryButton")
        else:
            self.btn_today.setObjectName("secondaryButton")
            self.btn_last7.setObjectName("primaryButton")
        self.btn_today.style().polish(self.btn_today)
        self.btn_last7.style().polish(self.btn_last7)
        self._render_trigger_chart()

    def _render_today_hourly(self) -> None:
        today_key = datetime.now().date().isoformat()
        day = self._days.get(today_key, {})
        hourly = day.get("hourly_nudges", [0] * 24)
        if not isinstance(hourly, list) or len(hourly) != 24:
            hourly = [0] * 24
        xs = list(range(24))
        ys = [int(v) for v in hourly]
        self.trigger_plot.setLabel("left", "Nudges")
        self.trigger_plot.setLabel("bottom", "Hour")
        self.trigger_plot.plot(
            xs,
            ys,
            pen=pg.mkPen("#89b4fa", width=2),
            symbol="o",
            symbolSize=5,
            symbolBrush="#89b4fa",
        )
        self.trigger_plot.getAxis("bottom").setTicks([[(0, "0"), (6, "6"), (12, "12"), (18, "18"), (23, "23")]])
        self.trigger_plot.setXRange(-0.5, 23.5, padding=0)
        ymax = max(ys) if ys else 0
        self.trigger_plot.setYRange(0, max(1, int(ymax * 1.2) + 1), padding=0)

    def _render_last_7_days(self) -> None:
        today = date.today()
        xs = list(range(7))
        labels: list[tuple[int, str]] = []
        ys: list[int] = []
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            key = d.isoformat()
            day = self._days.get(key, {})
            hourly = day.get("hourly_nudges", [0] * 24)
            count = sum(int(v) for v in hourly) if isinstance(hourly, list) else 0
            ys.append(count)
            labels.append((6 - i, d.strftime("%m-%d")))
        bars = pg.BarGraphItem(x=xs, height=ys, width=0.65, brush="#89b4fa", pen=pg.mkPen("#313244"))
        self.trigger_plot.addItem(bars)
        self.trigger_plot.setLabel("left", "Nudges")
        self.trigger_plot.setLabel("bottom", "Day")
        self.trigger_plot.getAxis("bottom").setTicks([labels])
        self.trigger_plot.setXRange(-0.5, 6.5, padding=0)
        ymax = max(ys) if ys else 0
        self.trigger_plot.setYRange(0, max(1, int(ymax * 1.2) + 1), padding=0)
