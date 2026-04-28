"""Dashboard page containing summary cards and an interactive pyqtgraph chart."""

from __future__ import annotations

import bisect

import pyqtgraph as pg
from pyqtgraph import PlotWidget
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

from components.stat_card import StatCard


class DashboardPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("pageRoot")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        cards_layout = QGridLayout()
        cards_layout.setHorizontalSpacing(12)
        cards_layout.setVerticalSpacing(12)

        cards_layout.addWidget(StatCard("Active Users", "12,480", "+8.4% from last week"), 0, 0)
        cards_layout.addWidget(StatCard("Conversion", "4.87%", "+0.6% from last week"), 0, 1)
        cards_layout.addWidget(StatCard("Open Tickets", "32", "-5 this week"), 0, 2)

        chart_panel = QFrame()
        chart_panel.setObjectName("chartPlaceholder")
        chart_layout = QVBoxLayout(chart_panel)
        chart_layout.setContentsMargins(18, 18, 18, 18)
        chart_layout.setSpacing(8)

        chart_title = QLabel("Weekly Performance")
        chart_title.setObjectName("sectionTitle")
        chart_hint = QLabel("Revenue and target trend over the last seven days (hover to inspect points).")
        chart_hint.setObjectName("mutedText")

        chart_view = self._build_interactive_chart()
        chart_layout.addWidget(chart_title)
        chart_layout.addWidget(chart_hint)
        chart_layout.addWidget(chart_view, 1)

        layout.addLayout(cards_layout)
        layout.addWidget(chart_panel, 1)

    def _build_interactive_chart(self) -> PlotWidget:
        self.days = [1, 2, 3, 4, 5, 6, 7]
        self.revenue_values = [72, 84, 78, 92, 105, 111, 126]
        self.target_values = [70, 75, 80, 85, 90, 95, 100]

        pg.setConfigOptions(antialias=True)
        chart = PlotWidget()
        chart.setObjectName("realChart")
        chart.setBackground((0, 0, 0, 0))

        chart.showGrid(x=True, y=True, alpha=0.25)
        chart.getAxis("bottom").setTextPen(pg.mkPen("#a6adc8"))
        chart.getAxis("left").setTextPen(pg.mkPen("#a6adc8"))
        chart.getAxis("bottom").setPen(pg.mkPen("#45475a"))
        chart.getAxis("left").setPen(pg.mkPen("#45475a"))
        chart.getAxis("bottom").setTicks([[(day, f"D{day}") for day in self.days]])
        chart.getAxis("left").setLabel("Revenue (K)", color="#a6adc8")
        chart.setMouseEnabled(x=True, y=False)
        chart.setMenuEnabled(False)
        chart.setYRange(60, 130, padding=0.05)
        chart.setXRange(1, 7, padding=0.05)

        chart.plot(
            self.days,
            self.revenue_values,
            pen=pg.mkPen("#89b4fa", width=3),
            symbol="o",
            symbolSize=8,
            symbolBrush="#89b4fa",
            name="Revenue",
        )
        chart.plot(
            self.days,
            self.target_values,
            pen=pg.mkPen(QColor("#a6adc8"), width=2, style=Qt.PenStyle.DashLine),
            symbol="t",
            symbolSize=7,
            symbolBrush="#a6adc8",
            name="Target",
        )
        self.revenue_highlight = pg.ScatterPlotItem(
            size=14,
            brush=pg.mkBrush("#89b4fa"),
            pen=pg.mkPen("#f5f7ff", width=1),
            symbol="o",
        )
        self.target_highlight = pg.ScatterPlotItem(
            size=13,
            brush=pg.mkBrush("#a6adc8"),
            pen=pg.mkPen("#f5f7ff", width=1),
            symbol="t",
        )
        chart.addItem(self.revenue_highlight)
        chart.addItem(self.target_highlight)
        self.revenue_highlight.hide()
        self.target_highlight.hide()

        legend = chart.addLegend(offset=(10, 10))
        legend.setBrush(pg.mkBrush(24, 24, 37, 180))
        legend.setPen(pg.mkPen("#313244"))

        self.crosshair_v = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#89b4fa", width=1))
        self.crosshair_h = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen("#89b4fa", width=1))
        chart.addItem(self.crosshair_v, ignoreBounds=True)
        chart.addItem(self.crosshair_h, ignoreBounds=True)

        self.tooltip_item = pg.TextItem(anchor=(0, 1), fill=pg.mkBrush(24, 24, 37, 230), color="#cdd6f4")
        chart.addItem(self.tooltip_item)
        self.tooltip_item.hide()
        self.tooltip_opacity = 0.0
        self._tooltip_target_opacity = 0.0
        self._tooltip_fade_step = 0.16
        self.tooltip_item.setOpacity(self.tooltip_opacity)
        self.tooltip_fade_timer = QTimer(self)
        self.tooltip_fade_timer.setInterval(16)
        self.tooltip_fade_timer.timeout.connect(self._tick_tooltip_fade)

        self._chart = chart
        self._proxy = pg.SignalProxy(chart.scene().sigMouseMoved, rateLimit=60, slot=self._handle_mouse_move)
        return chart

    def _handle_mouse_move(self, event) -> None:
        scene_pos = event[0]
        if not self._chart.sceneBoundingRect().contains(scene_pos):
            self._start_tooltip_fade(target_opacity=0.0)
            self.revenue_highlight.hide()
            self.target_highlight.hide()
            return

        mouse_point = self._chart.getPlotItem().vb.mapSceneToView(scene_pos)
        x_value = mouse_point.x()
        idx = bisect.bisect_left(self.days, x_value)
        idx = min(max(idx, 0), len(self.days) - 1)
        day = self.days[idx]
        revenue = self.revenue_values[idx]
        target = self.target_values[idx]

        self.crosshair_v.setPos(day)
        self.crosshair_h.setPos(revenue)
        self.revenue_highlight.setData([day], [revenue])
        self.target_highlight.setData([day], [target])
        self.revenue_highlight.show()
        self.target_highlight.show()
        self.tooltip_item.setHtml(
            f"<div style='padding:4px 6px;'>"
            f"<b>Day {day}</b><br/>Revenue: {revenue}K<br/>Target: {target}K"
            f"</div>"
        )
        self._place_tooltip(day, revenue)
        if not self.tooltip_item.isVisible():
            self.tooltip_opacity = 0.0
            self.tooltip_item.setOpacity(self.tooltip_opacity)
            self.tooltip_item.show()
        self._start_tooltip_fade(target_opacity=1.0)

    def _place_tooltip(self, x_value: float, y_value: float) -> None:
        view_box = self._chart.getPlotItem().vb
        (x_min, x_max), (y_min, y_max) = view_box.viewRange()
        pixel_size = view_box.viewPixelSize()

        rect = self.tooltip_item.boundingRect()
        tooltip_width = rect.width() * pixel_size[0]
        tooltip_height = rect.height() * pixel_size[1]

        margin_x = 0.15
        margin_y = 1.6

        x_offset = margin_x
        y_offset = margin_y

        if x_value + tooltip_width + margin_x > x_max:
            x_offset = -(tooltip_width + margin_x)
        if y_value + tooltip_height + margin_y > y_max:
            y_offset = -(tooltip_height + margin_y)
        if y_value + y_offset < y_min:
            y_offset = margin_y

        self.tooltip_item.setPos(x_value + x_offset, y_value + y_offset)

    def _tick_tooltip_fade(self) -> None:
        delta = self._tooltip_fade_step
        if self.tooltip_opacity < self._tooltip_target_opacity:
            self.tooltip_opacity = min(self._tooltip_target_opacity, self.tooltip_opacity + delta)
        else:
            self.tooltip_opacity = max(self._tooltip_target_opacity, self.tooltip_opacity - delta)
        self.tooltip_item.setOpacity(self.tooltip_opacity)
        if self.tooltip_opacity == self._tooltip_target_opacity:
            self.tooltip_fade_timer.stop()
            if self._tooltip_target_opacity == 0.0:
                self.tooltip_item.hide()

    def _start_tooltip_fade(self, target_opacity: float) -> None:
        self._tooltip_target_opacity = max(0.0, min(1.0, target_opacity))
        if self._tooltip_target_opacity > 0.0 and not self.tooltip_item.isVisible():
            self.tooltip_item.show()
        if not self.tooltip_fade_timer.isActive():
            self.tooltip_fade_timer.start()
