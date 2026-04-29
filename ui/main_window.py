"""Main dashboard window shell with routing and themed layout."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, QTimer, Qt
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from components.one_time_reminder_dialog import OneTimeReminderDialog
from components.sidebar_button import SidebarButton
from components.toast import Toast
from ui.preferences_store import PreferencesStore
from ui.view_model import NavigationViewModel
from views.dashboard_page import DashboardPage
from views.settings_page import SettingsPage
from views.tasks_page import TasksPage

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("try-working-hard")
        self.resize(1200, 760)
        self.setMinimumSize(960, 620)

        self.view_model = NavigationViewModel()
        self.sidebar_buttons: dict[str, SidebarButton] = {}
        self.page_index = {"home": 0, "settings": 1, "analytics": 2}
        self._indicator_ready = False
        self.preferences = PreferencesStore()
        self.shortcuts: list[QShortcut] = []

        self._setup_ui()
        self._apply_styles()
        self._setup_shortcuts()

        self.view_model.page_changed.connect(self._on_page_changed)
        self._set_active_button("home")
        QTimer.singleShot(0, lambda: self._set_indicator_position("home", animate=False))
        QTimer.singleShot(250, self._show_first_run_reminder)

    def _setup_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)

        app_layout = QHBoxLayout(root)
        app_layout.setContentsMargins(0, 0, 0, 0)
        app_layout.setSpacing(0)

        sidebar = self._build_sidebar()
        content_shell = self._build_content_shell()

        app_layout.addWidget(sidebar)
        app_layout.addWidget(content_shell, 1)

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 16, 14, 16)
        layout.setSpacing(8)

        logo = QLabel("try-working-hard")
        logo.setObjectName("brandLabel")
        layout.addWidget(logo)
        layout.addSpacing(12)

        self.nav_container = QFrame()
        self.nav_container.setObjectName("sidebarNavContainer")
        nav_layout = QVBoxLayout(self.nav_container)
        nav_layout.setContentsMargins(8, 6, 8, 6)
        nav_layout.setSpacing(8)

        self.sidebar_indicator = QFrame(self.nav_container)
        self.sidebar_indicator.setObjectName("sidebarIndicator")
        self.sidebar_indicator.setGeometry(QRect(2, 8, 4, 30))
        self.sidebar_indicator_animation = QPropertyAnimation(self.sidebar_indicator, b"geometry", self)
        self.sidebar_indicator_animation.setDuration(220)
        self.sidebar_indicator_animation.setEasingCurve(QEasingCurve.OutCubic)

        icon_root = Path(__file__).resolve().parents[1] / "assets" / "icons"
        for key, label, icon in [
            ("home", "Home", icon_root / "dashboard.svg"),
            ("settings", "Settings", icon_root / "settings.svg"),
            ("analytics", "Analytics", icon_root / "tasks.svg"),
        ]:
            button = SidebarButton(label, key, QIcon(str(icon)))
            button.clicked_with_key.connect(self.view_model.set_active_page)
            nav_layout.addWidget(button)
            self.sidebar_buttons[key] = button

        nav_layout.addStretch(1)
        layout.addWidget(self.nav_container, 1)
        layout.addStretch(1)
        return sidebar

    def _build_content_shell(self) -> QWidget:
        shell = QWidget()
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(20, 18, 20, 18)
        shell_layout.setSpacing(12)

        header = QFrame()
        header.setObjectName("header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 12, 16, 12)
        header_layout.setSpacing(10)

        self.page_title = QLabel("Home")
        self.page_title.setObjectName("pageTitle")
        header_layout.addWidget(self.page_title)
        header_layout.addStretch(1)

        avatar = QPushButton("VC")
        avatar.setObjectName("avatarButton")
        avatar.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        header_layout.addWidget(avatar)

        self.stack = QStackedWidget()
        self.dashboard_page = DashboardPage()
        self.settings_page = SettingsPage()
        self.tasks_page = TasksPage()

        self.stack.addWidget(self.dashboard_page)
        self.stack.addWidget(self.settings_page)
        self.stack.addWidget(self.tasks_page)
        self.toast = Toast(shell)
        self.settings_page.reset_reminders_requested.connect(self._reset_one_time_reminders)
        self.settings_page.settings_saved.connect(self.toast.show_message)

        self.opacity_effect = QGraphicsOpacityEffect(self.stack)
        self.stack.setGraphicsEffect(self.opacity_effect)
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity", self)
        self.fade_animation.setDuration(180)
        self.fade_animation.setStartValue(0.75)
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.setEasingCurve(QEasingCurve.OutCubic)

        shell_layout.addWidget(header)
        shell_layout.addWidget(self.stack, 1)

        return shell

    def _on_page_changed(self, page_key: str) -> None:
        self._set_active_button(page_key)
        self.stack.setCurrentIndex(self.page_index[page_key])
        page_titles = {"home": "Home", "settings": "Settings", "analytics": "Analytics"}
        self.page_title.setText(page_titles.get(page_key, page_key.capitalize()))
        self.fade_animation.stop()
        self.fade_animation.start()
        self._set_indicator_position(page_key, animate=True)

    def _set_active_button(self, page_key: str) -> None:
        for key, button in self.sidebar_buttons.items():
            button.setChecked(key == page_key)

    def _set_indicator_position(self, page_key: str, animate: bool) -> None:
        target_button = self.sidebar_buttons.get(page_key)
        if target_button is None:
            return
        target_rect = target_button.geometry()
        indicator_height = max(24, target_rect.height() - 10)
        y = target_rect.y() + (target_rect.height() - indicator_height) // 2
        end_rect = QRect(2, y, 4, indicator_height)

        if animate and self._indicator_ready:
            self.sidebar_indicator_animation.stop()
            self.sidebar_indicator_animation.setStartValue(self.sidebar_indicator.geometry())
            self.sidebar_indicator_animation.setEndValue(end_rect)
            self.sidebar_indicator_animation.start()
        else:
            self.sidebar_indicator.setGeometry(end_rect)
            self._indicator_ready = True

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        self._set_indicator_position(self.view_model.active_page, animate=False)
        if hasattr(self, "toast"):
            self.toast._layout_toast()

    def _apply_styles(self) -> None:
        styles_path = Path(__file__).resolve().parents[1] / "styles" / "styles.qss"
        self.setStyleSheet(styles_path.read_text(encoding="utf-8"))

    def _setup_shortcuts(self) -> None:
        self._add_shortcut("Ctrl+1", lambda: self.view_model.set_active_page("home"))
        self._add_shortcut("Ctrl+2", lambda: self.view_model.set_active_page("settings"))
        self._add_shortcut("Ctrl+3", lambda: self.view_model.set_active_page("analytics"))
        self._add_shortcut("Ctrl+N", self._refresh_analytics_with_feedback)
        self._add_shortcut("Delete", self._refresh_analytics_with_feedback)
        self._add_shortcut("?", self._show_shortcuts_hint)
        self._add_shortcut("F1", self._show_shortcuts_hint)
        self._add_shortcut("F2", lambda: self.view_model.set_active_page("home"))
        self._add_shortcut("F3", lambda: self.view_model.set_active_page("settings"))
        self._add_shortcut("F4", lambda: self.view_model.set_active_page("analytics"))
        self._add_shortcut("F5", self._start_from_shortcut)
        self._add_shortcut("Shift+F5", self._stop_from_shortcut)
        self._add_shortcut("F6", self._toggle_home_segment)
        self._add_shortcut("Return", self._start_from_shortcut)
        self._add_shortcut("Escape", self._stop_from_shortcut)

    def _add_shortcut(self, key: str, handler) -> None:
        shortcut = QShortcut(QKeySequence(key), self)
        shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        shortcut.activated.connect(handler)
        self.shortcuts.append(shortcut)

    def _refresh_analytics_with_feedback(self) -> None:
        self.view_model.set_active_page("analytics")
        self.tasks_page.refresh_analytics()
        self.toast.show_message("Analytics refreshed.")

    def _show_shortcuts_hint(self) -> None:
        self.toast.show_message("F2/F3/F4 pages, F5 start, F6 Home Control/Log, Ctrl+N refresh analytics.")

    def _start_from_shortcut(self) -> None:
        if self.view_model.active_page != "home":
            self.view_model.set_active_page("home")
        self.dashboard_page.start_runtime()

    def _toggle_home_segment(self) -> None:
        if self.view_model.active_page != "home":
            self.view_model.set_active_page("home")
        idx = self.dashboard_page.stack.currentIndex()
        self.dashboard_page.stack.setCurrentIndex(1 - idx)

    def _stop_from_shortcut(self) -> None:
        if self.view_model.active_page != "home":
            self.view_model.set_active_page("home")
        self.dashboard_page.stop_runtime()

    def _show_first_run_reminder(self) -> None:
        reminder_key = "dashboard_shortcuts"
        if not self.preferences.should_show_reminder(reminder_key):
            return
        reminder = OneTimeReminderDialog(
            title="Quick Productivity Tip",
            message=(
                "Use F2/F3/F4 to switch Home/Settings/Analytics, F5/Shift+F5 to start or stop, "
                "and F6 to switch Home Control/Log."
            ),
            parent=self,
        )
        reminder.exec()
        if reminder.dont_show_again.isChecked():
            self.preferences.remember_dismissed(reminder_key)
            self.toast.show_message("This reminder will not be shown again.")

    def _reset_one_time_reminders(self) -> None:
        self.preferences.reset_reminders()
        self.toast.show_message("One-time reminders reset.")

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self.dashboard_page.stop_runtime()
        super().closeEvent(event)
