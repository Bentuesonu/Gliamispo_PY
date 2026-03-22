from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QFrame, QHeaderView, QFileDialog,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from gliamispo.ui import theme
from gliamispo.models.eighths import Eighths
from gliamispo.export import export_oneliner, Format

# Lazy loading page size
_PAGE_SIZE = 50


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

        layout.addWidget(header)

        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background-color: {theme.qss_color(theme.BD1)};")
        layout.addWidget(div)

        # Table
        self._table = QTableWidget(0, 9)
        self._table.setHorizontalHeaderLabels([
            'Giorno', 'Scena', 'INT/EXT', 'Giorno/Notte',
            'Location', 'Pagine', 'Cast', 'Sinossi', 'Costo Est.',
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

        # Check scene count for lazy loading decision
        scene_count = db.execute(
            "SELECT COUNT(*) FROM scenes WHERE project_id=?",
            (project_id,)
        ).fetchone()[0]
        self._total_label.setText(f"{scene_count} scene")

        self._table.setRowCount(0)

        # Use lazy loading for large projects
        if scene_count > _PAGE_SIZE:
            self._load_rows_paginated()
            return

        # Standard loading for small projects
        try:
            entries = db.execute(
                'SELECT se.shooting_day, s.scene_number, s.int_ext, s.day_night,'
                ' s.location, s.page_start_whole, s.page_start_eighths,'
                ' s.page_end_whole, s.page_end_eighths, s.id, s.synopsis,'
                ' COALESCE(s.estimated_cost, 0.0)'
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
                ' page_end_whole, page_end_eighths, id, synopsis,'
                ' COALESCE(estimated_cost, 0.0)'
                ' FROM scenes WHERE project_id = ? ORDER BY id',
                (project_id,)
            ).fetchall()

        self._table.setRowCount(len(entries))
        for i, e in enumerate(entries):
            self._fill_row(i, e)

    def _on_export_excel(self):
        if self._project_id is None:
            return
        data = export_oneliner(
            self._container.database, self._project_id, fmt=Format.EXCEL
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "Esporta One-Liner", "oneliner.xlsx", "Excel (*.xlsx)"
        )
        if path:
            with open(path, "wb") as f:
                f.write(data)

    def _on_export_pdf(self):
        if self._project_id is None:
            return
        data = export_oneliner(
            self._container.database, self._project_id, fmt=Format.PDF
        )
        if not data:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, "Export", "Installa fpdf2: pip install fpdf2"
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Esporta One-Liner", "oneliner.pdf", "PDF (*.pdf)"
        )
        if path:
            with open(path, "wb") as f:
                f.write(data)

    def _load_rows_paginated(self, offset: int = 0):
        """Carica _PAGE_SIZE righe e schedula la prossima pagina con QTimer."""
        from PySide6.QtCore import QTimer
        db = self._container.database

        try:
            rows = db.execute(
                "SELECT se.shooting_day, s.scene_number, s.int_ext, s.day_night,"
                " s.location, s.page_start_whole, s.page_start_eighths,"
                " s.page_end_whole, s.page_end_eighths, s.id, s.synopsis,"
                " COALESCE(s.estimated_cost, 0.0)"
                " FROM schedule_entries se"
                " JOIN scenes s ON se.scene_id = s.id"
                " WHERE se.project_id = ?"
                " ORDER BY se.shooting_day, se.position"
                " LIMIT ? OFFSET ?",
                (self._project_id, _PAGE_SIZE, offset)
            ).fetchall()
        except Exception:
            rows = db.execute(
                "SELECT 1, scene_number, int_ext, day_night, location,"
                " page_start_whole, page_start_eighths,"
                " page_end_whole, page_end_eighths, id, synopsis,"
                " COALESCE(estimated_cost, 0.0)"
                " FROM scenes WHERE project_id = ? ORDER BY id"
                " LIMIT ? OFFSET ?",
                (self._project_id, _PAGE_SIZE, offset)
            ).fetchall()

        for row_idx, e in enumerate(rows, start=offset):
            if row_idx >= self._table.rowCount():
                self._table.insertRow(row_idx)
            self._fill_row(row_idx, e)

        if len(rows) == _PAGE_SIZE:
            QTimer.singleShot(
                10, lambda: self._load_rows_paginated(offset + _PAGE_SIZE)
            )

    def _fill_row(self, row_idx, e):
        """Riempie una singola riga della tabella."""
        db = self._container.database
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
            self._table.setItem(row_idx, j, item)

        cost = e[11] if e[11] else 0
        cost_item = QTableWidgetItem(f"\u20ac {cost:,.0f}" if cost > 0 else "\u2014")
        cost_item.setFlags(cost_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        cost_item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if cost > 5000:
            cost_item.setBackground(QColor("#FADBD8"))
        elif cost > 1000:
            cost_item.setBackground(QColor("#FDEBD0"))
        self._table.setItem(row_idx, 8, cost_item)

    def clear(self):
        self._project_id = None
        self._table.setRowCount(0)
        self._total_label.setText("")
