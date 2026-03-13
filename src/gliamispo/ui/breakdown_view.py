import re
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSplitter, QScrollArea, QFrame, QSizePolicy, QMenu,
    QDialog, QLineEdit, QComboBox, QDialogButtonBox, QFormLayout,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QCursor, QPainter, QColor, QAction, QFont, QFontMetrics
from gliamispo.ui import theme
from gliamispo.models.eighths import Eighths
from gliamispo.models.scene_element import BreakdownCategory
from gliamispo.parsing.raw_block_fixer import fix_raw_blocks


# ──────────────────────────────────────────────────────────────────────────────
# Dialogo: aggiunta elemento manuale
# ──────────────────────────────────────────────────────────────────────────────

class AddElementDialog(QDialog):
    """Finestra di dialogo per aggiungere un elemento manualmente."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Aggiungi Elemento")
        self.setMinimumWidth(360)

        layout = QFormLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("es. Pistola, Mario Rossi, Steadicam…")
        layout.addRow("Nome:", self._name_edit)

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
        else:
            self._name_edit.setFocus()

    def get_data(self) -> dict:
        return {
            "element_name": self._name_edit.text().strip(),
            "category": self._cat_combo.currentText(),
        }


# ──────────────────────────────────────────────────────────────────────────────
# Dialogo: cambio categoria elemento
# ──────────────────────────────────────────────────────────────────────────────

class ChangeCategoryDialog(QDialog):
    """Seleziona una nuova categoria per un elemento esistente."""

    def __init__(self, current_category: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cambia Categoria")
        self.setMinimumWidth(300)

        layout = QFormLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self._cat_combo = QComboBox()
        for cat in BreakdownCategory:
            self._cat_combo.addItem(cat.value)

        # Pre-seleziona categoria corrente
        idx = self._cat_combo.findText(current_category)
        if idx >= 0:
            self._cat_combo.setCurrentIndex(idx)

        layout.addRow("Nuova categoria:", self._cat_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_category(self) -> str:
        return self._cat_combo.currentText()


# ──────────────────────────────────────────────────────────────────────────────
# Riga singola nella lista scene
# ──────────────────────────────────────────────────────────────────────────────

class SceneListRow(QFrame):
    clicked = pyqtSignal(int)

    def __init__(self, scene, parent=None):
        super().__init__(parent)
        self._scene_id = scene["id"]
        self._selected = False
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedHeight(76)

        strip_color = theme.strip_color_for(
            scene.get("int_ext"), scene.get("day_night")
        )

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 12, 0)
        main_layout.setSpacing(0)

        # Color strip
        strip = QFrame()
        strip.setFixedWidth(4)
        strip.setStyleSheet(f"background-color: {strip_color.name()};")
        main_layout.addWidget(strip)

        # Content
        content = QVBoxLayout()
        content.setContentsMargins(12, 8, 0, 8)
        content.setSpacing(2)

        # Row 1: scene number + IE badge + page badge
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        num_label = QLabel(scene.get("scene_number", ""))
        num_label.setFont(theme.font_mono(18, bold=True))
        num_label.setStyleSheet(f"color: {theme.TEXT0.name()};")
        row1.addWidget(num_label)

        ie = scene.get("int_ext", "")
        if ie:
            ie_label = QLabel(ie)
            ie_label.setFont(theme.font_mono(9, bold=True))
            ie_color = theme.strip_color_for(ie, scene.get("day_night"))
            ie_label.setStyleSheet(f"""
                color: white;
                background-color: {ie_color.name()};
                border-radius: 3px;
                padding: 1px 6px;
            """)
            row1.addWidget(ie_label)

        row1.addStretch()

        # Page badge
        dur = self._format_duration(scene)
        if dur:
            page_label = QLabel(dur)
            page_label.setFont(theme.font_mono(10, bold=True))
            page_label.setStyleSheet(f"""
                color: {theme.TEXT2.name()};
                background-color: {theme.BG0.name()};
                border: 1px solid {theme.qss_color(theme.BD1)};
                border-radius: 4px;
                padding: 1px 8px;
            """)
            row1.addWidget(page_label)

        content.addLayout(row1)

        # Row 2: location
        loc = scene.get("location", "")
        loc_label = QLabel(loc.upper() if loc else "")
        loc_label.setFont(theme.font_ui(11))
        loc_label.setStyleSheet(f"color: {theme.TEXT1.name()};")
        loc_label.setMaximumWidth(220)
        content.addWidget(loc_label)

        # Row 3: cast abbreviations
        # FIX 2 — cast_abbrev ora viene passato da load_project()
        cast_text = scene.get("cast_abbrev", "")
        if cast_text:
            cast_label = QLabel(cast_text)
            cast_label.setFont(theme.font_ui(10, bold=True))
            cast_label.setStyleSheet(f"color: {theme.category_color('Cast').name()};")
            content.addWidget(cast_label)

        main_layout.addLayout(content, 1)
        self._update_style()

    def _format_duration(self, scene):
        w_s = scene.get("page_start_whole", 0) or 0
        e_s = scene.get("page_start_eighths", 0) or 0
        w_e = scene.get("page_end_whole", 0) or 0
        e_e = scene.get("page_end_eighths", 0) or 0
        dur = Eighths(w_e, e_e) - Eighths(w_s, e_s)
        if dur.total_eighths <= 0:
            return None
        return f"{dur} pag"

    def set_selected(self, selected):
        self._selected = selected
        self._update_style()

    def _update_style(self):
        bg = theme.BG0.name() if self._selected else theme.BG1.name()
        self.setStyleSheet(
            f"SceneListRow {{ background-color: {bg}; }}"
            f"SceneListRow:hover {{ background-color: {theme.BG0.name()}; }}"
        )

    def mousePressEvent(self, event):
        self.clicked.emit(self._scene_id)


# ──────────────────────────────────────────────────────────────────────────────
# Colonna lista scene
# ──────────────────────────────────────────────────────────────────────────────

class SceneListColumn(QWidget):
    scene_selected = pyqtSignal(int)
    add_scene_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(268)
        self.setMaximumWidth(320)
        self.setStyleSheet(f"background-color: {theme.BG1.name()};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(16, 12, 16, 8)

        label = QLabel("SCENE")
        label.setFont(theme.font_ui(9, bold=True))
        label.setStyleSheet(f"color: {theme.TEXT3.name()};")
        h_layout.addWidget(label)

        self._count_label = QLabel("0")
        self._count_label.setFont(theme.font_ui(11, bold=True))
        self._count_label.setStyleSheet(f"""
            color: {theme.TEXT0.name()};
            background-color: {theme.BG0.name()};
            border-radius: 10px;
            padding: 2px 8px;
        """)
        h_layout.addWidget(self._count_label)
        h_layout.addStretch()

        add_btn = QPushButton("+ Scena")
        add_btn.setFont(theme.font_ui(10))
        add_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        add_btn.setStyleSheet(f"""
            QPushButton {{
                color: {theme.GOLD.name()};
                background: transparent;
                border: none;
                padding: 4px 8px;
            }}
            QPushButton:hover {{ color: {theme.GOLD_DARK.name()}; }}
        """)
        add_btn.clicked.connect(self.add_scene_requested)
        h_layout.addWidget(add_btn)

        layout.addWidget(header)

        # Scroll area for scenes
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea { border: none; }")

        self._list_widget = QWidget()
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(0)
        self._list_layout.addStretch()
        self._scroll.setWidget(self._list_widget)
        layout.addWidget(self._scroll, 1)

        # Footer stats
        footer = QWidget()
        footer.setStyleSheet(f"background-color: {theme.BG3.name()};")
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(16, 8, 16, 8)

        self._stats_scenes = self._make_stat("0", "SCENE")
        self._stats_elements = self._make_stat("0", "EL. TOT.")
        self._stats_pages = self._make_stat("0", "PAG.")

        f_layout.addWidget(self._stats_scenes)
        f_layout.addWidget(self._stats_elements)
        f_layout.addWidget(self._stats_pages)
        layout.addWidget(footer)

        self._rows = []
        self._selected_id = None

    def _make_stat(self, value, label):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(0)
        l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v = QLabel(value)
        v.setFont(theme.font_ui(18, bold=True))
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.setStyleSheet(f"color: {theme.TEXT0.name()};")
        lb = QLabel(label)
        lb.setFont(theme.font_ui(8))
        lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lb.setStyleSheet(f"color: {theme.TEXT3.name()};")
        l.addWidget(v)
        l.addWidget(lb)
        w._value_label = v
        return w

    def load_scenes(self, scenes, element_count=0, total_pages="0"):
        for row in self._rows:
            self._list_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()

        for s in scenes:
            row = SceneListRow(s)
            row.clicked.connect(self._on_row_clicked)
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)
            self._rows.append(row)

        self._count_label.setText(str(len(scenes)))
        self._stats_scenes._value_label.setText(str(len(scenes)))
        self._stats_elements._value_label.setText(str(element_count))
        self._stats_pages._value_label.setText(total_pages)

    def _on_row_clicked(self, scene_id):
        self._selected_id = scene_id
        for row in self._rows:
            row.set_selected(row._scene_id == scene_id)
        self.scene_selected.emit(scene_id)


# ──────────────────────────────────────────────────────────────────────────────
# Colonna dettaglio scena
# ──────────────────────────────────────────────────────────────────────────────

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


# ── US Letter page metrics ──────────────────────────────────────────────────
# Standard screenplay: 8.5"×11", left margin 1.5", right margin 1.0"
# Text area = 6.0" → ~60 Courier characters per line.
# Calcolo larghezza pagina fissa basata su font metrics reali.
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
# Character cue: 2.2" dal bordo sinistro testo → 37%
# Parentetica:   1.6" sin → 27%, 1.9" dx → 32%
# Dialogo:       1.0" sin → 17%, 1.5" dx → 25%
_PCT_CHARACTER_L = 0.37
_PCT_PAREN_L     = 0.27
_PCT_PAREN_R     = 0.32
_PCT_DIALOGUE_L  = 0.17
_PCT_DIALOGUE_R  = 0.25


class SceneDetailColumn(QWidget):
    highlight_toggled = pyqtSignal(bool)
    tag_requested = pyqtSignal(int, str, str)  # (scene_id, element_name, category)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {theme.BG0.name()};")
        self.setMinimumWidth(350)

        self._page_w, self._margin_l, self._margin_r, self._text_w = _calc_page_metrics()
        self._inline_highlight = False
        self._current_scene = None
        self._current_elements = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar con toggle evidenziazione inline
        toolbar = QWidget()
        toolbar.setStyleSheet(f"background-color: {theme.BG1.name()};")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(16, 6, 16, 6)
        tb_layout.addStretch()

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
        layout.addWidget(toolbar)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background-color: {theme.BG0.name()}; }}"
        )

        self._content = QWidget()
        self._content.setFixedWidth(self._page_w)
        self._content.setStyleSheet(f"background-color: {theme.BG1.name()};")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(self._margin_l, 20, self._margin_r, 20)
        self._content_layout.setSpacing(0)

        # Scene header (slug line)
        self._scene_header = QLabel("")
        self._scene_header.setWordWrap(True)
        self._scene_header.setStyleSheet(
            f"{_sp_css(16, bold=True)}"
            f" color: {theme.TEXT0.name()};"
            f" border-bottom: 1px solid {theme.qss_color(theme.BD1)};"
            f" padding-bottom: 8px; margin-bottom: 4px;"
        )
        self._content_layout.addWidget(self._scene_header)

        self._scene_subheader = QLabel("")
        self._scene_subheader.setStyleSheet(
            f"{_sp_css(13)}"
            f" color: {theme.TEXT2.name()}; padding-bottom: 12px;"
        )
        self._content_layout.addWidget(self._scene_subheader)

        # Contenitore blocchi screenplay (ricostruito ad ogni load_scene)
        self._blocks_container = QWidget()
        self._blocks_layout = QVBoxLayout(self._blocks_container)
        self._blocks_layout.setContentsMargins(0, 0, 0, 0)
        self._blocks_layout.setSpacing(0)
        self._content_layout.addWidget(self._blocks_container)

        # Sezione elementi rilevati
        self._elements_header = QLabel("ELEMENTI RILEVATI")
        self._elements_header.setFont(theme.font_ui(9, bold=True))
        self._elements_header.setStyleSheet(
            f"color: {theme.TEXT3.name()}; padding-top: 16px; padding-bottom: 4px;"
        )
        self._content_layout.addWidget(self._elements_header)

        self._elements_container = QVBoxLayout()
        self._elements_container.setSpacing(4)
        self._content_layout.addLayout(self._elements_container)

        self._content_layout.addStretch()
        self._scroll.setWidget(self._content)
        layout.addWidget(self._scroll)

        self._element_widgets = []
        self._block_widgets = []

        self._placeholder = QLabel("Seleziona una scena")
        self._placeholder.setFont(theme.font_ui(14))
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet(f"color: {theme.TEXT4.name()};")
        layout.addWidget(self._placeholder)
        self._scroll.setVisible(False)

    def _on_highlight_toggled(self, checked):
        self._inline_highlight = checked
        self.highlight_toggled.emit(checked)
        if self._current_scene and self._current_elements:
            self.load_scene(self._current_scene, self._current_elements)

    def _build_highlight_map(self, elements):
        mapping = []
        for el in elements:
            name = el.get("element_name", "").strip()
            cat = el.get("category", "")
            if name:
                mapping.append((name, cat))
        mapping.sort(key=lambda x: len(x[0]), reverse=True)
        return mapping

    def _highlight_text(self, text, highlight_map):
        if not highlight_map:
            return text

        import html as html_mod
        safe_text = html_mod.escape(text)

        for name, cat in highlight_map:
            color = theme.CATEGORY_COLORS.get(cat, "#888888")
            safe_name = html_mod.escape(name)
            pattern = re.compile(re.escape(safe_name), re.IGNORECASE)
            replacement = (
                f'<span style="text-decoration: underline; '
                f'text-decoration-color: {color}; '
                f'text-underline-offset: 3px; '
                f'color: {color}; font-weight: bold;">'
                f'\\g<0></span>'
            )
            safe_text = pattern.sub(replacement, safe_text)

        return safe_text

    def load_scene(self, scene, elements):
        self._placeholder.setVisible(False)
        self._scroll.setVisible(True)
        self._current_scene = scene
        self._current_elements = elements

        num = scene.get("scene_number", "")
        ie  = scene.get("int_ext", "")
        loc = scene.get("location", "")
        dn  = scene.get("day_night", "")

        self._scene_header.setText(f"{num}  {ie}. {loc}".upper())
        self._scene_subheader.setText(f"– {dn}")

        highlight_map = self._build_highlight_map(elements) if self._inline_highlight else None

        # ── Visibilità sezione elementi ───────────────────────────────────────
        self._elements_header.setVisible(not self._inline_highlight)

        # ── Ricostruisci blocchi screenplay ───────────────────────────────────
        for w in self._block_widgets:
            self._blocks_layout.removeWidget(w)
            w.deleteLater()
        self._block_widgets.clear()

        raw_blocks = scene.get("raw_blocks") or []

        if raw_blocks:
            prev_type = None
            for b in raw_blocks:
                btype = b.get("type", "action")
                btext = b.get("text", "")
                if not btext.strip():
                    continue
                w = self._make_block_widget(btype, btext, prev_type, highlight_map)
                self._blocks_layout.addWidget(w)
                self._block_widgets.append(w)
                prev_type = btype
        else:
            synopsis = scene.get("synopsis", "") or ""
            for line in synopsis.splitlines():
                if line.strip():
                    lbl = QLabel(line)
                    lbl.setWordWrap(True)
                    if highlight_map:
                        lbl.setTextFormat(Qt.TextFormat.RichText)
                        lbl.setText(self._highlight_text(line, highlight_map))
                    lbl.setStyleSheet(
                        f"{_sp_css()}"
                        f" color: {theme.TEXT1.name()}; padding: 2px 0;"
                    )
                    self._blocks_layout.addWidget(lbl)
                    self._block_widgets.append(lbl)

        # ── Elementi rilevati ─────────────────────────────────────────────────
        for w in self._element_widgets:
            self._elements_container.removeWidget(w)
            w.deleteLater()
        self._element_widgets.clear()

        if not self._inline_highlight:
            self._elements_header.setText(f"ELEMENTI RILEVATI ({len(elements)})")
            for el in elements:
                tag = self._make_element_tag(el)
                self._elements_container.addWidget(tag)
                self._element_widgets.append(tag)

        self._scroll.verticalScrollBar().setValue(0)

    def _indent_px(self, pct):
        return max(int(self._text_w * pct), 20)

    def _make_block_widget(self, btype, text, prev_type, highlight_map=None):
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        if btype == "action":
            top = 12 if prev_type is None else (6 if prev_type == "action" else 16)
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, top, 0, 0)
            layout.setSpacing(0)
            lbl = QLabel()
            lbl.setWordWrap(True)
            lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            if highlight_map:
                lbl.setTextFormat(Qt.TextFormat.RichText)
                lbl.setText(self._highlight_text(text, highlight_map))
            else:
                lbl.setText(text)
            lbl.setStyleSheet(
                f"{_sp_css()}"
                f" color: {theme.TEXT1.name()};"
            )
            layout.addWidget(lbl)

        elif btype == "character":
            layout = QVBoxLayout(container)
            l_px = self._indent_px(_PCT_CHARACTER_L)
            layout.setContentsMargins(l_px, 16, 0, 0)
            layout.setSpacing(0)
            lbl = QLabel(text.upper())  # character cue: mai evidenziato
            lbl.setStyleSheet(
                f"{_sp_css()}"
                f" color: {theme.TEXT0.name()};"
            )
            layout.addWidget(lbl)

        elif btype == "parenthetical":
            layout = QVBoxLayout(container)
            l_px = self._indent_px(_PCT_PAREN_L)
            r_px = self._indent_px(_PCT_PAREN_R)
            layout.setContentsMargins(l_px, 0, r_px, 0)
            layout.setSpacing(0)
            lbl = QLabel()
            lbl.setWordWrap(True)
            lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            if highlight_map:
                lbl.setTextFormat(Qt.TextFormat.RichText)
                lbl.setText(self._highlight_text(text, highlight_map))
            else:
                lbl.setText(text)
            lbl.setStyleSheet(
                f"{_sp_css()}"
                f" color: {theme.TEXT2.name()};"
            )
            layout.addWidget(lbl)

        elif btype == "dialogue":
            layout = QVBoxLayout(container)
            l_px = self._indent_px(_PCT_DIALOGUE_L)
            r_px = self._indent_px(_PCT_DIALOGUE_R)
            layout.setContentsMargins(l_px, 0, r_px, 0)
            layout.setSpacing(0)
            lbl = QLabel()
            lbl.setWordWrap(True)
            lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            if highlight_map:
                lbl.setTextFormat(Qt.TextFormat.RichText)
                lbl.setText(self._highlight_text(text, highlight_map))
            else:
                lbl.setText(text)
            lbl.setStyleSheet(
                f"{_sp_css()}"
                f" color: {theme.TEXT1.name()};"
            )
            layout.addWidget(lbl)

        elif btype == "transition":
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 16, 0, 4)
            layout.setSpacing(0)
            lbl = QLabel(text.upper())
            lbl.setWordWrap(True)
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            lbl.setStyleSheet(
                f"{_sp_css(bold=True)}"
                f" color: {theme.TEXT2.name()};"
            )
            layout.addWidget(lbl)

        else:
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            lbl = QLabel()
            lbl.setWordWrap(True)
            lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            if highlight_map:
                lbl.setTextFormat(Qt.TextFormat.RichText)
                lbl.setText(self._highlight_text(text, highlight_map))
            else:
                lbl.setText(text)
            lbl.setStyleSheet(
                f"{_sp_css()} color: {theme.TEXT1.name()};"
            )
            layout.addWidget(lbl)

        # Selezione testo + context menu per tagging rapido
        if btype in ("action", "dialogue", "parenthetical"):
            lbl.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            lbl.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            lbl.customContextMenuRequested.connect(
                lambda pos, l=lbl:
                    self._on_text_block_context(l.mapToGlobal(pos), l)
            )

        return container

    def _on_text_block_context(self, global_pos, lbl):
        selected = lbl.selectedText().strip() if lbl else ""

        menu = QMenu(self)
        # Azioni standard
        copy_action = menu.addAction("Copia")
        copy_action.setEnabled(bool(selected))
        menu.addSeparator()
        # Sottomenu "Categoria" per tagging rapido
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
        elif result in cat_actions and selected and self._current_scene:
            scene_id = self._current_scene["id"]
            category = cat_actions[result]
            self.tag_requested.emit(scene_id, selected, category)

    def _make_element_tag(self, el):
        cat  = el.get("category", "")
        name = el.get("element_name", "")
        c    = theme.category_color(cat)
        tag  = QFrame()
        tag.setStyleSheet(f"""
            QFrame {{
                background-color: {theme.qss_color(theme.category_bg(cat))};
                border: 1px solid {theme.qss_color(theme.category_border(cat))};
                border-radius: 4px;
            }}
            QLabel {{
                background: transparent;
                border: none;
                color: {c.name()};
            }}
        """)
        tl = QHBoxLayout(tag)
        tl.setContentsMargins(10, 4, 10, 4)
        tl.setSpacing(5)
        ico = QLabel()
        ico.setPixmap(theme.category_qicon(cat, 12).pixmap(12, 12))
        ico.setFixedSize(12, 12)
        tl.addWidget(ico)
        txt = QLabel(f"{name} - {cat}")
        txt.setFont(theme.font_ui(10, bold=True))
        tl.addWidget(txt)
        return tag

    def clear(self):
        self._placeholder.setVisible(True)
        self._scroll.setVisible(False)


# ──────────────────────────────────────────────────────────────────────────────
# Pannello elementi con filtri, aggiunta e cambio categoria
# ──────────────────────────────────────────────────────────────────────────────

# FIX 1 — Costanti filtro
_FILTER_ALL      = "Tutti"
_FILTER_AI_ONLY  = "Solo AI"
_FILTER_VERIFIED = "Verificati"


class ElementsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(280)
        self.setMaximumWidth(380)
        self.setStyleSheet(f"background-color: {theme.BG1.name()};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(16, 12, 16, 8)

        label = QLabel("ELEMENTI")
        label.setFont(theme.font_ui(9, bold=True))
        label.setStyleSheet(f"color: {theme.TEXT3.name()};")
        h_layout.addWidget(label)

        self._count_label = QLabel("0")
        self._count_label.setFont(theme.font_ui(11, bold=True))
        self._count_label.setStyleSheet(f"""
            color: {theme.TEXT0.name()};
            background-color: {theme.BG0.name()};
            border-radius: 10px;
            padding: 2px 8px;
        """)
        h_layout.addWidget(self._count_label)
        h_layout.addStretch()
        layout.addWidget(header)

        # FIX 1 — Filter row con logica reale
        filt = QWidget()
        f_layout = QHBoxLayout(filt)
        f_layout.setContentsMargins(16, 0, 16, 8)
        f_layout.setSpacing(4)

        self._filter_buttons: dict[str, QPushButton] = {}
        self._active_filter = _FILTER_ALL

        for label_text in [_FILTER_ALL, _FILTER_AI_ONLY, _FILTER_VERIFIED]:
            btn = QPushButton(label_text)
            btn.setFont(theme.font_ui(10))
            btn.setCheckable(True)
            btn.setStyleSheet(f"""
                QPushButton {{
                    color: {theme.TEXT3.name()};
                    background: transparent;
                    border: 1px solid {theme.qss_color(theme.BD1)};
                    border-radius: 4px;
                    padding: 3px 10px;
                }}
                QPushButton:checked {{
                    color: {theme.GOLD.name()};
                    background-color: {theme.qss_color(theme.GOLD_BG)};
                    border-color: {theme.qss_color(theme.GOLD_BD)};
                }}
            """)
            if label_text == _FILTER_ALL:
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, lbl=label_text: self._on_filter_clicked(lbl))
            f_layout.addWidget(btn)
            self._filter_buttons[label_text] = btn

        f_layout.addStretch()
        layout.addWidget(filt)

        # Scroll area for elements
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea { border: none; }")

        self._list_widget = QWidget()
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(0)
        self._list_layout.addStretch()
        self._scroll.setWidget(self._list_widget)
        layout.addWidget(self._scroll, 1)

        # FIX 4 — Add element button collegato a dialogo reale
        add_row = QWidget()
        a_layout = QHBoxLayout(add_row)
        a_layout.setContentsMargins(16, 8, 16, 12)
        self._add_btn = QPushButton("+ Aggiungi Elemento")
        self._add_btn.setFont(theme.font_ui(11))
        self._add_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._add_btn.setStyleSheet(f"""
            QPushButton {{
                color: {theme.GOLD.name()};
                background-color: {theme.qss_color(theme.GOLD_BG)};
                border: 1.5px solid {theme.qss_color(theme.GOLD_BD)};
                border-radius: 6px;
                padding: 7px 14px;
            }}
            QPushButton:hover {{
                background-color: {theme.qss_color(theme.GOLD_BD)};
            }}
        """)
        self._add_btn.clicked.connect(self._on_add_element)
        self._add_btn.setEnabled(False)  # abilitato solo quando c'è una scena attiva
        a_layout.addWidget(self._add_btn)
        layout.addWidget(add_row)

        self._category_widgets = []
        self._all_elements: list[dict] = []   # FIX 1 — cache per filtro
        self._db               = None
        self._feedback         = None
        self._current_scene_id = None
        self._parent_view      = None

    # ── FIX 1: logica filtro ─────────────────────────────────────────────────

    def _on_filter_clicked(self, label: str):
        """Cambia filtro attivo e aggiorna la lista."""
        self._active_filter = label
        for lbl, btn in self._filter_buttons.items():
            btn.setChecked(lbl == label)
        self._apply_filter()

    def _apply_filter(self):
        """Applica il filtro corrente agli elementi in cache."""
        if self._active_filter == _FILTER_AI_ONLY:
            visible = [e for e in self._all_elements
                       if e.get("ai_suggested") and not e.get("user_verified")]
        elif self._active_filter == _FILTER_VERIFIED:
            visible = [e for e in self._all_elements if e.get("user_verified")]
        else:
            visible = self._all_elements

        self._render_elements(visible)

    # ── Caricamento e rendering ───────────────────────────────────────────────

    def load_elements(self, elements: list[dict]):
        """Carica elementi e applica il filtro attivo."""
        self._all_elements = elements
        self._count_label.setText(str(len(elements)))
        self._add_btn.setEnabled(self._current_scene_id is not None)
        self._apply_filter()

    def _render_elements(self, elements: list[dict]):
        """Svuota e ridisegna la lista con gli elementi forniti."""
        for w in self._category_widgets:
            self._list_layout.removeWidget(w)
            w.deleteLater()
        self._category_widgets.clear()

        by_cat: dict[str, list] = {}
        for el in elements:
            cat = el.get("category", "Other")
            by_cat.setdefault(cat, []).append(el)

        for cat, items in sorted(by_cat.items()):
            cat_widget = self._make_category_section(cat, items)
            self._list_layout.insertWidget(
                self._list_layout.count() - 1, cat_widget
            )
            self._category_widgets.append(cat_widget)

    def _make_category_section(self, cat, items):
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Category header
        header = QWidget()
        c = theme.category_color(cat)
        header.setStyleSheet(f"""
            background-color: {theme.qss_color(theme.category_bg(cat))};
            border-left: 3px solid {c.name()};
        """)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(12, 6, 12, 6)

        ico_lbl = QLabel()
        ico_lbl.setPixmap(theme.category_qicon(cat, 14).pixmap(14, 14))
        ico_lbl.setFixedSize(18, 14)
        h_layout.addWidget(ico_lbl)
        name_label = QLabel(cat.upper())
        name_label.setFont(theme.font_ui(10, bold=True))
        name_label.setStyleSheet(f"color: {c.name()};")
        h_layout.addWidget(name_label)
        h_layout.addStretch()

        count_label = QLabel(str(len(items)))
        count_label.setFont(theme.font_ui(10, bold=True))
        bg_c = theme.category_bg(cat)
        count_label.setStyleSheet(f"""
            color: {c.name()};
            background-color: {theme.qss_color(bg_c)};
            border: 1px solid {theme.qss_color(theme.category_border(cat))};
            border-radius: 8px;
            padding: 1px 6px;
        """)
        h_layout.addWidget(count_label)

        layout.addWidget(header)

        # Element rows
        for el in items:
            row = self._make_element_row(el, cat)
            layout.addWidget(row)

        return section

    def _make_element_row(self, el, cat):
        row = QWidget()
        row.setProperty('element_id',   el.get('id', 0))
        row.setProperty('scene_id',     el.get('scene_id', 0))
        row.setProperty('category',     cat)
        row.setProperty('element_name', el.get('element_name', ''))
        row.setProperty('confidence',   el.get('ai_confidence'))
        row.setProperty('verified',     el.get('user_verified', 0))

        c        = theme.category_color(cat)
        verified = el.get('user_verified', 0)
        bg       = theme.qss_color(theme.category_bg(cat)) if verified else 'transparent'
        row.setStyleSheet(f'background-color: {bg};')

        layout = QHBoxLayout(row)
        layout.setContentsMargins(16, 4, 12, 4)
        layout.setSpacing(8)

        check_char = '\u25CF' if verified else '\u25CB'
        check = QLabel(check_char)
        check.setFont(theme.font_ui(10))
        check.setStyleSheet(f'color: {c.name()};')
        check.setFixedWidth(16)
        layout.addWidget(check)

        name = QLabel(el.get('element_name', ''))
        name.setFont(theme.font_ui(11))
        name.setStyleSheet(f'color: {theme.TEXT1.name()};')
        layout.addWidget(name, 1)

        conf = el.get('ai_confidence')
        if conf is not None:
            conf_c  = theme.confidence_color(conf)
            conf_bg = QColor(conf_c); conf_bg.setAlphaF(0.12)
            conf_bd = QColor(conf_c); conf_bd.setAlphaF(0.30)
            conf_lbl = QLabel(f'{int(conf * 100)}%')
            conf_lbl.setFont(theme.font_ui(10, bold=True))
            conf_lbl.setStyleSheet(
                f'color: {conf_c.name()};'
                f' background-color: {theme.qss_color(conf_bg)};'
                f' border: 1px solid {theme.qss_color(conf_bd)};'
                f' border-radius: 4px; padding: 1px 8px;'
            )
            conf_lbl.setToolTip(
                f"Confidenza AI: {int(conf * 100)}%\n"
                f"{'⚠ Verifica consigliata' if conf < 0.75 else '✓ Alta confidenza'}"
            )
            layout.addWidget(conf_lbl)

        # F5 — pulsante nota
        note_text = el.get("notes", "") or ""
        note_btn = QPushButton("✎" if note_text else "✏")
        note_btn.setFont(theme.font_ui(10))
        note_btn.setFixedSize(28, 28)
        note_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        note_btn.setToolTip(note_text if note_text else "Aggiungi nota")
        note_btn.setStyleSheet(f"""
            QPushButton {{
                color: {theme.TEXT3.name() if not note_text else theme.GOLD.name()};
                background: transparent; border: none;
            }}
            QPushButton:hover {{ color: {theme.GOLD.name()}; }}
        """)
        note_btn.clicked.connect(lambda _, r=row: self._edit_element_note(r))
        layout.addWidget(note_btn)

        row.mousePressEvent = lambda e, r=row: self._on_element_press(e, r)
        return row

    def _edit_element_note(self, row):
        from PyQt6.QtWidgets import QInputDialog
        el_id    = row.property("element_id")
        result = self._db.execute(
            "SELECT notes FROM scene_elements WHERE id = ?", (el_id,)
        ).fetchone()
        current = result[0] or "" if result else ""

        text, ok = QInputDialog.getMultiLineText(
            self, "Nota elemento", "Nota:", current
        )
        if not ok:
            return
        self._db.execute(
            "UPDATE scene_elements SET notes = ? WHERE id = ?",
            (text.strip() or None, el_id)
        )
        self._db.commit()
        if self._current_scene_id:
            QTimer.singleShot(0, lambda sid=self._current_scene_id:
                self._parent_view._on_scene_selected(sid))

    # ── Azioni elementi ───────────────────────────────────────────────────────

    def _on_element_press(self, event, row):
        if event.button() == Qt.MouseButton.LeftButton:
            self._toggle_verify(row)
        elif event.button() == Qt.MouseButton.RightButton:
            menu = QMenu(self)
            verified = row.property('verified')

            verify_action = QAction(
                'Rimuovi verifica' if verified else 'Verifica', self
            )
            # FIX 3 — Cambia categoria nel menu contestuale
            change_cat_action = QAction('Cambia categoria…', self)
            delete_action = QAction('Elimina elemento', self)

            verify_action.triggered.connect(lambda: self._toggle_verify(row))
            change_cat_action.triggered.connect(lambda: self._change_category(row))
            delete_action.triggered.connect(lambda: self._delete_element(row))

            menu.addAction(verify_action)
            menu.addAction(change_cat_action)
            menu.addSeparator()
            menu.addAction(delete_action)
            menu.exec(event.globalPosition().toPoint())

    def _toggle_verify(self, row):
        el_id    = row.property('element_id')
        scene_id = row.property('scene_id')
        verified = row.property('verified')
        new_val  = 0 if verified else 1
        self._db.execute(
            'UPDATE scene_elements SET user_verified = ? WHERE id = ?',
            (new_val, el_id),
        )
        self._db.commit()
        if self._feedback:
            self._feedback.track_verification(el_id, scene_id, bool(new_val))
        if self._current_scene_id:
            QTimer.singleShot(0, lambda sid=self._current_scene_id:
                self._parent_view._on_scene_selected(sid))

    # FIX 3 — Cambio categoria con record nel FeedbackLoop
    def _change_category(self, row):
        current_cat = row.property('category')
        el_id       = row.property('element_id')
        scene_id    = row.property('scene_id')
        confidence  = row.property('confidence')

        dlg = ChangeCategoryDialog(current_cat, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        new_cat = dlg.get_category()
        if new_cat == current_cat:
            return

        self._db.execute(
            'UPDATE scene_elements SET category = ?, user_modified = 1 '
            'WHERE id = ?',
            (new_cat, el_id),
        )
        self._db.commit()

        # Segnala la correzione al FeedbackLoop → contribuisce al retraining
        if self._feedback:
            self._feedback.record_category_change(
                element_id=el_id,
                scene_id=scene_id,
                before_cat=current_cat,
                after_cat=new_cat,
                confidence=confidence,
            )

        if self._current_scene_id:
            QTimer.singleShot(0, lambda sid=self._current_scene_id:
                self._parent_view._on_scene_selected(sid))

    def _delete_element(self, row):
        el_id    = row.property('element_id')
        scene_id = row.property('scene_id')
        row_data = self._db.execute(
            'SELECT element_name, category FROM scene_elements WHERE id = ?',
            (el_id,)
        ).fetchone()
        self._db.execute(
            'DELETE FROM scene_elements WHERE id = ?', (el_id,)
        )
        if row_data:
            self._db.execute(
                'INSERT INTO rejected_elements '
                '(element_name, category, scene_id) VALUES (?, ?, ?)',
                (row_data[0], row_data[1], scene_id)
            )
        self._db.commit()
        if self._feedback and row_data:
            self._feedback.record_deletion(
                el_id, scene_id, row_data[0], row_data[1])
        if self._current_scene_id:
            QTimer.singleShot(0, lambda sid=self._current_scene_id:
                self._parent_view._on_scene_selected(sid))

    # FIX 4 — Aggiunta elemento manuale con dialogo reale
    def _on_add_element(self):
        if not self._current_scene_id:
            return

        dlg = AddElementDialog(parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        data = dlg.get_data()
        self._db.execute(
            'INSERT OR IGNORE INTO scene_elements '
            '(scene_id, category, element_name, ai_suggested, user_verified) '
            'VALUES (?, ?, ?, 0, 1)',
            (self._current_scene_id, data["category"], data["element_name"]),
        )
        self._db.commit()

        if self._current_scene_id:
            self._parent_view._on_scene_selected(self._current_scene_id)

    def clear(self):
        self._all_elements = []
        for w in self._category_widgets:
            self._list_layout.removeWidget(w)
            w.deleteLater()
        self._category_widgets.clear()
        self._count_label.setText("0")
        self._add_btn.setEnabled(False)


# ──────────────────────────────────────────────────────────────────────────────
# Vista principale Breakdown
# ──────────────────────────────────────────────────────────────────────────────

class BreakdownView(QWidget):
    def __init__(self, container, parent=None):
        super().__init__(parent)
        self._container = container
        self._project_id = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        self._scene_list = SceneListColumn()
        self._scene_detail = SceneDetailColumn()
        self._elements_panel = ElementsPanel()

        splitter.addWidget(self._scene_list)
        splitter.addWidget(self._scene_detail)
        splitter.addWidget(self._elements_panel)
        splitter.setSizes([268, 450, 320])

        layout.addWidget(splitter)

        self._elements_panel._db          = container.database
        self._elements_panel._feedback    = container.feedback_loop
        self._elements_panel._parent_view = self

        self._scene_list.scene_selected.connect(self._on_scene_selected)
        self._scene_detail.tag_requested.connect(self._on_tag_from_text)

    def load_project(self, project_id):
        self._project_id = project_id
        db = self._container.database

        rows = db.execute(
            "SELECT id, scene_number, location, int_ext, day_night, "
            "page_start_whole, page_start_eighths, page_end_whole, page_end_eighths "
            "FROM scenes WHERE project_id = ? ORDER BY id", (project_id,)
        ).fetchall()

        # FIX 2 — Carica abbreviazioni cast per ogni scena
        cast_by_scene: dict[int, str] = {}
        cast_rows = db.execute(
            "SELECT se.scene_id, se.element_name "
            "FROM scene_elements se "
            "JOIN scenes s ON s.id = se.scene_id "
            "WHERE s.project_id = ? AND se.category = 'Cast' "
            "ORDER BY se.scene_id, se.element_name",
            (project_id,)
        ).fetchall()
        for cr in cast_rows:
            sid, name = cr[0], cr[1]
            # Abbrevia: "Mario Rossi" → "M. Rossi"
            parts = name.strip().split()
            abbrev = (f"{parts[0][0]}. {' '.join(parts[1:])}"
                      if len(parts) > 1 else name)
            if sid in cast_by_scene:
                cast_by_scene[sid] += f", {abbrev}"
            else:
                cast_by_scene[sid] = abbrev

        scenes = []
        for r in rows:
            sid = r[0]
            scenes.append({
                "id": sid,
                "scene_number": r[1],
                "location": r[2],
                "int_ext": r[3],
                "day_night": r[4],
                "page_start_whole": r[5],
                "page_start_eighths": r[6],
                "page_end_whole": r[7],
                "page_end_eighths": r[8],
                "cast_abbrev": cast_by_scene.get(sid, ""),  # FIX 2
            })

        el_count = db.execute(
            "SELECT COUNT(*) FROM scene_elements se "
            "JOIN scenes s ON se.scene_id = s.id WHERE s.project_id = ?",
            (project_id,)
        ).fetchone()[0]

        self._scene_list.load_scenes(scenes, el_count)
        self._scene_detail.clear()
        self._elements_panel.clear()

    def _on_scene_selected(self, scene_id):
        import json
        db = self._container.database
        row = db.execute(
            "SELECT id, scene_number, location, int_ext, day_night, synopsis, raw_blocks "
            "FROM scenes WHERE id = ?", (scene_id,)
        ).fetchone()
        if not row:
            return

        raw_blocks = []
        if row[6]:
            try:
                raw_blocks = json.loads(row[6])
            except Exception:
                raw_blocks = []

        if raw_blocks:
            fixed, n_changes = fix_raw_blocks(raw_blocks)
            if n_changes > 0:
                raw_blocks = fixed
                db.execute(
                    "UPDATE scenes SET raw_blocks = ? WHERE id = ?",
                    (json.dumps(fixed, ensure_ascii=False), row[0])
                )
                db.commit()

        scene = {
            "id": row[0], "scene_number": row[1], "location": row[2],
            "int_ext": row[3], "day_night": row[4], "synopsis": row[5],
            "raw_blocks": raw_blocks,
        }

        elements = db.execute(
            'SELECT id, category, element_name, ai_confidence,'
            ' user_verified, ai_suggested, notes'
            ' FROM scene_elements WHERE scene_id = ?'
            ' ORDER BY category, element_name',
            (scene_id,)
        ).fetchall()

        el_list = [
            {'id': e[0], 'category': e[1], 'element_name': e[2],
             'ai_confidence': e[3], 'user_verified': e[4],
             'ai_suggested': e[5], 'notes': e[6] or '', 'scene_id': scene_id}
            for e in elements
        ]

        self._elements_panel._current_scene_id = scene_id
        self._scene_detail.load_scene(scene, el_list)
        self._elements_panel.load_elements(el_list)

    def _on_tag_from_text(self, scene_id, element_name, category):
        db = self._container.database
        try:
            db.execute(
                "INSERT OR IGNORE INTO scene_elements"
                " (scene_id, category, element_name, ai_suggested, user_verified)"
                " VALUES (?, ?, ?, 0, 1)",
                (scene_id, category, element_name)
            )
            db.commit()
        except Exception:
            pass
        self._on_scene_selected(scene_id)

    def clear(self):
        self._project_id = None
        self._scene_list.load_scenes([])
        self._scene_detail.clear()
        self._elements_panel.clear()