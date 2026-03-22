# src/gliamispo/ui/search_dialog.py
"""
Dialog per la visualizzazione dei risultati di ricerca FTS5.

Emette il segnale result_selected(content_type: str, content_id: int)
al doppio click su un risultato, permettendo a MainWindow di navigare
alla vista corretta.

Tipi di contenuto restituiti:
  'scene'   -> naviga al Breakdown, seleziona la scena per id
  'element' -> naviga al Breakdown, evidenzia l'elemento per id
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem,
    QLabel, QHeaderView, QPushButton,
    QFrame,
)
from PySide6.QtCore import Qt, Signal
from gliamispo.ui import theme


# Mappa content_type -> etichetta visiva
_TYPE_LABELS = {
    "scene":    "\U0001f3a6  Scena",
    "element":  "\U0001f3ad Elemento",
    "location": "\U0001f4cd Location",
}


class SearchResultsDialog(QDialog):
    """
    Dialog modale con i risultati FTS5 filtrati per project_id.

    Segnali
    -------
    result_selected(content_type: str, content_id: int)
        Emesso al doppio click su una riga.
        content_type e' uno tra: 'scene', 'element', 'location'
        content_id e' l'id della riga nella tabella sorgente.
    """

    result_selected = Signal(str, int)

    def __init__(self, db, project_id: int, query: str, parent=None):
        super().__init__(parent)
        self._db         = db
        self._project_id = project_id
        self._query      = query.strip()

        self.setWindowTitle(f"Ricerca: {self._query}")
        self.setMinimumSize(700, 460)
        self.setModal(True)
        self.setStyleSheet(f"background-color: {theme.BG0.name()};")

        self._build_ui()
        self._load_results()

    # -------------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(14)

        # Header
        header_row = QHBoxLayout()

        # CORREZIONE riga 69:
        # Le virgolette tipografiche " " nel sorgente precedente venivano
        # convertite in virgolette ASCII ", chiudendo prematuramente l'f-string.
        # Soluzione: usare singoli apici come delimitatore esterno,
        # cosi' i " dentro la stringa non ambiguita' con il delimitatore.
        title = QLabel(f'\U0001f50d  Risultati per "{self._query}"')
        title.setFont(theme.font_ui(14, bold=True))
        title.setStyleSheet(f"color: {theme.TEXT0.name()};")
        header_row.addWidget(title)

        header_row.addStretch()

        self._count_label = QLabel("")
        self._count_label.setFont(theme.font_ui(11))
        self._count_label.setStyleSheet(f"color: {theme.TEXT3.name()};")
        header_row.addWidget(self._count_label)

        layout.addLayout(header_row)

        # Divider
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background-color: {theme.qss_color(theme.BD1)};")
        layout.addWidget(div)

        # Tabella
        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["Tipo", "Testo", "ID"])

        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {theme.BG0.name()};
                alternate-background-color: {theme.BG1.name()};
                border: 1px solid {theme.qss_color(theme.BD1)};
                border-radius: 6px;
                color: {theme.TEXT0.name()};
            }}
            QTableWidget::item:selected {{
                background-color: {theme.qss_color(theme.GOLD_BG)};
                color: {theme.TEXT0.name()};
            }}
            QHeaderView::section {{
                background-color: {theme.BG2.name()};
                color: {theme.TEXT2.name()};
                font-size: 11px;
                font-weight: 600;
                border: none;
                padding: 5px 8px;
            }}
        """)
        self._table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table, 1)

        # Footer
        footer = QHBoxLayout()

        hint = QLabel("\u21b5  Doppio click per navigare al risultato")
        hint.setFont(theme.font_ui(10))
        hint.setStyleSheet(f"color: {theme.TEXT3.name()};")
        footer.addWidget(hint)
        footer.addStretch()

        close_btn = QPushButton("Chiudi")
        close_btn.setFont(theme.font_ui(11))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                color: {theme.TEXT2.name()};
                background: transparent;
                border: 1.5px solid {theme.qss_color(theme.BD1)};
                border-radius: 6px;
                padding: 5px 18px;
            }}
            QPushButton:hover {{
                background-color: {theme.qss_color(theme.BD0)};
            }}
        """)
        close_btn.clicked.connect(self.reject)
        footer.addWidget(close_btn)

        layout.addLayout(footer)

    # -------------------------------------------------------------------------

    def _load_results(self):
        """Interroga l'indice FTS5 e popola la tabella."""
        rows = []
        try:
            rows = self._db.execute(
                "SELECT content_type, content_id, text "
                "FROM search_index "
                "WHERE search_index MATCH ? AND project_id = ? "
                "ORDER BY rank",
                (self._query, self._project_id)
            ).fetchall()
        except Exception as exc:
            # FTS5 non disponibile (DB non ancora migrato a V18)
            # oppure query con caratteri speciali -- mostriamo 0 risultati
            print(f"[SearchDialog] FTS5 query error: {exc}")

        n = len(rows)
        self._count_label.setText(
            f"{n} risultato" if n == 1 else f"{n} risultati"
        )

        self._table.setRowCount(n)
        for i, row in enumerate(rows):
            c_type = row[0] if row[0] else ""
            c_id   = int(row[1]) if row[1] is not None else 0
            text   = str(row[2])[:120] if row[2] else ""

            label_item = QTableWidgetItem(_TYPE_LABELS.get(c_type, c_type))
            label_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter)

            text_item = QTableWidgetItem(text)
            text_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter)

            id_item = QTableWidgetItem(str(c_id))
            id_item.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            )
            id_item.setFont(theme.font_mono(10))
            id_item.setData(Qt.ItemDataRole.UserRole, (c_type, c_id))

            self._table.setItem(i, 0, label_item)
            self._table.setItem(i, 1, text_item)
            self._table.setItem(i, 2, id_item)

        self._table.resizeRowsToContents()

    # -------------------------------------------------------------------------

    def _on_double_click(self, idx):
        row = idx.row()
        id_item = self._table.item(row, 2)
        if id_item is None:
            return
        data = id_item.data(Qt.ItemDataRole.UserRole)
        if data:
            c_type, c_id = data
            self.result_selected.emit(c_type, c_id)
            self.accept()