# src/gliamispo/ui/shot_list_view.py
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QDialog, QFormLayout, QComboBox, QLineEdit, QSpinBox,
    QTextEdit, QDialogButtonBox, QLabel,
)
from PySide6.QtCore import Qt
from gliamispo.ui import theme

SHOT_TYPES = [
    'MASTER', 'MCU', 'CU', 'ECU', 'OTS',
    'INSERT', 'WIDE', 'TWO_SHOT', 'POV', 'CUTAWAY',
]
CAMERA_MOVEMENTS = [
    'STATICO', 'DOLLY', 'STEADICAM', 'DRONE',
    'HANDHELD', 'CRANE', 'ZOOM',
]


class ShotListView(QWidget):
    def __init__(self, container, parent=None):
        super().__init__(parent)
        self._container        = container
        self._project_id       = None
        self._current_scene_id = None
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._scene_panel = self._build_scene_panel()
        self._shot_panel  = self._build_shot_panel()
        layout.addWidget(self._scene_panel, 1)
        layout.addWidget(self._shot_panel, 2)

    def _build_scene_panel(self):
        panel  = QWidget()
        panel.setStyleSheet(f"background-color: {theme.BG1.name()};")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(16, 12, 16, 8)

        lbl = QLabel("SCENE")
        lbl.setFont(theme.font_ui(9, bold=True))
        lbl.setStyleSheet(f"color: {theme.TEXT3.name()};")
        h_layout.addWidget(lbl)
        h_layout.addStretch()
        layout.addWidget(header)

        self._scene_list = QListWidget()
        self._scene_list.currentRowChanged.connect(self._on_scene_selected)
        self._scene_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {theme.BG1.name()};
                border: none;
                outline: none;
            }}
            QListWidget::item {{
                padding: 8px 16px;
                border-bottom: 1px solid {theme.qss_color(theme.BD1)};
                color: {theme.TEXT1.name()};
            }}
            QListWidget::item:selected {{
                background-color: {theme.BG0.name()};
                color: {theme.TEXT0.name()};
            }}
            QListWidget::item:hover {{
                background-color: {theme.BG0.name()};
            }}
        """)
        layout.addWidget(self._scene_list, 1)
        return panel

    def _build_shot_panel(self):
        panel  = QWidget()
        panel.setStyleSheet(f"background-color: {theme.BG0.name()};")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QWidget()
        toolbar.setStyleSheet(f"background-color: {theme.BG2.name()};")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(16, 8, 16, 8)

        shots_label = QLabel("SHOT LIST")
        shots_label.setFont(theme.font_ui(9, bold=True))
        shots_label.setStyleSheet(f"color: {theme.TEXT3.name()};")
        tb_layout.addWidget(shots_label)
        tb_layout.addStretch()

        self._add_shot_btn = QPushButton("+ Aggiungi Shot")
        self._add_shot_btn.setFont(theme.font_ui(10))
        self._add_shot_btn.setEnabled(False)
        self._add_shot_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_shot_btn.setStyleSheet(f"""
            QPushButton {{
                color: {theme.GOLD.name()};
                background-color: {theme.qss_color(theme.GOLD_BG)};
                border: 1.5px solid {theme.qss_color(theme.GOLD_BD)};
                border-radius: 6px;
                padding: 6px 14px;
            }}
            QPushButton:hover {{
                background-color: {theme.qss_color(theme.GOLD_BD)};
            }}
            QPushButton:disabled {{
                color: {theme.TEXT4.name()};
                background-color: transparent;
                border-color: {theme.qss_color(theme.BD1)};
            }}
        """)
        self._add_shot_btn.clicked.connect(self._on_add_shot)
        tb_layout.addWidget(self._add_shot_btn)
        layout.addWidget(toolbar)

        self._shot_table = QTableWidget()
        self._shot_table.setColumnCount(5)
        self._shot_table.setHorizontalHeaderLabels(
            ["Shot", "Tipo", "Obiettivo mm", "Movimento", "Descrizione"])
        self._shot_table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Stretch)
        self._shot_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self._shot_table.doubleClicked.connect(self._on_shot_double_clicked)
        self._shot_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {theme.BG1.name()};
                border: none;
                gridline-color: {theme.qss_color(theme.BD1)};
            }}
            QTableWidget::item {{
                padding: 6px 8px;
                color: {theme.TEXT1.name()};
            }}
            QTableWidget::item:selected {{
                background-color: {theme.qss_color(theme.GOLD_BG)};
                color: {theme.TEXT0.name()};
            }}
            QHeaderView::section {{
                background-color: {theme.BG3.name()};
                color: {theme.TEXT2.name()};
                font-weight: bold;
                font-size: 11px;
                padding: 8px 6px;
                border: none;
                border-bottom: 1px solid {theme.qss_color(theme.BD2)};
            }}
        """)
        layout.addWidget(self._shot_table, 1)
        return panel

    # ── Caricamento ──────────────────────────────────────────────────

    def load_project(self, project_id: int):
        self._project_id = project_id
        self._load_scenes()

    def _load_scenes(self):
        self._scene_list.clear()
        self._shot_table.setRowCount(0)
        self._current_scene_id = None
        if self._project_id is None:
            return
        rows = self._container.database.execute(
            "SELECT id, scene_number, location, int_ext, day_night "
            "FROM scenes WHERE project_id = ? ORDER BY scene_number",
            (self._project_id,)
        ).fetchall()
        for row in rows:
            label = f"{row[1]}  {row[2]} {row[3]} {row[4]}"
            item  = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, row[0])  # scene_id
            self._scene_list.addItem(item)

    def _on_scene_selected(self, idx):
        item = self._scene_list.item(idx)
        if item is None:
            return
        self._current_scene_id = item.data(Qt.ItemDataRole.UserRole)
        self._add_shot_btn.setEnabled(True)
        self._load_shots()

    def _load_shots(self):
        self._shot_table.setRowCount(0)
        if self._current_scene_id is None:
            return
        rows = self._container.database.execute(
            "SELECT id, shot_number, shot_type, lens_mm, "
            "camera_movement, description "
            "FROM shot_list WHERE scene_id = ? ORDER BY position, id",
            (self._current_scene_id,)
        ).fetchall()
        for r in rows:
            row_idx = self._shot_table.rowCount()
            self._shot_table.insertRow(row_idx)
            self._shot_table.setItem(row_idx, 0, QTableWidgetItem(r[1] or ""))
            self._shot_table.setItem(row_idx, 1, QTableWidgetItem(r[2] or ""))
            self._shot_table.setItem(row_idx, 2,
                QTableWidgetItem(str(r[3]) if r[3] else ""))
            self._shot_table.setItem(row_idx, 3, QTableWidgetItem(r[4] or ""))
            self._shot_table.setItem(row_idx, 4, QTableWidgetItem(r[5] or ""))
            # salva shot_id nella prima cella per recuperarlo al doppio click
            self._shot_table.item(row_idx, 0).setData(
                Qt.ItemDataRole.UserRole, r[0])

    # ── Aggiunta / modifica shot ──────────────────────────────────────

    def _on_add_shot(self):
        if self._current_scene_id is None:
            return
        dlg = _ShotDialog(parent=self)
        if dlg.exec():
            data = dlg.get_data()
            pos  = self._shot_table.rowCount()
            self._container.database.execute(
                "INSERT INTO shot_list "
                "(scene_id, shot_number, shot_type, lens_mm, "
                " camera_movement, description, position) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (self._current_scene_id,
                 data["shot_number"], data["shot_type"],
                 data["lens_mm"],     data["camera_movement"],
                 data["description"], pos)
            )
            self._container.database.commit()
            self._load_shots()

    def _on_shot_double_clicked(self, index):
        row  = index.row()
        item = self._shot_table.item(row, 0)
        if item is None:
            return
        shot_id = item.data(Qt.ItemDataRole.UserRole)
        if shot_id is None:
            return
        row_data = self._container.database.execute(
            "SELECT shot_number, shot_type, lens_mm, "
            "camera_movement, description, setup_notes "
            "FROM shot_list WHERE id = ?",
            (shot_id,)
        ).fetchone()
        if not row_data:
            return
        dlg = _ShotDialog(
            shot_data={
                "shot_number":     row_data[0],
                "shot_type":       row_data[1],
                "lens_mm":         row_data[2],
                "camera_movement": row_data[3],
                "description":     row_data[4],
                "setup_notes":     row_data[5],
            },
            parent=self
        )
        if dlg.exec():
            data = dlg.get_data()
            self._container.database.execute(
                "UPDATE shot_list SET shot_number=?, shot_type=?, "
                "lens_mm=?, camera_movement=?, description=? "
                "WHERE id=?",
                (data["shot_number"], data["shot_type"],
                 data["lens_mm"],     data["camera_movement"],
                 data["description"], shot_id)
            )
            self._container.database.commit()
            self._load_shots()

    def clear(self):
        self._project_id       = None
        self._current_scene_id = None
        self._scene_list.clear()
        self._shot_table.setRowCount(0)
        self._add_shot_btn.setEnabled(False)


class _ShotDialog(QDialog):
    def __init__(self, shot_data=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Shot")
        self.setMinimumWidth(360)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {theme.BG1.name()};
            }}
            QLabel {{
                color: {theme.TEXT1.name()};
            }}
            QLineEdit, QSpinBox, QComboBox, QTextEdit {{
                background-color: {theme.BG0.name()};
                border: 1px solid {theme.qss_color(theme.BD1)};
                border-radius: 4px;
                padding: 6px 8px;
                color: {theme.TEXT0.name()};
            }}
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QTextEdit:focus {{
                border-color: {theme.GOLD.name()};
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 8px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {theme.BG0.name()};
                border: 1px solid {theme.qss_color(theme.BD2)};
                selection-background-color: {theme.qss_color(theme.GOLD_BG)};
                selection-color: {theme.TEXT0.name()};
                color: {theme.TEXT1.name()};
                padding: 4px;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 6px 8px;
                color: {theme.TEXT1.name()};
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {theme.BG2.name()};
                color: {theme.TEXT0.name()};
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: {theme.qss_color(theme.GOLD_BG)};
                color: {theme.TEXT0.name()};
            }}
            QPushButton {{
                background-color: {theme.qss_color(theme.GOLD_BG)};
                color: {theme.GOLD.name()};
                border: 1px solid {theme.qss_color(theme.GOLD_BD)};
                border-radius: 4px;
                padding: 6px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {theme.qss_color(theme.GOLD_BD)};
            }}
        """)
        form = QFormLayout(self)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(12)

        self._shot_number = QLineEdit(
            shot_data.get("shot_number", "") if shot_data else "")
        self._shot_type = QComboBox()
        self._shot_type.addItems(SHOT_TYPES)
        if shot_data and shot_data.get("shot_type") in SHOT_TYPES:
            self._shot_type.setCurrentText(shot_data["shot_type"])

        self._lens = QSpinBox()
        self._lens.setRange(0, 1000)
        self._lens.setSuffix(" mm")
        if shot_data and shot_data.get("lens_mm"):
            self._lens.setValue(int(shot_data["lens_mm"]))

        self._movement = QComboBox()
        self._movement.addItems([""] + CAMERA_MOVEMENTS)
        if shot_data and shot_data.get("camera_movement"):
            self._movement.setCurrentText(shot_data["camera_movement"])

        self._desc = QTextEdit(
            shot_data.get("description", "") if shot_data else "")
        self._desc.setFixedHeight(80)

        form.addRow("N\u00b0 Shot:", self._shot_number)
        form.addRow("Tipo:", self._shot_type)
        form.addRow("Obiettivo:", self._lens)
        form.addRow("Movimento:", self._movement)
        form.addRow("Descrizione:", self._desc)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    def get_data(self) -> dict:
        lens = self._lens.value() if self._lens.value() > 0 else None
        mov  = self._movement.currentText() or None
        return {
            "shot_number":     self._shot_number.text().strip() or "A",
            "shot_type":       self._shot_type.currentText(),
            "lens_mm":         lens,
            "camera_movement": mov,
            "description":     self._desc.toPlainText().strip(),
        }
