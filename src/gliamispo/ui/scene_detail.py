from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QTableWidget, QTableWidgetItem, QGroupBox, QPlainTextEdit,
    QPushButton, QMessageBox,
)
from PySide6.QtCore import Qt, Signal


class SceneDetail(QWidget):
    # Segnale emesso quando la sinossi viene modificata
    synopsis_changed = Signal(int, str)  # scene_id, new_synopsis

    def __init__(self, container, parent=None):
        super().__init__(parent)
        self._container = container
        self._scene_id = None
        self._original_synopsis = ""  # Per tracciare modifiche

        self._scene_number_label = QLabel("—")
        self._location_label = QLabel("—")
        self._int_ext_label = QLabel("—")
        self._day_night_label = QLabel("—")

        # Sinossi modificabile
        self._synopsis_edit = QPlainTextEdit()
        self._synopsis_edit.setPlaceholderText("Inserisci o modifica la sinossi...")
        self._synopsis_edit.setMaximumHeight(100)
        self._synopsis_edit.textChanged.connect(self._on_synopsis_changed)

        # Pulsanti per la sinossi
        self._save_synopsis_btn = QPushButton("Salva")
        self._save_synopsis_btn.setEnabled(False)
        self._save_synopsis_btn.clicked.connect(self._save_synopsis)
        self._save_synopsis_btn.setToolTip("Salva le modifiche alla sinossi")

        self._regenerate_btn = QPushButton("Rigenera")
        self._regenerate_btn.clicked.connect(self._regenerate_synopsis)
        self._regenerate_btn.setToolTip("Rigenera la sinossi automaticamente")

        self._revert_btn = QPushButton("Annulla")
        self._revert_btn.setEnabled(False)
        self._revert_btn.clicked.connect(self._revert_synopsis)
        self._revert_btn.setToolTip("Annulla le modifiche non salvate")

        # Layout pulsanti sinossi
        synopsis_buttons = QHBoxLayout()
        synopsis_buttons.addWidget(self._save_synopsis_btn)
        synopsis_buttons.addWidget(self._regenerate_btn)
        synopsis_buttons.addWidget(self._revert_btn)
        synopsis_buttons.addStretch()

        # Layout sinossi con edit e pulsanti
        synopsis_layout = QVBoxLayout()
        synopsis_layout.setContentsMargins(0, 0, 0, 0)
        synopsis_layout.addWidget(self._synopsis_edit)
        synopsis_layout.addLayout(synopsis_buttons)

        synopsis_widget = QWidget()
        synopsis_widget.setLayout(synopsis_layout)

        form = QFormLayout()
        form.addRow("Scena:", self._scene_number_label)
        form.addRow("Location:", self._location_label)
        form.addRow("INT/EXT:", self._int_ext_label)
        form.addRow("Giorno/Notte:", self._day_night_label)
        form.addRow("Sinossi:", synopsis_widget)

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

        # Carica sinossi e traccia originale
        synopsis = row[4] or ""
        self._original_synopsis = synopsis
        self._synopsis_edit.blockSignals(True)
        self._synopsis_edit.setPlainText(synopsis)
        self._synopsis_edit.blockSignals(False)
        self._save_synopsis_btn.setEnabled(False)
        self._revert_btn.setEnabled(False)

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
        self._original_synopsis = ""
        self._scene_number_label.setText("—")
        self._location_label.setText("—")
        self._int_ext_label.setText("—")
        self._day_night_label.setText("—")
        self._synopsis_edit.blockSignals(True)
        self._synopsis_edit.clear()
        self._synopsis_edit.blockSignals(False)
        self._save_synopsis_btn.setEnabled(False)
        self._revert_btn.setEnabled(False)
        self._elements_table.setRowCount(0)

    def _on_synopsis_changed(self):
        """Attiva pulsanti quando la sinossi viene modificata."""
        current = self._synopsis_edit.toPlainText()
        has_changes = current != self._original_synopsis
        self._save_synopsis_btn.setEnabled(has_changes)
        self._revert_btn.setEnabled(has_changes)

    def _save_synopsis(self):
        """Salva la sinossi modificata nel database."""
        if self._scene_id is None:
            return

        new_synopsis = self._synopsis_edit.toPlainText().strip()

        try:
            self._container.database.execute(
                "UPDATE scenes SET synopsis = ? WHERE id = ?",
                (new_synopsis, self._scene_id)
            )
            self._container.database.commit()

            self._original_synopsis = new_synopsis
            self._save_synopsis_btn.setEnabled(False)
            self._revert_btn.setEnabled(False)

            # Emetti segnale per aggiornare altre viste
            self.synopsis_changed.emit(self._scene_id, new_synopsis)

        except Exception as e:
            QMessageBox.warning(
                self,
                "Errore",
                f"Impossibile salvare la sinossi:\n{e}"
            )

    def _regenerate_synopsis(self):
        """Rigenera la sinossi automaticamente dai raw_blocks della scena."""
        if self._scene_id is None:
            return

        # Chiedi conferma se ci sono modifiche non salvate
        current = self._synopsis_edit.toPlainText()
        if current != self._original_synopsis:
            reply = QMessageBox.question(
                self,
                "Rigenerare sinossi?",
                "Ci sono modifiche non salvate. Rigenerare sovrascriverà il testo attuale.\n\nContinuare?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        try:
            # Recupera raw_blocks dalla scena
            row = self._container.database.execute(
                "SELECT raw_blocks FROM scenes WHERE id = ?",
                (self._scene_id,)
            ).fetchone()

            if not row or not row[0]:
                QMessageBox.information(
                    self,
                    "Nessun contenuto",
                    "La scena non contiene blocchi di testo da cui generare la sinossi."
                )
                return

            import json
            raw_blocks = json.loads(row[0])

            # Genera nuova sinossi
            from gliamispo.services.synopsis_generator import generate_synopsis
            new_synopsis = generate_synopsis(raw_blocks)

            if not new_synopsis:
                QMessageBox.information(
                    self,
                    "Sinossi vuota",
                    "Non è stato possibile generare una sinossi dal contenuto della scena."
                )
                return

            # Aggiorna il campo di testo
            self._synopsis_edit.setPlainText(new_synopsis)
            # _on_synopsis_changed verrà chiamato automaticamente

        except Exception as e:
            QMessageBox.warning(
                self,
                "Errore",
                f"Impossibile rigenerare la sinossi:\n{e}"
            )

    def _revert_synopsis(self):
        """Annulla le modifiche e ripristina la sinossi originale."""
        self._synopsis_edit.setPlainText(self._original_synopsis)
        self._save_synopsis_btn.setEnabled(False)
        self._revert_btn.setEnabled(False)
