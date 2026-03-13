from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QHBoxLayout, QComboBox,
)
from PyQt6.QtCore import Qt


class CallSheetView(QWidget):
    def __init__(self, container, parent=None):
        super().__init__(parent)
        self._container = container
        self._project_id = None

        self._date_combo = QComboBox()
        self._date_combo.currentTextChanged.connect(self._on_date_changed)

        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Giorno:"))
        header_layout.addWidget(self._date_combo)
        header_layout.addStretch()

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["Scena", "Location", "INT/EXT", "Giorno/Notte", "Ore"]
        )

        layout = QVBoxLayout(self)
        layout.addLayout(header_layout)
        layout.addWidget(self._table)

    def load_project(self, project_id):
        self._project_id = project_id
        rows = self._container.database.execute(
            "SELECT DISTINCT shooting_day FROM schedule_entries "
            "WHERE project_id = ? ORDER BY shooting_day",
            (project_id,)
        ).fetchall()
        self._date_combo.blockSignals(True)
        self._date_combo.clear()
        for r in rows:
            self._date_combo.addItem(str(r[0]))
        self._date_combo.blockSignals(False)
        if self._date_combo.count():
            self._load_for_day(self._date_combo.currentText())

    def _on_date_changed(self, day):
        if day:
            self._load_for_day(day)

    def _load_for_day(self, day):
        if self._project_id is None:
            return
        rows = self._container.database.execute(
            "SELECT s.scene_number, s.location, s.int_ext, s.day_night, "
            "s.manual_shooting_hours "
            "FROM schedule_entries se "
            "JOIN scenes s ON se.scene_id = s.id "
            "WHERE se.project_id = ? AND se.shooting_day = ? "
            "ORDER BY se.position",
            (self._project_id, day)
        ).fetchall()
        self._table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, val in enumerate(r):
                item = QTableWidgetItem(str(val) if val is not None else "")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._table.setItem(i, j, item)

    def clear(self):
        self._project_id = None
        self._date_combo.clear()
        self._table.setRowCount(0)
