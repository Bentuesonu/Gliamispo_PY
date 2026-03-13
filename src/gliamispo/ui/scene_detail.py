from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLabel,
    QTableWidget, QTableWidgetItem, QGroupBox,
)
from PyQt6.QtCore import Qt


class SceneDetail(QWidget):
    def __init__(self, container, parent=None):
        super().__init__(parent)
        self._container = container
        self._scene_id = None

        self._scene_number_label = QLabel("—")
        self._location_label = QLabel("—")
        self._int_ext_label = QLabel("—")
        self._day_night_label = QLabel("—")
        self._synopsis_label = QLabel("—")
        self._synopsis_label.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Scena:", self._scene_number_label)
        form.addRow("Location:", self._location_label)
        form.addRow("INT/EXT:", self._int_ext_label)
        form.addRow("Giorno/Notte:", self._day_night_label)
        form.addRow("Sinossi:", self._synopsis_label)

        scene_group = QGroupBox("Dettaglio Scena")
        scene_group.setLayout(form)

        self._elements_table = QTableWidget(0, 4)
        self._elements_table.setHorizontalHeaderLabels(
            ["Categoria", "Elemento", "Quantità", "Note"]
        )

        elements_layout = QVBoxLayout()
        elements_layout.addWidget(self._elements_table)
        elements_group = QGroupBox("Elementi Breakdown")
        elements_group.setLayout(elements_layout)

        layout = QVBoxLayout(self)
        layout.addWidget(scene_group)
        layout.addWidget(elements_group)

    def load_scene(self, scene_id):
        self._scene_id = scene_id
        row = self._container.database.execute(
            "SELECT scene_number, location, int_ext, day_night, synopsis "
            "FROM scenes WHERE id = ?", (scene_id,)
        ).fetchone()
        if not row:
            return
        self._scene_number_label.setText(row[0] or "—")
        self._location_label.setText(row[1] or "—")
        self._int_ext_label.setText(row[2] or "—")
        self._day_night_label.setText(row[3] or "—")
        self._synopsis_label.setText(row[4] or "—")
        self._load_elements(scene_id)

    def _load_elements(self, scene_id):
        rows = self._container.database.execute(
            "SELECT category, element_name, quantity, notes "
            "FROM scene_elements WHERE scene_id = ? ORDER BY category, element_name",
            (scene_id,)
        ).fetchall()
        self._elements_table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, val in enumerate(r):
                item = QTableWidgetItem(str(val) if val is not None else "")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._elements_table.setItem(i, j, item)

    def clear(self):
        self._scene_id = None
        self._scene_number_label.setText("—")
        self._location_label.setText("—")
        self._int_ext_label.setText("—")
        self._day_night_label.setText("—")
        self._synopsis_label.setText("—")
        self._elements_table.setRowCount(0)
