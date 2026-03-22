from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QMenu, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QSize, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QCursor
from gliamispo.ui import theme


# Dimensioni sidebar
SIDEBAR_WIDTH_EXPANDED = 248
SIDEBAR_WIDTH_COLLAPSED = 56


class SidebarProjectRow(QFrame):
    clicked = Signal(int)
    edit_requested = Signal(int)
    delete_requested = Signal(int)

    def __init__(self, project_id, title, director, parent=None):
        super().__init__(parent)
        self._project_id = project_id
        self._selected = False
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedHeight(60)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(2)

        self._title_label = QLabel(title or "Senza titolo")
        self._title_label.setFont(theme.font_ui(12, bold=True))
        self._title_label.setStyleSheet(f"color: {theme.TEXT_INV.name()};")

        self._director_label = QLabel(f"Reg. {director}" if director else "")
        self._director_label.setFont(theme.font_ui(10))
        self._director_label.setStyleSheet(f"color: {theme.TEXT_INV2.name()};")

        layout.addWidget(self._title_label)
        layout.addWidget(self._director_label)

        self._update_style()
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def set_selected(self, selected):
        self._selected = selected
        self._update_style()

    def _update_style(self):
        if self._selected:
            self.setStyleSheet(f"""
                SidebarProjectRow {{
                    background-color: {theme.SIDEBAR_HOVER.name()};
                    border-left: 4px solid {theme.GOLD.name()};
                    border-radius: 0px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                SidebarProjectRow {{
                    background-color: transparent;
                    border-left: 4px solid transparent;
                    border-radius: 0px;
                }}
                SidebarProjectRow:hover {{
                    background-color: {theme.SIDEBAR_HOVER.name()};
                }}
            """)

    def mousePressEvent(self, event):
        self.clicked.emit(self._project_id)

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {theme.SIDEBAR_HOVER.name()};
                color: {theme.TEXT_INV.name()};
                border: 1px solid {theme.qss_color(theme.BD2)};
                padding: 4px;
            }}
            QMenu::item:selected {{
                background-color: {theme.GOLD.name()};
            }}
        """)
        edit_action = menu.addAction("Modifica")
        delete_action = menu.addAction("Elimina")
        action = menu.exec(self.mapToGlobal(pos))
        if action == edit_action:
            self.edit_requested.emit(self._project_id)
        elif action == delete_action:
            self.delete_requested.emit(self._project_id)


class SidebarView(QWidget):
    project_selected = Signal(int)
    import_requested = Signal()
    new_project_requested = Signal()
    edit_project_requested = Signal(int)
    delete_project_requested = Signal(int)
    collapse_toggled = Signal(bool)  # True = collapsed

    def __init__(self, parent=None):
        super().__init__(parent)
        self._collapsed = False
        self.setMinimumWidth(SIDEBAR_WIDTH_COLLAPSED)
        self.setMaximumWidth(SIDEBAR_WIDTH_EXPANDED)
        self.setFixedWidth(SIDEBAR_WIDTH_EXPANDED)
        self.setStyleSheet(f"background-color: {theme.SIDEBAR_BG.name()};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header con toggle
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 12, 12, 12)
        header_layout.setSpacing(8)

        # Pulsante toggle (hamburger/close)
        self._toggle_btn = QPushButton("\u2630")  # ☰
        self._toggle_btn.setFont(theme.font_ui(16))
        self._toggle_btn.setFixedSize(32, 32)
        self._toggle_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._toggle_btn.setToolTip("Comprimi/Espandi sidebar")
        self._toggle_btn.setStyleSheet(f"""
            QPushButton {{
                color: {theme.TEXT_INV.name()};
                background: transparent;
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {theme.SIDEBAR_HOVER.name()};
            }}
        """)
        self._toggle_btn.clicked.connect(self._toggle_collapse)
        header_layout.addWidget(self._toggle_btn)

        # Area titolo
        self._header_text = QWidget()
        header_text_layout = QVBoxLayout(self._header_text)
        header_text_layout.setContentsMargins(0, 0, 0, 0)
        header_text_layout.setSpacing(0)

        self._app_title = QLabel("GLIAMISPO")
        self._app_title.setFont(theme.font_ui(14, bold=True))
        self._app_title.setStyleSheet(f"color: {theme.TEXT_INV.name()};")

        self._version = QLabel("Pre-Produzione v7")
        self._version.setFont(theme.font_ui(9))
        self._version.setStyleSheet(f"color: {theme.TEXT_INV2.name()};")

        header_text_layout.addWidget(self._app_title)
        header_text_layout.addWidget(self._version)
        header_layout.addWidget(self._header_text, 1)

        layout.addWidget(header)

        # Divider
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background-color: {theme.qss_color(theme.SIDEBAR_BORDER)};")
        layout.addWidget(div)

        # Section label
        self._section_label = QLabel("PROGETTI")
        self._section_label.setFont(theme.font_ui(9, bold=True))
        self._section_label.setStyleSheet(f"""
            color: {theme.TEXT_INV2.name()};
            padding: 12px 16px 6px 16px;
        """)
        layout.addWidget(self._section_label)

        # Project list scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._list_widget = QWidget()
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(0)
        self._list_layout.addStretch()
        self._scroll.setWidget(self._list_widget)
        layout.addWidget(self._scroll, 1)

        # Footer divider
        div2 = QFrame()
        div2.setFixedHeight(1)
        div2.setStyleSheet(f"background-color: {theme.qss_color(theme.SIDEBAR_BORDER)};")
        layout.addWidget(div2)

        # Footer buttons
        self._footer = QWidget()
        footer_layout = QHBoxLayout(self._footer)
        footer_layout.setContentsMargins(12, 10, 12, 12)
        footer_layout.setSpacing(6)

        self._import_btn = QPushButton("Importa")
        self._import_btn.setFont(theme.font_ui(10))
        self._import_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._import_btn.setStyleSheet(f"""
            QPushButton {{
                color: {theme.TEXT_INV.name()};
                background-color: transparent;
                border: 1.5px solid {theme.qss_color(theme.SIDEBAR_BORDER)};
                border-radius: 6px;
                padding: 6px 10px;
            }}
            QPushButton:hover {{
                background-color: {theme.SIDEBAR_HOVER.name()};
            }}
        """)
        self._import_btn.clicked.connect(self.import_requested)

        self._new_btn = QPushButton("+ Nuovo")
        self._new_btn.setFont(theme.font_ui(10, bold=True))
        self._new_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._new_btn.setStyleSheet(f"""
            QPushButton {{
                color: {theme.GOLD.name()};
                background-color: {theme.qss_color(theme.GOLD_BG)};
                border: 1.5px solid {theme.qss_color(theme.GOLD_BD)};
                border-radius: 6px;
                padding: 6px 10px;
            }}
            QPushButton:hover {{
                background-color: {theme.qss_color(theme.GOLD_BD)};
            }}
        """)
        self._new_btn.clicked.connect(self.new_project_requested)

        # Pulsanti compatti per modalita collapsed
        self._import_btn_compact = QPushButton("\U0001F4C2")  # 📂
        self._import_btn_compact.setFont(theme.font_ui(14))
        self._import_btn_compact.setFixedSize(36, 36)
        self._import_btn_compact.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._import_btn_compact.setToolTip("Importa")
        self._import_btn_compact.setVisible(False)
        self._import_btn_compact.setStyleSheet(f"""
            QPushButton {{
                color: {theme.TEXT_INV.name()};
                background: transparent;
                border: none;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {theme.SIDEBAR_HOVER.name()};
            }}
        """)
        self._import_btn_compact.clicked.connect(self.import_requested)

        self._new_btn_compact = QPushButton("+")
        self._new_btn_compact.setFont(theme.font_ui(18, bold=True))
        self._new_btn_compact.setFixedSize(36, 36)
        self._new_btn_compact.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._new_btn_compact.setToolTip("Nuovo progetto")
        self._new_btn_compact.setVisible(False)
        self._new_btn_compact.setStyleSheet(f"""
            QPushButton {{
                color: {theme.GOLD.name()};
                background-color: {theme.qss_color(theme.GOLD_BG)};
                border: 1.5px solid {theme.qss_color(theme.GOLD_BD)};
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {theme.qss_color(theme.GOLD_BD)};
            }}
        """)
        self._new_btn_compact.clicked.connect(self.new_project_requested)

        footer_layout.addWidget(self._import_btn, 1)
        footer_layout.addWidget(self._new_btn, 1)
        footer_layout.addWidget(self._import_btn_compact)
        footer_layout.addWidget(self._new_btn_compact)
        layout.addWidget(self._footer)

        self._rows = []
        self._selected_id = None

    def _toggle_collapse(self):
        """Alterna tra modalita espansa e collassata."""
        self._collapsed = not self._collapsed
        target_width = SIDEBAR_WIDTH_COLLAPSED if self._collapsed else SIDEBAR_WIDTH_EXPANDED

        # Anima il cambio di larghezza
        self._anim = QPropertyAnimation(self, b"maximumWidth")
        self._anim.setDuration(150)
        self._anim.setStartValue(self.width())
        self._anim.setEndValue(target_width)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.finished.connect(self._on_collapse_finished)
        self._anim.start()

        # Aggiorna la visibilita degli elementi
        self._header_text.setVisible(not self._collapsed)
        self._section_label.setVisible(not self._collapsed)
        self._scroll.setVisible(not self._collapsed)

        # Toggle pulsanti footer
        self._import_btn.setVisible(not self._collapsed)
        self._new_btn.setVisible(not self._collapsed)
        self._import_btn_compact.setVisible(self._collapsed)
        self._new_btn_compact.setVisible(self._collapsed)

        # Cambia icona toggle
        self._toggle_btn.setText("\u2630" if self._collapsed else "\u2630")

        self.collapse_toggled.emit(self._collapsed)

    def _on_collapse_finished(self):
        """Chiamato quando l'animazione e terminata."""
        target_width = SIDEBAR_WIDTH_COLLAPSED if self._collapsed else SIDEBAR_WIDTH_EXPANDED
        self.setFixedWidth(target_width)

    def is_collapsed(self) -> bool:
        return self._collapsed

    def set_collapsed(self, collapsed: bool):
        """Imposta lo stato collapsed senza animazione."""
        if self._collapsed == collapsed:
            return
        self._collapsed = collapsed
        target_width = SIDEBAR_WIDTH_COLLAPSED if collapsed else SIDEBAR_WIDTH_EXPANDED
        self.setFixedWidth(target_width)
        self._header_text.setVisible(not collapsed)
        self._section_label.setVisible(not collapsed)
        self._scroll.setVisible(not collapsed)
        self._import_btn.setVisible(not collapsed)
        self._new_btn.setVisible(not collapsed)
        self._import_btn_compact.setVisible(collapsed)
        self._new_btn_compact.setVisible(collapsed)

    def load_projects(self, projects):
        for row in self._rows:
            self._list_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()

        for p in projects:
            row = SidebarProjectRow(p["id"], p["title"], p.get("director"))
            row.clicked.connect(self._on_row_clicked)
            row.edit_requested.connect(self.edit_project_requested)
            row.delete_requested.connect(self.delete_project_requested)
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)
            self._rows.append(row)

    def _on_row_clicked(self, project_id):
        self._selected_id = project_id
        for row in self._rows:
            row.set_selected(row._project_id == project_id)
        self.project_selected.emit(project_id)

    def select_project(self, project_id):
        if self._selected_id == project_id:
            return
        self._selected_id = project_id
        for row in self._rows:
            row.set_selected(row._project_id == project_id)
