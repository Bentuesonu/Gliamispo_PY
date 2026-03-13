from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QFrame, QHeaderView, QPushButton,
)
from PyQt6.QtCore import Qt
from gliamispo.ui import theme
from gliamispo.models.eighths import Eighths


class OneLinerView(QWidget):
    def __init__(self, container, parent=None):
        super().__init__(parent)
        self._container = container
        self._project_id = None
        self.setStyleSheet(f"background-color: {theme.BG1.name()};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setStyleSheet(f"background-color: {theme.BG2.name()};")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(16, 10, 16, 10)

        title = QLabel("ONE-LINER SCHEDULE")
        title.setFont(theme.font_ui(12, bold=True))
        title.setStyleSheet(f"color: {theme.TEXT0.name()};")
        h_layout.addWidget(title)
        h_layout.addStretch()

        self._total_label = QLabel("")
        self._total_label.setFont(theme.font_ui(11))
        self._total_label.setStyleSheet(f"color: {theme.TEXT3.name()};")
        h_layout.addWidget(self._total_label)

        export_btn = QPushButton('Esporta PDF')
        export_btn.setFont(theme.font_ui(11))
        export_btn.setStyleSheet(f'''
            QPushButton {{
                color: {theme.GOLD.name()};
                background-color: {theme.qss_color(theme.GOLD_BG)};
                border: 1.5px solid {theme.qss_color(theme.GOLD_BD)};
                border-radius: 6px; padding: 5px 14px;
            }}
        ''')
        export_btn.clicked.connect(self._export_pdf)
        h_layout.addWidget(export_btn)

        layout.addWidget(header)

        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background-color: {theme.qss_color(theme.BD1)};")
        layout.addWidget(div)

        # Table
        self._table = QTableWidget(0, 8)
        self._table.setHorizontalHeaderLabels([
            'Giorno', 'Scena', 'INT/EXT', 'Giorno/Notte',
            'Location', 'Pagine', 'Cast', 'Sinossi',
        ])
        self._table.horizontalHeader().setSectionResizeMode(
            7, QHeaderView.ResizeMode.Stretch
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {theme.BG1.name()};
                alternate-background-color: {theme.BG0.name()};
                border: none;
                gridline-color: {theme.qss_color(theme.BD0)};
            }}
            QHeaderView::section {{
                background-color: {theme.BG3.name()};
                color: {theme.TEXT2.name()};
                border: none;
                border-bottom: 1px solid {theme.qss_color(theme.BD1)};
                padding: 6px 8px;
                font-size: 10px;
                font-weight: 600;
            }}
            QTableWidget::item {{
                padding: 4px 8px;
            }}
        """)
        layout.addWidget(self._table, 1)

    def load_project(self, project_id):
        self._project_id = project_id
        db = self._container.database

        try:
            entries = db.execute(
                'SELECT se.shooting_day, s.scene_number, s.int_ext, s.day_night,'
                ' s.location, s.page_start_whole, s.page_start_eighths,'
                ' s.page_end_whole, s.page_end_eighths, s.id, s.synopsis'
                ' FROM schedule_entries se'
                ' JOIN scenes s ON se.scene_id = s.id'
                ' WHERE se.project_id = ?'
                ' ORDER BY se.shooting_day, se.position',
                (project_id,)
            ).fetchall()
        except Exception:
            entries = []

        if not entries:
            entries = db.execute(
                'SELECT 1, scene_number, int_ext, day_night, location,'
                ' page_start_whole, page_start_eighths,'
                ' page_end_whole, page_end_eighths, id, synopsis'
                ' FROM scenes WHERE project_id = ? ORDER BY id',
                (project_id,)
            ).fetchall()

        self._table.setRowCount(len(entries))
        for i, e in enumerate(entries):
            dur = Eighths(e[7] or 0, e[8] or 0) - Eighths(e[5] or 0, e[6] or 0)

            cast_rows = db.execute(
                "SELECT element_name FROM scene_elements "
                "WHERE scene_id = ? AND category = 'Cast' "
                "ORDER BY element_name", (e[9],)
            ).fetchall()
            cast_text = ", ".join(r[0] for r in cast_rows)

            values = [
                str(e[0]), e[1] or '', e[2] or '', e[3] or '',
                e[4] or '', str(dur) if dur.total_eighths > 0 else '',
                cast_text,
                (e[10] or '')[:120],
            ]
            for j, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if j == 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._table.setItem(i, j, item)

        scene_count = len(entries)
        self._total_label.setText(f"{scene_count} scene")

    def _export_pdf(self):
        from PyQt6.QtWidgets import QFileDialog
        from gliamispo.export.pdf_exporter import OneLinerExporter

        if self._project_id is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, 'Salva One-Liner PDF', '', 'PDF (*.pdf)'
        )
        if not path:
            return

        rows = []
        for i in range(self._table.rowCount()):
            rows.append(tuple(
                self._table.item(i, j).text() if self._table.item(i, j) else ''
                for j in range(self._table.columnCount())
            ))

        db_row = self._container.database.execute(
            'SELECT title FROM projects WHERE id = ?',
            (self._project_id,)
        ).fetchone()
        title = db_row[0] if db_row else ''

        data = OneLinerExporter(title).export(rows)
        if data:
            with open(path, 'wb') as f:
                f.write(data)
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, 'Export', 'Installa fpdf2: pip install fpdf2')

    def clear(self):
        self._project_id = None
        self._table.setRowCount(0)
        self._total_label.setText("")
