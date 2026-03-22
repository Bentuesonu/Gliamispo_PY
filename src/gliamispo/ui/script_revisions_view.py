# src/gliamispo/ui/script_revisions_view.py
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QFileDialog, QMessageBox, QHeaderView,
    QAbstractItemView, QFrame,
)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt
from gliamispo.ui import theme


# ── Colori Hollywood ──────────────────────────────────────────────────────────
_HOLLYWOOD_COLORS = {
    1:  ("WHITE",     "#FFFFFF", "#111111"),
    2:  ("BLUE",      "#ADD8E6", "#0a2a3a"),
    3:  ("PINK",      "#FFB6C1", "#3a0010"),
    4:  ("YELLOW",    "#FFFF99", "#2a2a00"),
    5:  ("GREEN",     "#90EE90", "#0a2a0a"),
    6:  ("GOLDENROD", "#DAA520", "#FFFFFF"),
    7:  ("BUFF",      "#F0DC82", "#2a2000"),
    8:  ("SALMON",    "#FA8072", "#FFFFFF"),
    9:  ("CHERRY",    "#DE3163", "#FFFFFF"),
    10: ("TAN",       "#D2B48C", "#2a1a00"),
}


def _color_for_rev(rev_num: int):
    return _HOLLYWOOD_COLORS.get(rev_num % 10 or 10, _HOLLYWOOD_COLORS[1])


# ── Estrazione testo da qualsiasi formato supportato ─────────────────────────

def _extract_text(file_path: str) -> str:
    """
    Estrae testo grezzo da .fountain, .txt, .pdf, .docx / .doc.
    Ritorna stringa vuota in caso di errore.
    """
    lower = file_path.lower()
    try:
        if lower.endswith(".pdf"):
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                return "\n".join(p.extract_text() or "" for p in pdf.pages)
        elif lower.endswith((".docx", ".doc")):
            from docx import Document
            doc = Document(file_path)
            return "\n".join(p.text for p in doc.paragraphs)
        else:
            with open(file_path, encoding="utf-8", errors="replace") as f:
                return f.read()
    except Exception:
        return ""


# ── Diff sceneggiatura ────────────────────────────────────────────────────────

def _diff_screenplay(db, project_id: int, file_path: str) -> dict:
    """
    Estrae il testo dal file (qualsiasi formato supportato), lo parsa con
    FountainParser e confronta le scene con quelle nel DB corrente.

    Ritorna:
        {
            "added":     [scene_number, ...],
            "deleted":   [scene_number, ...],
            "modified":  [scene_number, ...],
            "unchanged": [scene_number, ...],
            "error":     str | None,
        }
    """
    text = _extract_text(file_path)
    if not text.strip():
        return {
            "added": [], "deleted": [], "modified": [],
            "unchanged": [], "error": "Nessun testo leggibile nel file.",
        }

    from gliamispo.parsing.fountain_parser import FountainParser
    parsed = FountainParser().parse(text)

    if not parsed:
        return {
            "added": [], "deleted": [], "modified": [],
            "unchanged": [], "error": "Nessuna scena rilevata nel file.",
        }

    # scene_number -> synopsis normalizzato dal file importato
    new_scenes = {
        s.scene_number.strip(): (s.synopsis or "").strip().lower()
        for s in parsed
        if s.scene_number
    }

    # scene_number -> synopsis dal DB
    rows = db.execute(
        "SELECT scene_number, synopsis FROM scenes WHERE project_id = ?",
        (project_id,)
    ).fetchall()
    db_scenes = {
        (r[0] or "").strip(): (r[1] or "").strip().lower()
        for r in rows
        if r[0]
    }

    added    = [n for n in new_scenes if n not in db_scenes]
    deleted  = [n for n in db_scenes  if n not in new_scenes]
    modified = [
        n for n in new_scenes
        if n in db_scenes and new_scenes[n] != db_scenes[n]
    ]
    unchanged = [
        n for n in new_scenes
        if n in db_scenes and new_scenes[n] == db_scenes[n]
    ]

    return {
        "added":     sorted(added),
        "deleted":   sorted(deleted),
        "modified":  sorted(modified),
        "unchanged": sorted(unchanged),
        "error":     None,
    }


def _apply_revision_badges(db, project_id: int, rev_color: str, diff: dict):
    """Imposta revision_badge sulle scene modificate e aggiunte."""
    badge_scenes = set(diff.get("modified", [])) | set(diff.get("added", []))
    if not badge_scenes:
        return
    for scene_num in badge_scenes:
        db.execute(
            "UPDATE scenes SET revision_badge = ? "
            "WHERE project_id = ? AND scene_number = ?",
            (rev_color.upper(), project_id, scene_num)
        )
    db.commit()


def _save_diff_to_db(db, rev_id: int, diff: dict):
    """Salva il risultato del diff in revision_scene_changes."""
    mapping = {
        "added":    "added",
        "deleted":  "deleted",
        "modified": "modified",
    }
    for key, change_type in mapping.items():
        for sn in diff.get(key, []):
            db.execute(
                "INSERT INTO revision_scene_changes "
                "(revision_id, scene_number, change_type, diff_summary) "
                "VALUES (?,?,?,?)",
                (rev_id, sn, change_type,
                 f"Rilevato alla revisione #{rev_id}")
            )
    db.commit()


# ── Widget principale ─────────────────────────────────────────────────────────

class ScriptRevisionsPanel(QWidget):

    _BG   = "#f4f0eb"
    _BG2  = "#ece7e0"
    _BD   = "#d0c8be"
    _TXT  = "#2a2724"
    _TXT3 = "#7a7268"

    def __init__(self, container, parent=None):
        super().__init__(parent)
        self._container = container
        self._project_id = None
        self._build_ui()

    # ── Costruzione UI ────────────────────────────────────────────────────────

    def _build_ui(self):
        self.setStyleSheet(f"background-color: {self._BG};")
        self.setMinimumWidth(300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setStyleSheet(
            f"background-color: {self._BG2};"
            f"border-bottom: 1px solid {self._BD};"
        )
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(14, 10, 14, 10)
        title = QLabel("Revisioni Sceneggiatura")
        title.setFont(theme.font_ui(12, bold=True))
        title.setStyleSheet(f"color: {self._TXT}; background: transparent;")
        h_layout.addWidget(title, 1)
        layout.addWidget(header)

        # Toolbar
        toolbar = QWidget()
        toolbar.setStyleSheet(
            f"background-color: {self._BG};"
            f"border-bottom: 1px solid {self._BD};"
        )
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(12, 8, 12, 8)
        tb.setSpacing(8)

        self._import_btn = QPushButton("Importa Revisione")
        self._import_btn.setFont(theme.font_ui(10))
        self._import_btn.setEnabled(False)
        self._import_btn.setFixedHeight(28)
        self._import_btn.setStyleSheet(f"""
            QPushButton {{
                color: {self._TXT};
                background-color: {self._BG2};
                border: 1px solid {self._BD};
                border-radius: 4px;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background-color: {self._BD};
            }}
            QPushButton:disabled {{
                color: {self._TXT3};
            }}
        """)
        self._import_btn.clicked.connect(self._on_import)
        tb.addWidget(self._import_btn)
        tb.addStretch()
        layout.addWidget(toolbar)

        # Legenda
        legend = QLabel(
            "Doppio click su una riga per impostare la revisione come corrente."
        )
        legend.setFont(theme.font_ui(9))
        legend.setWordWrap(True)
        legend.setStyleSheet(
            f"color: {self._TXT3}; background: transparent;"
            f" padding: 6px 14px 4px 14px;"
        )
        layout.addWidget(legend)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {self._BD};")
        layout.addWidget(sep)

        # Tabella revisioni
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["#", "Colore", "Stato", "Data", "Note"]
        )
        self._table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Stretch
        )
        for col, w in enumerate([28, 80, 80, 120]):
            self._table.setColumnWidth(col, w)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {self._BG};
                alternate-background-color: {self._BG2};
                color: {self._TXT};
                border: none;
                gridline-color: {self._BD};
                font-size: 11px;
            }}
            QTableWidget::item {{
                padding: 4px 6px;
                color: {self._TXT};
            }}
            QTableWidget::item:selected {{
                background-color: {theme.GOLD_BG.name()};
                color: {self._TXT};
            }}
            QHeaderView::section {{
                background-color: {self._BG2};
                color: {self._TXT3};
                border: none;
                border-bottom: 1px solid {self._BD};
                padding: 4px 6px;
                font-size: 10px;
                font-weight: bold;
            }}
            QScrollBar:vertical {{
                background: {self._BG};
                width: 6px;
            }}
            QScrollBar::handle:vertical {{
                background: {self._BD};
                border-radius: 3px;
            }}
        """)
        self._table.doubleClicked.connect(self._on_row_double_click)
        layout.addWidget(self._table, 1)

        # Area riepilogo diff
        self._diff_widget = QWidget()
        self._diff_widget.setVisible(False)
        self._diff_widget.setStyleSheet(
            f"background-color: {self._BG2};"
            f"border-top: 1px solid {self._BD};"
        )
        diff_layout = QVBoxLayout(self._diff_widget)
        diff_layout.setContentsMargins(12, 8, 12, 8)
        diff_layout.setSpacing(4)

        diff_title = QLabel("Ultima analisi diff:")
        diff_title.setFont(theme.font_ui(9, bold=True))
        diff_title.setStyleSheet(
            f"color: {self._TXT3}; background: transparent;"
        )
        diff_layout.addWidget(diff_title)

        self._diff_label = QLabel("")
        self._diff_label.setFont(theme.font_ui(10))
        self._diff_label.setWordWrap(True)
        self._diff_label.setStyleSheet(
            f"color: {self._TXT}; background: transparent;"
        )
        diff_layout.addWidget(self._diff_label)
        layout.addWidget(self._diff_widget)

    # ── Dati ─────────────────────────────────────────────────────────────────

    def load_project(self, project_id: int):
        self._project_id = project_id
        self._import_btn.setEnabled(True)
        self._reload()

    def clear(self):
        self._project_id = None
        self._import_btn.setEnabled(False)
        self._table.setRowCount(0)
        self._diff_widget.setVisible(False)

    def _reload(self):
        if self._project_id is None:
            return
        from gliamispo.revisions.revision_manager import RevisionManager
        mgr = RevisionManager(self._container.database)
        revisions = mgr.get_revisions(self._project_id)
        self._table.setRowCount(len(revisions))
        for i, rev in enumerate(revisions):
            rev_id, rev_num, color, ts, notes, fpath, is_current = (
                rev[0], rev[1], rev[2], rev[3], rev[4], rev[5], rev[6]
            )
            num_item = QTableWidgetItem(str(rev_num))
            num_item.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            )
            num_item.setForeground(QColor(self._TXT))
            num_item.setData(Qt.ItemDataRole.UserRole, rev_id)
            self._table.setItem(i, 0, num_item)

            _, bg_hex, fg_hex = _color_for_rev(rev_num)
            color_item = QTableWidgetItem(color.upper())
            color_item.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            )
            color_item.setBackground(QColor(bg_hex))
            color_item.setForeground(QColor(fg_hex))
            self._table.setItem(i, 1, color_item)

            stato_item = QTableWidgetItem("Corrente" if is_current else "")
            stato_item.setForeground(QColor(self._TXT))
            self._table.setItem(i, 2, stato_item)

            date_str = (
                datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M")
                if ts else ""
            )
            date_item = QTableWidgetItem(date_str)
            date_item.setForeground(QColor(self._TXT))
            self._table.setItem(i, 3, date_item)

            notes_item = QTableWidgetItem(notes or "")
            notes_item.setForeground(QColor(self._TXT))
            self._table.setItem(i, 4, notes_item)

    # ── Azioni ────────────────────────────────────────────────────────────────

    def _on_import(self):
        if self._project_id is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Importa Revisione", "",
            "Sceneggiature (*.fountain *.txt *.pdf *.docx)"
        )
        if not path:
            return

        from gliamispo.revisions.revision_manager import RevisionManager
        db  = self._container.database
        mgr = RevisionManager(db)

        # 1. Registra la revisione nel DB
        rev_id = mgr.import_revision(self._project_id, path)

        # 2. Recupera rev_num e colore appena creati
        rev_row = db.execute(
            "SELECT revision_number, revision_color "
            "FROM script_revisions WHERE id=?",
            (rev_id,)
        ).fetchone()
        rev_num   = rev_row[0]
        rev_color = rev_row[1]

        # 3. Diff su tutti i formati supportati
        diff = _diff_screenplay(db, self._project_id, path)

        if diff.get("error"):
            QMessageBox.warning(
                self, "Analisi diff",
                f"Revisione #{rev_num} registrata.\n\n{diff['error']}"
            )
            self._reload()
            return

        # 4. Salva diff e aggiorna badge
        _save_diff_to_db(db, rev_id, diff)
        _apply_revision_badges(db, self._project_id, rev_color, diff)

        # 5. Aggiorna UI
        self._reload()
        self._show_diff_summary(rev_num, rev_color, diff)

    def _show_diff_summary(self, rev_num: int, rev_color: str, diff: dict):
        added     = diff.get("added", [])
        deleted   = diff.get("deleted", [])
        modified  = diff.get("modified", [])
        unchanged = diff.get("unchanged", [])

        def scene_list(lst, max_shown=5):
            shown = ", ".join(f"sc.{n}" for n in lst[:max_shown])
            suffix = (
                f" (+{len(lst) - max_shown} altre)"
                if len(lst) > max_shown else ""
            )
            return shown + suffix

        lines = [f"Revisione #{rev_num}  ({rev_color.upper()})"]

        if added:
            lines.append(f"Aggiunte: {len(added)}  {scene_list(added)}")
        if deleted:
            lines.append(f"Eliminate: {len(deleted)}  {scene_list(deleted)}")
        if modified:
            lines.append(f"Modificate: {len(modified)}  {scene_list(modified)}")
        if unchanged:
            lines.append(f"Invariate: {len(unchanged)}")

        if not (added or deleted or modified):
            lines.append(
                "Nessuna differenza rilevata rispetto al DB attuale."
            )
        elif modified or added:
            lines.append(
                "Il badge colorato e' stato applicato alle scene "
                "modificate e aggiunte nello Stripboard."
            )

        self._diff_label.setText("\n".join(lines))
        self._diff_widget.setVisible(True)

    def _on_row_double_click(self, index):
        """Imposta la revisione selezionata come corrente."""
        row = index.row()
        rev_id_item = self._table.item(row, 0)
        if rev_id_item is None:
            return
        rev_id = rev_id_item.data(Qt.ItemDataRole.UserRole)
        if rev_id is None:
            return
        from gliamispo.revisions.revision_manager import RevisionManager
        mgr = RevisionManager(self._container.database)
        mgr.set_current(self._project_id, rev_id)
        self._reload()