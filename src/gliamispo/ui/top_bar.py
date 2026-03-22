from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QFrame,
    QVBoxLayout, QSizePolicy, QLineEdit, QSpacerItem, QMenu,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QCursor
from gliamispo.ui import theme


# Soglie di larghezza per layout responsive
WIDTH_COMPACT = 1000   # Sotto questa larghezza: solo icone nei tab
WIDTH_MINIMAL = 800    # Sotto questa larghezza: ricerca collassata


class TabButton(QPushButton):
    def __init__(self, label, parent=None):
        super().__init__(label, parent)
        self._label = label
        self._active = False
        self._compact = False
        self._icon_inactive = theme.tab_qicon(label, theme.TEXT2.name(), 18)
        self._icon_active   = theme.tab_qicon(label, theme.GOLD.name(), 18)
        self.setIconSize(QSize(18, 18))
        self.setFont(theme.font_ui(11))
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setCheckable(True)
        self.setToolTip(label)
        self._update_style()

    def set_active(self, active):
        self._active = active
        self.setChecked(active)
        self._update_style()

    def set_compact(self, compact: bool):
        """In modalita compatta mostra solo l'icona."""
        if self._compact == compact:
            return
        self._compact = compact
        if compact:
            self.setText("")
        else:
            self.setText(self._label)
        self._update_style()

    def _update_style(self):
        # Padding adattivo in base alla modalita
        h_pad = "6px" if self._compact else "10px"

        if self._active:
            self.setIcon(self._icon_active)
            self.setStyleSheet(f"""
                QPushButton {{
                    color: {theme.GOLD.name()};
                    background: transparent;
                    border: none;
                    border-bottom: 2px solid {theme.GOLD.name()};
                    padding: 8px {h_pad} 6px {h_pad};
                    font-weight: 600;
                }}
            """)
        else:
            self.setIcon(self._icon_inactive)
            self.setStyleSheet(f"""
                QPushButton {{
                    color: {theme.TEXT2.name()};
                    background: transparent;
                    border: none;
                    border-bottom: 2px solid transparent;
                    padding: 8px {h_pad} 6px {h_pad};
                }}
                QPushButton:hover {{
                    color: {theme.TEXT0.name()};
                }}
            """)


class TopBarView(QWidget):
    tab_changed       = Signal(int)
    export_pdf_requested  = Signal()
    export_xlsx_requested = Signal()
    settings_requested = Signal()
    search_triggered  = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(52)
        self.setStyleSheet(f"background-color: {theme.BG1.name()};")

        self._search_expanded = False
        self._compact_mode = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._bar = QWidget()
        self._layout = QHBoxLayout(self._bar)
        self._layout.setContentsMargins(12, 0, 12, 0)
        self._layout.setSpacing(4)

        # ── Project title area ──────────────────────────────────────────────
        self._title_label = QLabel("")
        self._title_label.setFont(theme.font_ui(13, bold=True))
        self._title_label.setStyleSheet(f"color: {theme.TEXT0.name()};")

        self._director_label = QLabel("")
        self._director_label.setFont(theme.font_ui(11))
        self._director_label.setStyleSheet(f"color: {theme.TEXT3.name()};")

        self._title_area = QWidget()
        self._title_area.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        title_layout = QVBoxLayout(self._title_area)
        title_layout.setContentsMargins(0, 6, 12, 6)
        title_layout.setSpacing(0)
        title_layout.addWidget(self._title_label)
        title_layout.addWidget(self._director_label)
        self._layout.addWidget(self._title_area)

        # ── Spacer flessibile sinistro ──────────────────────────────────────
        self._left_spacer = QSpacerItem(8, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._layout.addItem(self._left_spacer)

        # ── Tab buttons container ───────────────────────────────────────────
        self._tabs_container = QWidget()
        self._tabs_layout = QHBoxLayout(self._tabs_container)
        self._tabs_layout.setContentsMargins(0, 0, 0, 0)
        self._tabs_layout.setSpacing(2)

        self._tab_buttons = []
        for i, label in enumerate(theme.TABS):
            btn = TabButton(label)
            btn.clicked.connect(lambda checked, idx=i: self._on_tab_clicked(idx))
            self._tab_buttons.append(btn)
            self._tabs_layout.addWidget(btn)

        self._layout.addWidget(self._tabs_container)

        # ── Spacer flessibile destro ────────────────────────────────────────
        self._right_spacer = QSpacerItem(8, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._layout.addItem(self._right_spacer)

        # ── Pulsante ricerca (icona) ────────────────────────────────────────
        self._search_btn = QPushButton("\U0001F50D")
        self._search_btn.setFont(theme.font_ui(14))
        self._search_btn.setFixedSize(34, 34)
        self._search_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._search_btn.setToolTip("Cerca")
        self._search_btn.setStyleSheet(f"""
            QPushButton {{
                color: {theme.TEXT2.name()};
                background: transparent;
                border: none;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {theme.qss_color(theme.BD0)};
                color: {theme.TEXT0.name()};
            }}
        """)
        self._search_btn.clicked.connect(self._toggle_search)
        self._search_btn.setVisible(False)
        self._layout.addWidget(self._search_btn)

        # ── Campo di ricerca espandibile ────────────────────────────────────
        self._search_container = QWidget()
        search_layout = QHBoxLayout(self._search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(0)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Cerca scene, elementi...")
        self._search_edit.setFont(theme.font_ui(11))
        self._search_edit.setFixedWidth(180)
        self._search_edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: {theme.BG2.name()};
                color: {theme.TEXT0.name()};
                border: 1.5px solid {theme.qss_color(theme.BD1)};
                border-top-left-radius: 6px;
                border-bottom-left-radius: 6px;
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
                border-right: none;
                padding: 4px 10px;
                font-size: 11px;
            }}
            QLineEdit:focus {{
                border-color: {theme.GOLD.name()};
                background-color: {theme.BG0.name()};
            }}
        """)
        # Ricerca solo su Invio (non automatica)
        self._search_edit.returnPressed.connect(self._emit_search)
        self._search_edit.editingFinished.connect(self._on_search_editing_finished)
        search_layout.addWidget(self._search_edit)

        # Pulsante lente per avviare la ricerca
        self._search_go_btn = QPushButton("\U0001F50D")
        self._search_go_btn.setFont(theme.font_ui(12))
        self._search_go_btn.setFixedSize(32, 28)
        self._search_go_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._search_go_btn.setToolTip("Avvia ricerca")
        self._search_go_btn.setStyleSheet(f"""
            QPushButton {{
                color: {theme.TEXT2.name()};
                background-color: {theme.BG2.name()};
                border: 1.5px solid {theme.qss_color(theme.BD1)};
                border-top-left-radius: 0px;
                border-bottom-left-radius: 0px;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
                border-left: none;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {theme.qss_color(theme.BD0)};
                color: {theme.TEXT0.name()};
            }}
        """)
        self._search_go_btn.clicked.connect(self._emit_search)
        search_layout.addWidget(self._search_go_btn)

        self._search_container.setVisible(False)
        self._layout.addWidget(self._search_container)

        self._layout.addSpacing(4)

        # ── Pulsante Esporta con menu dropdown ──────────────────────────────
        self._export_btn = QPushButton("Esporta ▾")
        self._export_btn.setFont(theme.font_ui(11))
        self._export_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._export_btn.setStyleSheet(f"""
            QPushButton {{
                color: {theme.TEXT2.name()};
                background: transparent;
                border: 1.5px solid {theme.qss_color(theme.BD1)};
                border-radius: 6px;
                padding: 5px 12px;
            }}
            QPushButton:hover {{
                background-color: {theme.qss_color(theme.BD0)};
                color: {theme.TEXT0.name()};
            }}
            QPushButton::menu-indicator {{
                image: none;
            }}
        """)
        export_menu = QMenu(self)
        export_menu.setStyleSheet(f"""
            QMenu {{
                background-color: {theme.BG1.name()};
                border: 1px solid {theme.qss_color(theme.BD1)};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                color: {theme.TEXT0.name()};
                padding: 6px 16px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {theme.qss_color(theme.BD0)};
            }}
        """)
        export_menu.addAction("PDF (.pdf)", lambda: self.export_pdf_requested.emit())
        export_menu.addAction("Excel (.xlsx)", lambda: self.export_xlsx_requested.emit())
        self._export_btn.setMenu(export_menu)
        self._layout.addWidget(self._export_btn)

        self._layout.addSpacing(2)

        # ── Pulsante Impostazioni ───────────────────────────────────────────
        self._settings_btn = QPushButton("\u2699")
        self._settings_btn.setFont(theme.font_ui(16))
        self._settings_btn.setFixedSize(34, 34)
        self._settings_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._settings_btn.setToolTip("Impostazioni")
        self._settings_btn.setStyleSheet(f"""
            QPushButton {{
                color: {theme.TEXT3.name()};
                background: transparent;
                border: none;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {theme.qss_color(theme.BD0)};
                color: {theme.TEXT0.name()};
            }}
        """)
        self._settings_btn.clicked.connect(self.settings_requested)
        self._layout.addWidget(self._settings_btn)

        outer.addWidget(self._bar, 1)

        # ── Bottom divider ──────────────────────────────────────────────────
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {theme.qss_color(theme.BD1)};")
        outer.addWidget(divider)

        self._current_tab = 0
        self._has_project = False
        self._update_tabs()

    # ── Public API ──────────────────────────────────────────────────────────

    def set_project_info(self, title, director):
        self._title_label.setText(title or "")
        self._director_label.setText(f"Reg. {director}" if director else "")

    def set_visible_state(self, has_project: bool):
        self._has_project = has_project
        self._tabs_container.setVisible(has_project)
        self._search_btn.setVisible(has_project)
        if not has_project:
            self._search_container.setVisible(False)
            self._search_edit.clear()
            self._search_expanded = False
            self._export_btn.setVisible(False)
        self._adapt_to_width()

    def set_current_tab(self, idx: int):
        self._current_tab = idx
        self._update_tabs()

    def set_export_visible(self, visible: bool):
        """Mostra o nasconde il pulsante Esporta."""
        self._export_btn.setVisible(visible)

    # ── Resize Event per adattamento responsive ─────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._adapt_to_width()

    def _adapt_to_width(self):
        """Adatta il layout in base alla larghezza disponibile."""
        w = self.width()

        # Determina la modalita compatta
        compact = w < WIDTH_COMPACT

        if compact != self._compact_mode:
            self._compact_mode = compact
            for btn in self._tab_buttons:
                btn.set_compact(compact)

        # Gestione ricerca: su schermi piccoli usa solo il pulsante
        if w < WIDTH_MINIMAL and self._has_project:
            # Mostra solo il pulsante ricerca, nasconde il campo se non in uso
            if not self._search_expanded:
                self._search_container.setVisible(False)
                self._search_btn.setVisible(True)
        elif self._has_project:
            # Schermo grande: mostra sempre il campo di ricerca
            self._search_container.setVisible(True)
            self._search_btn.setVisible(False)
            self._search_expanded = False

    # ── Internal slots ──────────────────────────────────────────────────────

    def _on_tab_clicked(self, idx: int):
        self._current_tab = idx
        self._update_tabs()
        self.tab_changed.emit(idx)

    def _update_tabs(self):
        for i, btn in enumerate(self._tab_buttons):
            btn.set_active(i == self._current_tab)

    # ── Gestione ricerca espandibile ────────────────────────────────────────

    def _toggle_search(self):
        """Mostra/nasconde il campo di ricerca quando si clicca l'icona."""
        self._search_expanded = not self._search_expanded
        self._search_container.setVisible(self._search_expanded)
        if self._search_expanded:
            self._search_edit.setFocus()
        else:
            self._search_edit.clear()

    def _on_search_editing_finished(self):
        """Collassa la ricerca quando si perde il focus (solo su schermi piccoli)."""
        if self.width() < WIDTH_MINIMAL and not self._search_edit.text():
            self._search_expanded = False
            self._search_container.setVisible(False)
            self._search_btn.setVisible(True)

    def _emit_search(self):
        """Emette il segnale di ricerca quando l'utente preme Invio o clicca la lente."""
        text = self._search_edit.text().strip()
        if len(text) >= 2:
            self.search_triggered.emit(text)