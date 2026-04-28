"""Task table with preset style and data model."""

from __future__ import annotations

from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem


class TaskTable(QTableWidget):
    def __init__(self) -> None:
        super().__init__(0, 3)
        self.setHorizontalHeaderLabels(["Task", "Owner", "Status"])
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setAlternatingRowColors(True)
        self.setObjectName("taskTable")

        self._seed_rows()

    def _seed_rows(self) -> None:
        for task, owner, status in [
            ("Review onboarding flow", "Alicia", "In Progress"),
            ("Prepare release notes", "Jordan", "Done"),
            ("Refactor notification service", "Maya", "Todo"),
            ("Validate payment retry UX", "Lucas", "In QA"),
        ]:
            self.add_task(task, owner, status)

    def add_task(self, task: str, owner: str, status: str) -> None:
        row = self.rowCount()
        self.insertRow(row)
        self.setItem(row, 0, QTableWidgetItem(task))
        self.setItem(row, 1, QTableWidgetItem(owner))
        self.setItem(row, 2, QTableWidgetItem(status))

    def remove_selected_task(self) -> None:
        selected = self.selectionModel().selectedRows()
        if not selected:
            return
        self.removeRow(selected[0].row())
