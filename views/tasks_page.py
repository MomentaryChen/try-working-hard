"""Tasks page with table and simple actions."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from components.custom_table import TaskTable


class TasksPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("pageRoot")
        self._new_task_index = 1

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        actions = QHBoxLayout()
        actions.setSpacing(10)

        self.add_button = QPushButton("Add Task")
        self.add_button.setObjectName("primaryButton")
        self.add_button.setCursor(Qt.PointingHandCursor)

        self.remove_button = QPushButton("Remove Selected")
        self.remove_button.setObjectName("secondaryButton")
        self.remove_button.setCursor(Qt.PointingHandCursor)

        actions.addWidget(self.add_button)
        actions.addWidget(self.remove_button)
        actions.addStretch(1)

        self.table = TaskTable()

        layout.addLayout(actions)
        layout.addWidget(self.table, 1)

        self.add_button.clicked.connect(self.add_task)
        self.remove_button.clicked.connect(self.remove_selected_task)

    def add_task(self) -> None:
        task_name = f"New Task #{self._new_task_index}"
        self.table.add_task(task_name, "You", "Todo")
        self._new_task_index += 1

    def remove_selected_task(self) -> bool:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return False
        self.table.remove_selected_task()
        return True
