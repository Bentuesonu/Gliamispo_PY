from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QHBoxLayout, QComboBox, QPushButton, QFileDialog,
    QInputDialog, QMessageBox,
)
from PySide6.QtCore import Qt
from gliamispo.export import export_call_sheet, Format


class CallSheetView(QWidget):
    def __init__(self, container, parent=None):
        super().__init__(parent)
        self._container = container
        self._project_id = None
        self._selected_call_sheet_id = None

        self._date_combo = QComboBox()
        self._date_combo.currentTextChanged.connect(self._on_date_changed)

        self._email_btn = QPushButton("Distribuisci ODG")
        self._email_btn.clicked.connect(self._distribute_email)

        self._sides_btn = QPushButton("Genera Sides")
        self._sides_btn.clicked.connect(self._generate_sides)

        self._mm_btn = QPushButton("Movie Magic CSV")
        self._mm_btn.clicked.connect(self._export_movie_magic)

        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Giorno:"))
        header_layout.addWidget(self._date_combo)
        header_layout.addStretch()
        header_layout.addWidget(self._email_btn)
        header_layout.addWidget(self._sides_btn)
        header_layout.addWidget(self._mm_btn)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["Scena", "Location", "INT/EXT", "Giorno/Notte", "Ore"]
        )

        layout = QVBoxLayout(self)
        layout.addLayout(header_layout)
        layout.addWidget(self._table)

    def load_project(self, project_id):
        self._project_id = project_id
        # ✅ FIX: usa shooting_days via shooting_schedules (non schedule_entries)
        rows = self._container.database.execute(
            "SELECT DISTINCT sd.day_number "
            "FROM shooting_days sd "
            "JOIN shooting_schedules ss ON ss.id = sd.schedule_id "
            "WHERE ss.project_id = ? "
            "ORDER BY sd.day_number",
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
        # ✅ FIX: usa shooting_day_scenes + shooting_days (non schedule_entries/position)
        rows = self._container.database.execute(
            "SELECT s.scene_number, s.location, s.int_ext, s.day_night, "
            "s.manual_shooting_hours "
            "FROM shooting_day_scenes sds "
            "JOIN shooting_days sd ON sd.id = sds.shooting_day_id "
            "JOIN shooting_schedules ss ON ss.id = sd.schedule_id "
            "JOIN scenes s ON s.id = sds.scene_id "
            "WHERE ss.project_id = ? AND sd.day_number = ? "
            "ORDER BY sds.sort_order",
            (self._project_id, int(day))
        ).fetchall()
        self._table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, val in enumerate(r):
                item = QTableWidgetItem(str(val) if val is not None else "")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._table.setItem(i, j, item)

        cs_row = self._container.database.execute(
            "SELECT cs.id FROM call_sheets cs "
            "JOIN shooting_days sd ON sd.id = cs.shooting_day_id "
            "JOIN shooting_schedules ss ON ss.id = sd.schedule_id "
            "WHERE ss.project_id = ? AND sd.day_number = ? LIMIT 1",
            (self._project_id, int(day))
        ).fetchone()
        self._selected_call_sheet_id = cs_row[0] if cs_row else None

    def _export_pdf(self):
        if not self._selected_call_sheet_id:
            return
        data = export_call_sheet(
            self._container.database, self._selected_call_sheet_id, fmt=Format.PDF
        )
        if not data:
            QMessageBox.warning(
                self, "Export", "Impossibile generare il PDF."
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Salva Call Sheet", "call_sheet.pdf", "PDF (*.pdf)"
        )
        if path:
            with open(path, "wb") as f:
                f.write(data)

    def _export_excel(self):
        if not self._selected_call_sheet_id:
            return
        data = export_call_sheet(
            self._container.database, self._selected_call_sheet_id, fmt=Format.EXCEL
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "Salva Call Sheet", "call_sheet.xlsx", "Excel (*.xlsx)"
        )
        if path:
            with open(path, "wb") as f:
                f.write(data)

    def _distribute_email(self):
        """Feature 4.1 — Distribuzione ODG via Email."""
        if not self._selected_call_sheet_id:
            return
        email, ok = QInputDialog.getText(self, "Destinatario", "Email destinatario:")
        if not ok or not email:
            return
        name, ok2 = QInputDialog.getText(self, "Destinatario", "Nome destinatario:")
        if not ok2:
            return
        pdf = export_call_sheet(
            self._container.database, self._selected_call_sheet_id, fmt=Format.PDF
        )
        day = self._date_combo.currentText()
        ok3 = self._container.email_distributor.send_call_sheet(pdf, name, email, day)
        if ok3:
            db = self._container.database
            with db._lock:
                db._conn.execute(
                    "INSERT INTO distribution_log "
                    "(call_sheet_id, recipient_name, recipient_email) VALUES (?,?,?)",
                    (self._selected_call_sheet_id, name, email),
                )
                db._conn.commit()
            QMessageBox.information(self, "Inviato", f"ODG inviato a {email}")
        else:
            QMessageBox.warning(
                self,
                "Errore",
                "Invio email fallito. Controlla le impostazioni SMTP.",
            )

    def _generate_sides(self):
        """Feature 4.2 — Script Sides Generator."""
        if not self._selected_call_sheet_id or not self._project_id:
            return
        from gliamispo.export.sides_generator import generate_all_sides_batch
        import os

        folder = QFileDialog.getExistingDirectory(self, "Cartella output Sides")
        if not folder:
            return
        sides = generate_all_sides_batch(
            self._container.database, self._project_id, self._selected_call_sheet_id
        )
        for actor, pdf in sides.items():
            safe = actor.replace(" ", "_").replace("/", "-")
            with open(os.path.join(folder, f"sides_{safe}.pdf"), "wb") as f:
                f.write(pdf)
        QMessageBox.information(
            self, "Sides generati", f"{len(sides)} PDF creati in {folder}"
        )

    def _export_movie_magic(self):
        """Feature 4.3 — Export Movie Magic CSV."""
        if not self._project_id:
            return
        from gliamispo.export.industry_export import export_movie_magic_csv

        data = export_movie_magic_csv(self._container.database, self._project_id)
        path, _ = QFileDialog.getSaveFileName(
            self, "Esporta Movie Magic", "schedule.csv", "CSV (*.csv)"
        )
        if path:
            with open(path, "wb") as f:
                f.write(data)

    def clear(self):
        self._project_id = None
        self._selected_call_sheet_id = None
        self._date_combo.clear()
        self._table.setRowCount(0)