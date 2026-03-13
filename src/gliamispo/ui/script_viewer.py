import json
import re
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSplitter, QScrollArea, QFrame, QSizePolicy,
    QLineEdit, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QMenu,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QCursor, QFont, QFontMetrics, QIcon
from gliamispo.ui import theme
from gliamispo.parsing.raw_block_fixer import fix_raw_blocks
from gliamispo.models.eighths import Eighths
from gliamispo.models.scene_element import BreakdownCategory




# ──────────────────────────────────────────────────────────────────────────────
# _wrap_h(): calcola l'altezza di un testo con word-wrap
#
# PROBLEMA RADICE DEL BUG DI CLIPPING:
# - QLabel.hasHeightForWidth() → False di default → QVBoxLayout usa sizeHint()
# - sizeHint().height() = 1 riga → layout alloca spazio insufficiente
# - Anche con WrapLabel (override di hasHeightForWidth), la catena si spezza
#   sul QWidget container intermedio che NON propagha heightForWidth.
#
# SOLUZIONE: calcolo esplicito con QFontMetrics + setFixedHeight sul container.
# QFontMetrics usa il font passato direttamente (non self.fontMetrics() che
# ritorna il font di sistema quando il font è impostato via setStyleSheet).
# ──────────────────────────────────────────────────────────────────────────────

def _wrap_h(text: str, avail_w: int, font: "QFont", pad: int = 8) -> int:
    """
    Altezza in pixel necessaria per disegnare `text` con word-wrap
    in `avail_w` pixel usando `font`. `pad` = margine verticale aggiuntivo.
    Usa QFontMetrics(font) — non self.fontMetrics() — per metriche corrette
    anche quando il font è impostato via setStyleSheet().
    """
    fm = QFontMetrics(font)
    rect = fm.boundingRect(
        0, 0, max(avail_w, 1), 100_000,
        Qt.TextFlag.TextWordWrap | Qt.TextFlag.TextExpandTabs,
        text,
    )
    return rect.height() + pad


# ──────────────────────────────────────────────────────────────────────────────
# Costanti di impaginazione cinematografica (standard industria, Courier 15pt)
# ──────────────────────────────────────────────────────────────────────────────

# Percentuali indentazione (standard US Letter screenplay)
_US_LETTER_CHARS = 60

def _calc_page_metrics():
    fm = QFontMetrics(_screenplay_font(15))
    char_w = fm.horizontalAdvance('X')
    text_w = char_w * _US_LETTER_CHARS
    margin_l = int(text_w * 1.5 / 6.0)
    margin_r = int(text_w * 1.0 / 6.0)
    page_w = margin_l + text_w + margin_r
    return page_w, margin_l, margin_r, text_w

# Indentazioni screenplay standard (proporzione su text area 6.0"):
_PCT_CHARACTER_L = 0.37
_PCT_PAREN_L     = 0.27
_PCT_PAREN_R     = 0.32
_PCT_DIALOGUE_L  = 0.17
_PCT_DIALOGUE_R  = 0.25


_FONT_CSS = "font-family: 'Courier New', Courier, monospace;"


def _screenplay_font(size=15, bold=False):
    f = QFont("Courier New", size)
    f.setBold(bold)
    f.setStyleHint(QFont.StyleHint.TypeWriter)
    f.setFixedPitch(True)
    return f


def _sp_css(size=15, bold=False, extra=""):
    w = "bold" if bold else "normal"
    return f"{_FONT_CSS} font-size: {size}pt; font-weight: {w}; {extra}"


# ──────────────────────────────────────────────────────────────────────────────
# F1 helper — durata scena in ottavi
# ──────────────────────────────────────────────────────────────────────────────

def _format_scene_duration(scene):
    ws = scene.get("page_start_whole", 0) or 0
    es = scene.get("page_start_eighths", 0) or 0
    we = scene.get("page_end_whole", 0) or 0
    ee = scene.get("page_end_eighths", 0) or 0
    dur = Eighths(we, ee) - Eighths(ws, es)
    if dur.total_eighths <= 0:
        return ""
    if dur.whole == 0:
        return f"{dur.eighths}/8 pag"
    if dur.eighths == 0:
        return f"{dur.whole} pag"
    return f"{dur.whole} {dur.eighths}/8 pag"


# ──────────────────────────────────────────────────────────────────────────────
# F3 — Dialog per taggare un termine inline
# ──────────────────────────────────────────────────────────────────────────────

class TagElementDialog(QDialog):
    def __init__(self, text_hint="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tagga elemento")
        self.setMinimumWidth(360)
        layout = QFormLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self._name_edit = QLineEdit(text_hint)
        self._name_edit.setPlaceholderText("es. Pistola, Mario Rossi…")
        layout.addRow("Termine:", self._name_edit)

        self._cat_combo = QComboBox()
        for cat in BreakdownCategory:
            self._cat_combo.addItem(cat.value)
        layout.addRow("Categoria:", self._cat_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _on_accept(self):
        if self._name_edit.text().strip():
            self.accept()

    def get_data(self):
        return {
            "element_name": self._name_edit.text().strip(),
            "category": self._cat_combo.currentText(),
        }


# ──────────────────────────────────────────────────────────────────────────────
# NotesPanel — blocco note laterale giallo ocra per scena
# ──────────────────────────────────────────────────────────────────────────────

class NotesPanel(QWidget):
    closed = pyqtSignal()
    note_saved = pyqtSignal(int, str)

    _BG   = "#FEFAE0"
    _BD   = "#E6C84A"
    _HEAD = "#E8B135"
    _TEXT = "#3A2E00"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene_id   = None
        self._db         = None
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._autosave)
        self.setMinimumWidth(220)
        self.setMaximumWidth(320)
        self.setStyleSheet(f"background-color: {self._BG};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setStyleSheet(
            f"background-color: {self._HEAD};"
            f" border-bottom: 1px solid {self._BD};"
        )
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(12, 8, 8, 8)
        self._title = QLabel("NOTE — SCENA")
        self._title.setFont(theme.font_ui(10, bold=True))
        self._title.setStyleSheet(f"color: {self._TEXT};")
        h_layout.addWidget(self._title, 1)
        close_btn = QPushButton("X")
        close_btn.setFixedSize(22, 22)
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.setFont(theme.font_ui(10, bold=True))
        close_btn.setStyleSheet(
            f"color: {self._TEXT}; background: transparent; border: none;"
            f"font-size: 13px;"
        )
        close_btn.clicked.connect(self.closed.emit)
        h_layout.addWidget(close_btn)
        layout.addWidget(header)

        self._hint = QLabel("")
        self._hint.setFont(theme.font_ui(9))
        self._hint.setStyleSheet(
            f"color: {self._TEXT}; opacity: 0.7;"
            f" padding: 4px 12px 2px 12px;"
            f" background-color: {self._BG};"
        )
        self._hint.setWordWrap(True)
        layout.addWidget(self._hint)

        from PyQt6.QtWidgets import QTextEdit
        self._editor = QTextEdit()
        self._editor.setPlaceholderText(
            "Scrivi qui le note di regia, logistica, "
            "problemi di scena\u2026"
        )
        self._editor.setFont(theme.font_ui(11))
        self._editor.setStyleSheet(f"""
            QTextEdit {{
                background-color: {self._BG};
                color: {self._TEXT};
                border: none;
                padding: 12px;
                line-height: 1.5;
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
        self._editor.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._editor, 1)

        self._status = QLabel("Salvato")
        self._status.setFont(theme.font_ui(9))
        self._status.setStyleSheet(
            f"color: {self._TEXT}; opacity: 0.5;"
            f" padding: 4px 12px; background-color: {self._BG};"
        )
        self._status.setVisible(False)
        layout.addWidget(self._status)

    def load_scene(self, scene_id, scene_label, db):
        self._scene_id = scene_id
        self._db       = db
        self._title.setText(f"NOTE \u2014 {scene_label.upper()}")
        self._hint.setText(scene_label)
        self._editor.blockSignals(True)
        row = db.execute(
            "SELECT scene_notes FROM scenes WHERE id = ?", (scene_id,)
        ).fetchone()
        self._editor.setPlainText(row[0] or "" if row else "")
        self._editor.blockSignals(False)
        self._status.setVisible(False)

    def _on_text_changed(self):
        self._status.setText("Modificato...")
        self._status.setVisible(True)
        self._save_timer.start(1000)

    def _autosave(self):
        if self._scene_id is None or self._db is None:
            return
        text = self._editor.toPlainText().strip() or None
        self._db.execute(
            "UPDATE scenes SET scene_notes = ? WHERE id = ?",
            (text, self._scene_id)
        )
        self._db.commit()
        self.note_saved.emit(self._scene_id, text or "")
        self._status.setText("Salvato")
        QTimer.singleShot(1500, lambda: self._status.setVisible(False))


# ──────────────────────────────────────────────────────────────────────────────
# CategorySidebar — F8 durata totale aggiunta
# ──────────────────────────────────────────────────────────────────────────────

class CategorySidebar(QWidget):
    category_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(220)
        self.setMaximumWidth(280)
        self.setStyleSheet(f"background-color: {theme.BG2.name()};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("CATEGORIE")
        header.setFont(theme.font_ui(9, bold=True))
        header.setStyleSheet(f"color: {theme.TEXT3.name()}; padding: 12px 16px 8px 16px;")
        layout.addWidget(header)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea { border: none; }")

        self._list = QWidget()
        self._list_layout = QVBoxLayout(self._list)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(0)
        self._list_layout.addStretch()
        self._scroll.setWidget(self._list)
        layout.addWidget(self._scroll, 1)

        self._stats = QWidget()
        self._stats.setStyleSheet(f"background-color: {theme.BG3.name()};")
        s_layout = QVBoxLayout(self._stats)
        s_layout.setContentsMargins(16, 10, 16, 10)
        self._scene_count = QLabel("Scene: 0")
        self._scene_count.setFont(theme.font_ui(11))
        self._scene_count.setStyleSheet(f"color: {theme.TEXT2.name()};")
        self._elem_count = QLabel("Elementi: 0")
        self._elem_count.setFont(theme.font_ui(11))
        self._elem_count.setStyleSheet(f"color: {theme.TEXT2.name()};")
        # F8 — durata totale
        self._total_dur = QLabel("Durata totale: —")
        self._total_dur.setFont(theme.font_ui(11))
        self._total_dur.setStyleSheet(f"color: {theme.TEXT2.name()};")
        self._est_min = QLabel("")
        self._est_min.setFont(theme.font_ui(10))
        self._est_min.setStyleSheet(f"color: {theme.TEXT3.name()};")
        s_layout.addWidget(self._scene_count)
        s_layout.addWidget(self._elem_count)
        s_layout.addWidget(self._total_dur)
        s_layout.addWidget(self._est_min)
        layout.addWidget(self._stats)

        self._buttons = []
        self._selected = "all"

    def load_categories(self, categories, scene_count=0, elem_count=0, total_eighths=0):
        for btn in self._buttons:
            self._list_layout.removeWidget(btn)
            btn.deleteLater()
        self._buttons.clear()

        all_btn = self._make_cat_btn("Mostra Tutto", QIcon(), sum(c for _, c in categories))
        all_btn.setChecked(True)
        self._list_layout.insertWidget(0, all_btn)
        self._buttons.append(all_btn)

        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background-color: {theme.qss_color(theme.BD1)};")
        idx = 1
        self._list_layout.insertWidget(idx, div)
        self._buttons.append(div)
        idx += 1

        for cat, count in categories:
            btn = self._make_cat_btn(cat, theme.category_qicon(cat), count)
            self._list_layout.insertWidget(idx, btn)
            self._buttons.append(btn)
            idx += 1

        self._scene_count.setText(f"Scene: {scene_count}")
        self._elem_count.setText(f"Elementi: {elem_count}")
        self._update_duration(total_eighths)

    def _update_duration(self, total_eighths):
        if total_eighths <= 0:
            self._total_dur.setText("Durata totale: —")
            self._est_min.setText("")
            return

        whole = total_eighths // 8
        eighths = total_eighths % 8
        if eighths == 0:
            dur_str = f"{whole} pag"
        elif whole == 0:
            dur_str = f"{eighths}/8 pag"
        else:
            dur_str = f"{whole} {eighths}/8 pag"

        total_seconds = total_eighths * 60 // 8
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60

        if hours > 0:
            time_str = f"~{hours}h {minutes:02d}min"
        else:
            time_str = f"~{minutes} min"

        self._total_dur.setText(f"Durata totale: {dur_str}")
        self._est_min.setText(time_str)

    def _make_cat_btn(self, label, icon, count):
        btn = QPushButton(f"  {label}   ({count})")
        if not icon.isNull():
            btn.setIcon(icon)
            btn.setIconSize(QSize(14, 14))
        btn.setFont(theme.font_ui(11))
        btn.setCheckable(True)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                color: {theme.TEXT1.name()};
                background: transparent;
                border: none;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: {theme.qss_color(theme.BD0)};
            }}
            QPushButton:checked {{
                color: {theme.GOLD.name()};
                background-color: {theme.qss_color(theme.GOLD_BG)};
                border-left: 3px solid {theme.GOLD.name()};
            }}
        """)
        btn.clicked.connect(lambda: self._on_cat_clicked(label))
        return btn

    def _on_cat_clicked(self, cat):
        self._selected = cat
        for btn in self._buttons:
            if isinstance(btn, QPushButton):
                btn.setChecked(False)
        self.category_selected.emit(cat)


# ──────────────────────────────────────────────────────────────────────────────
# ScriptContentView — F1 F2 F3 F5 F6 F7
# ──────────────────────────────────────────────────────────────────────────────

class ScriptContentView(QWidget):
    tag_added      = pyqtSignal()         # F3 — emesso dopo ogni tag salvato
    note_requested = pyqtSignal(int, str) # (scene_id, scene_label) per aprire le note

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(500)
        self.setStyleSheet(f"background-color: {theme.BG0.name()};")

        self._page_w, self._margin_l, self._margin_r, self._text_w = _calc_page_metrics()

        # F2 stato toggle highlight
        self._inline_highlight = False
        # F2/F6 cache dati
        self._all_data_cache = []
        # F3 — database e feedback
        self._db = None
        self._feedback = None
        self._search_query = ''   # BUG1 FIX — termine di ricerca attivo

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Toolbar (F2 highlight + F6 search) ────────────────────────────────
        toolbar = QWidget()
        toolbar.setStyleSheet(f"background-color: {theme.BG1.name()};")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(16, 6, 16, 6)
        tb_layout.setSpacing(8)

        # F6 — barra di ricerca
        self._search_bar = QLineEdit()
        self._search_bar.setPlaceholderText("Cerca nel testo…")
        self._search_bar.setFont(theme.font_ui(11))
        self._search_bar.setFixedWidth(240)
        self._search_bar.setStyleSheet(f"""
            QLineEdit {{
                background-color: {theme.BG0.name()};
                color: {theme.TEXT1.name()};
                border: 1px solid {theme.qss_color(theme.BD1)};
                border-radius: 4px;
                padding: 3px 10px;
            }}
            QLineEdit:focus {{
                border-color: {theme.GOLD.name()};
            }}
        """)
        self._search_bar.textChanged.connect(self._on_search)

        self._clear_btn = QPushButton("✕")
        self._clear_btn.setFixedSize(24, 24)
        self._clear_btn.setFont(theme.font_ui(10))
        self._clear_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._clear_btn.setVisible(False)
        self._clear_btn.setStyleSheet(
            f"color: {theme.TEXT3.name()}; background: transparent; border: none;"
        )
        self._clear_btn.clicked.connect(self._search_bar.clear)

        tb_layout.addWidget(self._search_bar)
        tb_layout.addWidget(self._clear_btn)
        tb_layout.addSpacing(12)

        # F2 — toggle highlight
        self._highlight_btn = QPushButton("Evidenzia nel testo")
        self._highlight_btn.setFont(theme.font_ui(10))
        self._highlight_btn.setCheckable(True)
        self._highlight_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._highlight_btn.setStyleSheet(f"""
            QPushButton {{
                color: {theme.TEXT3.name()};
                background: transparent;
                border: 1px solid {theme.qss_color(theme.BD1)};
                border-radius: 4px;
                padding: 3px 12px;
            }}
            QPushButton:checked {{
                color: {theme.GOLD.name()};
                background-color: {theme.qss_color(theme.GOLD_BG)};
                border-color: {theme.qss_color(theme.GOLD_BD)};
            }}
        """)
        self._highlight_btn.toggled.connect(self._on_highlight_toggled)
        tb_layout.addWidget(self._highlight_btn)
        tb_layout.addStretch()

        outer.addWidget(toolbar)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background-color: {theme.BG0.name()}; }}"
        )

        self._page = QWidget()
        self._page.setFixedWidth(self._page_w)
        self._page.setStyleSheet(f"background-color: {theme.BG1.name()};")

        self._content_layout = QVBoxLayout(self._page)
        self._content_layout.setContentsMargins(self._margin_l, 32, self._margin_r, 32)
        self._content_layout.setSpacing(0)
        self._content_layout.addStretch()

        self._scroll.setWidget(self._page)
        outer.addWidget(self._scroll, 1)

        # F7 — dict invece di lista per indicizzazione per scene_id
        self._scene_widgets = {}

    # ── F2 — Highlight ────────────────────────────────────────────────────────

    def _on_highlight_toggled(self, checked):
        self._inline_highlight = checked
        if self._all_data_cache:
            self._render_scenes(self._all_data_cache)

    def _build_highlight_map(self, elements):
        mapping = []
        for el in elements:
            name = el.get("element_name", "").strip()
            cat  = el.get("category", "")
            if name:
                mapping.append((name, cat))
        mapping.sort(key=lambda x: len(x[0]), reverse=True)
        return mapping

    def _highlight_text(self, text, highlight_map):
        if not highlight_map:
            return text
        import html as html_mod
        safe = html_mod.escape(text)
        for name, cat in highlight_map:
            color = theme.CATEGORY_COLORS.get(cat, "#888888")
            safe_name = html_mod.escape(name)
            pattern = re.compile(re.escape(safe_name), re.IGNORECASE)
            repl = (
                f'<span style="text-decoration:underline;'
                f'text-decoration-color:{color};'
                f'text-underline-offset:3px;'
                f'color:{color};font-weight:bold;">'
                f'\\g<0></span>'
            )
            safe = pattern.sub(repl, safe)
        return safe

    def _highlight_search(self, text, query):
        if not query:
            return text
        import html as html_mod
        safe = html_mod.escape(text)
        safe_q = html_mod.escape(query)
        pattern = re.compile(re.escape(safe_q), re.IGNORECASE)
        repl = (
            '<span style="background-color:#FFE066;'
            'color:#1C2A3A;font-weight:bold;'
            'border-radius:2px;padding:0 2px;">'
            '\\g<0></span>'
        )
        return pattern.sub(repl, safe)

    def _highlight_search_in_html(self, html_text, query):
        import html as html_mod
        safe_q = html_mod.escape(query)
        pat = re.compile(re.escape(safe_q), re.IGNORECASE)
        repl = (
            '<span style="background-color:#FFE066;'
            'color:#1C2A3A;font-weight:bold;">'
            '\\g<0></span>'
        )
        parts = re.split(r'(<[^>]+>)', html_text)
        for i, part in enumerate(parts):
            if not part.startswith('<'):
                parts[i] = pat.sub(repl, part)
        return ''.join(parts)

    # ── F6 — Ricerca full-text ────────────────────────────────────────────────

    def _on_search(self, query):
        query = query.strip()
        self._search_query = query          # salva il termine attivo
        self._clear_btn.setVisible(bool(query))
        if not query:
            self._search_query = ''
            if self._all_data_cache:
                self._render_scenes(self._all_data_cache)
            return
        q_lower = query.lower()
        matched = []
        for scene, elements in (self._all_data_cache or []):
            slug = f"{scene.get('scene_number','')} {scene.get('location','')}".lower()
            blocks_text = " ".join(
                b.get("text", "") for b in (scene.get("raw_blocks") or [])
            ).lower()
            synopsis = (scene.get("synopsis", "") or "").lower()
            if q_lower in slug or q_lower in blocks_text or q_lower in synopsis:
                matched.append((scene, elements))
        self._render_scenes(matched)
        if matched:
            first_id = matched[0][0]["id"]
            QTimer.singleShot(50, lambda sid=first_id:
                self.scroll_to_scene(sid))

    # ── F7 — Scroll a scena ───────────────────────────────────────────────────

    def scroll_to_scene(self, scene_id):
        widget = self._scene_widgets.get(scene_id)
        if widget:
            self._scroll.ensureWidgetVisible(widget)

    # ── Caricamento scene ─────────────────────────────────────────────────────

    def load_scenes(self, scenes_with_elements):
        self._all_data_cache = scenes_with_elements
        self._render_scenes(scenes_with_elements)

    def _render_scenes(self, scenes_with_elements):
        self.clear()
        for scene, elements in scenes_with_elements:
            hmap  = self._build_highlight_map(elements) if self._inline_highlight else None
            sterm = self._search_query
            block = self._make_scene_block(scene, elements, hmap, sterm)
            self._content_layout.insertWidget(
                self._content_layout.count() - 1, block
            )
            self._scene_widgets[scene["id"]] = block

    def _make_scene_block(self, scene, elements, hmap=None, sterm=""):
        block = QWidget()
        block.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(block)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(0)

        scene_id = scene.get("id", 0)

        # ── SLUG LINE + F1 badge ottavi ───────────────────────────────────────
        ie  = scene.get("int_ext", "")
        loc = scene.get("location", "")
        dn  = scene.get("day_night", "")
        num = scene.get("scene_number", "")
        slug_text = f"{num}  {ie}. {loc} – {dn}" if num else f"{ie}. {loc} – {dn}"

        _slug_font = _screenplay_font(16, bold=True)
        slug = QLabel(slug_text.upper())
        slug.setWordWrap(True)
        slug.setStyleSheet(
            f"{_sp_css(16, bold=True)}"
            f" color: {theme.TEXT0.name()};"
            f" padding: 6px 0px 6px 0px;"
            f" border-top: 2px solid {theme.qss_color(theme.BD1)};"
        )
        # Badge durata + pulsante Note occupano ~200px nella riga HBox;
        # calcola altezza sulla larghezza effettiva per evitare clipping.
        _slug_side_reserve = 200
        slug_avail_w = max(int(self._text_w) - _slug_side_reserve, 100)
        slug.setFixedHeight(_wrap_h(slug_text.upper(), slug_avail_w,
                                    _slug_font, pad=14))

        # F1 — badge durata in ottavi + pulsante Note
        dur_text = _format_scene_duration(scene)
        slug_row = QWidget()
        slug_row_layout = QHBoxLayout(slug_row)
        slug_row_layout.setContentsMargins(0, 0, 0, 0)
        slug_row_layout.setSpacing(8)
        slug_row_layout.addWidget(slug, 1)
        if dur_text:
            dur_lbl = QLabel(dur_text)
            dur_lbl.setFont(theme.font_mono(10, bold=True))
            dur_lbl.setStyleSheet(f"""
                color: {theme.TEXT2.name()};
                background-color: {theme.BG0.name()};
                border: 1px solid {theme.qss_color(theme.BD1)};
                border-radius: 4px;
                padding: 1px 8px;
            """)
            slug_row_layout.addWidget(dur_lbl)
        has_note = bool((scene.get("scene_notes") or "").strip())
        note_btn = QPushButton("\u270e Note \u25cf" if has_note else "\u270e Note")
        note_btn.setFont(theme.font_ui(9, bold=has_note))
        note_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        note_btn_color = theme.GOLD.name() if has_note else theme.TEXT3.name()
        note_btn.setStyleSheet(f"""
            QPushButton {{
                color: {note_btn_color};
                background: transparent;
                border: 1px solid {note_btn_color};
                border-radius: 4px;
                padding: 1px 10px;
                font-size: 9pt;
            }}
            QPushButton:hover {{
                background-color: {theme.qss_color(theme.GOLD_BG)};
                color: {theme.GOLD.name()};
                border-color: {theme.GOLD.name()};
            }}
        """)
        scene_label = f"SC. {num} \u2014 {loc}" if num else loc
        note_btn.clicked.connect(
            lambda _, sid=scene_id, lbl=scene_label:
                self.note_requested.emit(sid, lbl)
        )
        slug_row_layout.addWidget(note_btn)
        layout.addWidget(slug_row)

        # ── BLOCCHI DI TESTO ──────────────────────────────────────────────────
        raw_blocks = scene.get("raw_blocks") or []

        if raw_blocks:
            prev_type = None
            for b in raw_blocks:
                btype = b.get("type", "action")
                btext = b.get("text", "")
                if not btext.strip():
                    continue
                w = self._make_block_widget(btype, btext, prev_type, hmap, scene_id, sterm)
                layout.addWidget(w)
                prev_type = btype
        else:
            synopsis = scene.get("synopsis", "")
            if synopsis:
                for line in synopsis.splitlines():
                    if line.strip():
                        _syn_font = _screenplay_font(15)
                        lbl = QLabel(line)
                        lbl.setWordWrap(True)
                        lbl.setStyleSheet(
                            f"{_sp_css()}"
                            f" color: {theme.TEXT1.name()}; padding: 2px 0;"
                        )
                        lbl.setFixedHeight(_wrap_h(line, int(self._text_w),
                                                   _syn_font))
                        layout.addWidget(lbl)

        # ── ELEMENTI TAG ──────────────────────────────────────────────────────
        if elements:
            el_row = self._make_elements_row(elements)
            layout.addWidget(el_row)

        spacer = QWidget()
        spacer.setFixedHeight(24)
        layout.addWidget(spacer)

        return block

    def _indent_px(self, pct):
        return max(int(self._text_w * pct), 20)

    def _make_block_widget(self, btype, text, prev_type, hmap=None, scene_id=0, sterm=""):
        font    = _screenplay_font(15)
        font_b  = _screenplay_font(15, bold=True)
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        if btype == "action":
            top = 12 if prev_type is None else (6 if prev_type == "action" else 16)
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, top, 0, 0)
            layout.setSpacing(0)
            lbl = QLabel()
            lbl.setWordWrap(True)
            lbl.setStyleSheet(f"{_sp_css()} color: {theme.TEXT1.name()};")
            if hmap or sterm:
                import html
                lbl.setTextFormat(Qt.TextFormat.RichText)
                display = self._highlight_text(text, hmap) if hmap else html.escape(text)
                if sterm:
                    display = self._highlight_search_in_html(display, sterm)
                lbl.setText(display)
            else:
                lbl.setText(text)
            h = _wrap_h(text, int(self._text_w), font)
            lbl.setFixedHeight(h)
            container.setFixedHeight(top + h)
            layout.addWidget(lbl)

        elif btype == "character":
            l_px = self._indent_px(_PCT_CHARACTER_L)
            layout = QVBoxLayout(container)
            layout.setContentsMargins(l_px, 16, 0, 0)
            layout.setSpacing(0)
            lbl = QLabel(text.upper())
            lbl.setStyleSheet(f"{_sp_css()} color: {theme.TEXT0.name()};")
            fm = QFontMetrics(font)
            h = fm.height() + 4
            lbl.setFixedHeight(h)
            container.setFixedHeight(16 + h)
            layout.addWidget(lbl)

        elif btype == "parenthetical":
            l_px = self._indent_px(_PCT_PAREN_L)
            r_px = self._indent_px(_PCT_PAREN_R)
            layout = QVBoxLayout(container)
            layout.setContentsMargins(l_px, 0, r_px, 0)
            layout.setSpacing(0)
            avail = max(int(self._text_w - l_px - r_px), 20)
            lbl = QLabel()
            lbl.setWordWrap(True)
            lbl.setStyleSheet(f"{_sp_css()} color: {theme.TEXT2.name()};")
            if hmap or sterm:
                import html
                lbl.setTextFormat(Qt.TextFormat.RichText)
                display = self._highlight_text(text, hmap) if hmap else html.escape(text)
                if sterm:
                    display = self._highlight_search_in_html(display, sterm)
                lbl.setText(display)
            else:
                lbl.setText(text)
            h = _wrap_h(text, avail, font)
            lbl.setFixedHeight(h)
            container.setFixedHeight(h)
            layout.addWidget(lbl)

        elif btype == "dialogue":
            l_px = self._indent_px(_PCT_DIALOGUE_L)
            r_px = self._indent_px(_PCT_DIALOGUE_R)
            layout = QVBoxLayout(container)
            layout.setContentsMargins(l_px, 0, r_px, 0)
            layout.setSpacing(0)
            avail = max(int(self._text_w - l_px - r_px), 20)
            lbl = QLabel()
            lbl.setWordWrap(True)
            lbl.setStyleSheet(f"{_sp_css()} color: {theme.TEXT1.name()};")
            if hmap or sterm:
                import html
                lbl.setTextFormat(Qt.TextFormat.RichText)
                display = self._highlight_text(text, hmap) if hmap else html.escape(text)
                if sterm:
                    display = self._highlight_search_in_html(display, sterm)
                lbl.setText(display)
            else:
                lbl.setText(text)
            h = _wrap_h(text, avail, font)
            lbl.setFixedHeight(h)
            container.setFixedHeight(h)
            layout.addWidget(lbl)

        elif btype == "transition":
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 16, 0, 4)
            layout.setSpacing(0)
            lbl = QLabel(text.upper())
            lbl.setWordWrap(True)
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            lbl.setStyleSheet(f"{_sp_css(bold=True)} color: {theme.TEXT2.name()};")
            h = _wrap_h(text.upper(), int(self._text_w), font_b)
            lbl.setFixedHeight(h)
            container.setFixedHeight(16 + 4 + h)
            layout.addWidget(lbl)

        else:
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            lbl = QLabel(text)
            lbl.setWordWrap(True)
            lbl.setStyleSheet(f"{_sp_css()} color: {theme.TEXT1.name()};")
            h = _wrap_h(text, int(self._text_w), font)
            lbl.setFixedHeight(h)
            container.setFixedHeight(h)
            layout.addWidget(lbl)

        # F3 — testo selezionabile + context menu per tagging inline
        if btype in ("action", "dialogue", "parenthetical"):
            lbl.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            if self._db is not None:
                lbl.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                lbl.customContextMenuRequested.connect(
                    lambda pos, l=lbl, sid=scene_id:
                        self._on_block_context(l.mapToGlobal(pos), sid, l)
                )

        return container

    def _make_elements_row(self, elements):
        wrap = QWidget()
        wrap.setStyleSheet(
            f"background-color: {theme.qss_color(theme.BG2)};"
            f" border-radius: 4px; margin-top: 8px;"
        )
        layout = QHBoxLayout(wrap)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        for el in elements[:12]:
            cat  = el.get("category", "")
            name = el.get("element_name", "")
            note = el.get("notes", "") or ""
            c    = theme.category_color(cat)
            tag  = QLabel(f"{name}")
            tag.setFont(theme.font_ui(9))
            tag_style = f"""
                color: {c.name()};
                background-color: {theme.qss_color(theme.category_bg(cat))};
                border: 1px solid {theme.qss_color(theme.category_border(cat))};
                border-radius: 3px;
                padding: 2px 6px;
            """
            # F5 — nota come tooltip + bordo sinistro colorato
            if note:
                tag.setToolTip(note)
                tag_style += f" border-left: 3px solid {c.name()};"
            tag.setStyleSheet(tag_style)
            layout.addWidget(tag)
        layout.addStretch()
        return wrap

    # ── F3 — Tagging inline ───────────────────────────────────────────────────

    def _on_block_context(self, global_pos, scene_id, lbl=None):
        selected = lbl.selectedText().strip() if lbl else ""
        menu = QMenu(self)
        copy_action = menu.addAction("Copia")
        copy_action.setEnabled(bool(selected))
        menu.addSeparator()
        cat_menu = menu.addMenu("Categoria")
        cat_menu.setEnabled(bool(selected))
        cat_actions = {}
        for cat in BreakdownCategory:
            a = cat_menu.addAction(cat.value)
            a.setIcon(theme.category_qicon(cat.value))
            cat_actions[a] = cat.value
        result = menu.exec(global_pos)
        if not result:
            return
        if result == copy_action and selected:
            from PyQt6.QtWidgets import QApplication
            QApplication.clipboard().setText(selected)
        elif result in cat_actions and selected:
            self._tag_element_direct(scene_id, selected, cat_actions[result])

    def _tag_element_direct(self, scene_id, element_name, category):
        if not self._db:
            return
        try:
            self._db.execute(
                "INSERT OR IGNORE INTO scene_elements"
                " (scene_id, category, element_name, ai_suggested, user_verified)"
                " VALUES (?, ?, ?, 0, 1)",
                (scene_id, category, element_name)
            )
            self._db.commit()
        except Exception:
            pass
        self.tag_added.emit()

    def _tag_element(self, scene_id, hint=""):
        if not self._db:
            return
        dlg = TagElementDialog(text_hint=hint, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        data = dlg.get_data()
        try:
            self._db.execute(
                "INSERT OR IGNORE INTO scene_elements"
                " (scene_id, category, element_name, ai_suggested, user_verified)"
                " VALUES (?, ?, ?, 0, 1)",
                (scene_id, data["category"], data["element_name"])
            )
            self._db.commit()
        except Exception:
            pass
        self.tag_added.emit()

    # ── Utility ───────────────────────────────────────────────────────────────

    def clear(self):
        for w in self._scene_widgets.values():
            self._content_layout.removeWidget(w)
            w.deleteLater()
        self._scene_widgets.clear()


# ──────────────────────────────────────────────────────────────────────────────
# ScriptViewerView — coordina sidebar, content e DB
# ──────────────────────────────────────────────────────────────────────────────

class ScriptViewerView(QWidget):
    def __init__(self, container, parent=None):
        super().__init__(parent)
        self._container = container
        self._project_id = None
        self._all_data = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        self._splitter = splitter

        self._sidebar = CategorySidebar()

        self._notes_panel = NotesPanel()
        self._notes_panel.setVisible(False)

        self._content = ScriptContentView()
        self._content._db = container.database

        splitter.addWidget(self._sidebar)
        splitter.addWidget(self._notes_panel)
        splitter.addWidget(self._content)
        splitter.setSizes([250, 0, 650])
        splitter.setCollapsible(1, True)

        layout.addWidget(splitter)

        self._sidebar.category_selected.connect(self._filter_by_category)
        self._notes_panel.closed.connect(self._close_notes)
        self._content.note_requested.connect(self._open_notes)
        self._notes_panel.note_saved.connect(self._on_note_saved)
        self._content.tag_added.connect(lambda: self.load_project(self._project_id))

    def _open_notes(self, scene_id, scene_label):
        db = self._container.database
        self._notes_panel.load_scene(scene_id, scene_label, db)
        if not self._notes_panel.isVisible():
            self._notes_panel.setVisible(True)
            sizes = self._splitter.sizes()
            sidebar_w = sizes[0]
            total = sum(sizes)
            notes_w = 280
            content_w = max(total - sidebar_w - notes_w, 400)
            self._splitter.setSizes([sidebar_w, notes_w, content_w])

    def _close_notes(self):
        sizes = self._splitter.sizes()
        sidebar_w = sizes[0]
        total = sum(sizes)
        self._notes_panel.setVisible(False)
        self._splitter.setSizes([sidebar_w, 0, total - sidebar_w])

    def _on_note_saved(self, scene_id, text):
        for i, (scene, elements) in enumerate(self._all_data):
            if scene["id"] == scene_id:
                scene["scene_notes"] = text
                break
        widget = self._content._scene_widgets.get(scene_id)
        if widget:
            for child in widget.findChildren(QPushButton):
                if "Note" in child.text():
                    has = bool(text.strip())
                    child.setText("\u270e Note \u25cf" if has else "\u270e Note")
                    color = theme.GOLD.name() if has else theme.TEXT3.name()
                    child.setStyleSheet(f"""
                        QPushButton {{
                            color: {color};
                            background: transparent;
                            border: 1px solid {color};
                            border-radius: 4px;
                            padding: 1px 10px;
                            font-size: 9pt;
                        }}
                        QPushButton:hover {{
                            background-color: {theme.qss_color(theme.GOLD_BG)};
                            color: {theme.GOLD.name()};
                            border-color: {theme.GOLD.name()};
                        }}
                    """)
                    break

    def load_project(self, project_id):
        self._project_id = project_id
        db = self._container.database

        # F1 — aggiunge le 4 colonne ottavi alla query + scene_notes
        scenes = db.execute(
            "SELECT id, scene_number, location, int_ext, day_night, synopsis, raw_blocks, "
            "page_start_whole, page_start_eighths, page_end_whole, page_end_eighths, "
            "scene_notes "
            "FROM scenes WHERE project_id = ? ORDER BY id", (project_id,)
        ).fetchall()

        self._all_data = []
        cat_counts = {}
        total_elements = 0
        total_eighths = 0  # F8

        for s in scenes:
            raw_blocks = json.loads(s[6]) if s[6] else []
            if raw_blocks:
                fixed, n_changes = fix_raw_blocks(raw_blocks)
                if n_changes > 0:
                    raw_blocks = fixed
                    db.execute(
                        "UPDATE scenes SET raw_blocks = ? WHERE id = ?",
                        (json.dumps(fixed, ensure_ascii=False), s[0])
                    )
                    db.commit()
            # F1 — ottavi nel dict scena + scene_notes
            scene = {
                "id": s[0], "scene_number": s[1], "location": s[2],
                "int_ext": s[3], "day_night": s[4], "synopsis": s[5],
                "raw_blocks": raw_blocks,
                "page_start_whole":   s[7],
                "page_start_eighths": s[8],
                "page_end_whole":     s[9],
                "page_end_eighths":   s[10],
                "scene_notes":        s[11] or "",
            }
            # F8 — accumula ottavi totali
            ws = s[7] or 0; es = s[8] or 0
            we = s[9] or 0; ee = s[10] or 0
            dur = (we * 8 + ee) - (ws * 8 + es)
            if dur > 0:
                total_eighths += dur

            # F5 — aggiunge notes alla query scene_elements
            elements = db.execute(
                "SELECT category, element_name, notes FROM scene_elements "
                "WHERE scene_id = ? ORDER BY category, element_name", (s[0],)
            ).fetchall()
            el_list = [
                {"category": e[0], "element_name": e[1], "notes": e[2] or ""}
                for e in elements
            ]
            self._all_data.append((scene, el_list))

            for e in el_list:
                cat_counts[e["category"]] = cat_counts.get(e["category"], 0) + 1
                total_elements += 1

        categories = sorted(cat_counts.items())
        # F8 — passa total_eighths alla sidebar
        self._sidebar.load_categories(categories, len(scenes), total_elements,
                                      total_eighths=total_eighths)
        self._content.load_scenes(self._all_data)

    def _filter_by_category(self, cat):
        if cat == "Mostra Tutto":
            self._content.load_scenes(self._all_data)
            # F8 — ricalcola totale su tutte le scene
            total_eighths = sum(
                max((s.get("page_end_whole", 0) or 0) * 8 + (s.get("page_end_eighths", 0) or 0)
                    - (s.get("page_start_whole", 0) or 0) * 8 - (s.get("page_start_eighths", 0) or 0), 0)
                for s, _ in self._all_data
            )
            self._sidebar._update_duration(total_eighths)
            return

        filtered = []
        first_scene_id = None
        for scene, elements in self._all_data:
            matching = [e for e in elements if e["category"] == cat]
            if matching:
                filtered.append((scene, matching))
                if first_scene_id is None:
                    first_scene_id = scene["id"]

        self._content.load_scenes(filtered)

        # F7 — scroll alla prima scena della categoria
        if first_scene_id is not None:
            QTimer.singleShot(50, lambda sid=first_scene_id:
                self._content.scroll_to_scene(sid))

        # F8 — aggiorna durata filtrata
        filtered_eighths = sum(
            max((s.get("page_end_whole", 0) or 0) * 8 + (s.get("page_end_eighths", 0) or 0)
                - (s.get("page_start_whole", 0) or 0) * 8 - (s.get("page_start_eighths", 0) or 0), 0)
            for s, _ in filtered
        )
        self._sidebar._update_duration(filtered_eighths)

    def clear(self):
        self._project_id = None
        self._all_data = []
        self._sidebar.load_categories([])
        self._content.clear()
        self._close_notes()
