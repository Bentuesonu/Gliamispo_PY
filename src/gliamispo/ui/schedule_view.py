from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QLabel,
)
from PyQt6.QtCore import Qt


class ScheduleView(QWidget):
    def __init__(self, container, parent=None):
        super().__init__(parent)
        self._container = container
        self._project_id = None

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            ["Giorno", "Posizione", "Scena", "Location", "INT/EXT", "Durata (ore)"]
        )

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Schedule"))
        layout.addWidget(self._table)

    def load_schedule(self, project_id):
        self._project_id = project_id
        rows = self._container.database.execute(
            "SELECT se.shooting_day, se.position, s.scene_number, "
            "s.location, s.int_ext, s.manual_shooting_hours "
            "FROM schedule_entries se "
            "JOIN scenes s ON se.scene_id = s.id "
            "WHERE se.project_id = ? "
            "ORDER BY se.shooting_day, se.position",
            (project_id,)
        ).fetchall()
        self._table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, val in enumerate(r):
                item = QTableWidgetItem(str(val) if val is not None else "")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._table.setItem(i, j, item)

    def clear(self):
        self._project_id = None
        self._table.setRowCount(0)
