from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QMenu, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QCursor
from gliamispo.ui import theme


class SidebarProjectRow(QFrame):
    clicked = pyqtSignal(int)
    edit_requested = pyqtSignal(int)
    delete_requested = pyqtSignal(int)

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
    project_selected = pyqtSignal(int)
    import_requested = pyqtSignal()
    new_project_requested = pyqtSignal()
    edit_project_requested = pyqtSignal(int)
    delete_project_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(248)
        self.setStyleSheet(f"background-color: {theme.SIDEBAR_BG.name()};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(20, 20, 20, 16)
        header_layout.setSpacing(2)

        app_title = QLabel("GLIAMISPO")
        app_title.setFont(theme.font_ui(15, bold=True))
        app_title.setStyleSheet(f"color: {theme.TEXT_INV.name()};")

        version = QLabel("Pre-Produzione v7")
        version.setFont(theme.font_ui(10))
        version.setStyleSheet(f"color: {theme.TEXT_INV2.name()};")

        header_layout.addWidget(app_title)
        header_layout.addWidget(version)
        layout.addWidget(header)

        # Divider
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background-color: {theme.qss_color(theme.SIDEBAR_BORDER)};")
        layout.addWidget(div)

        # Section label
        section_label = QLabel("PROGETTI")
        section_label.setFont(theme.font_ui(9, bold=True))
        section_label.setStyleSheet(f"""
            color: {theme.TEXT_INV2.name()};
            padding: 12px 20px 6px 20px;
        """)
        layout.addWidget(section_label)

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
        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 12, 16, 16)
        footer_layout.setSpacing(8)

        import_btn = QPushButton("Importa")
        import_btn.setFont(theme.font_ui(11))
        import_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        import_btn.setStyleSheet(f"""
            QPushButton {{
                color: {theme.TEXT_INV.name()};
                background-color: transparent;
                border: 1.5px solid {theme.qss_color(theme.SIDEBAR_BORDER)};
                border-radius: 6px;
                padding: 7px 14px;
            }}
            QPushButton:hover {{
                background-color: {theme.SIDEBAR_HOVER.name()};
            }}
        """)
        import_btn.clicked.connect(self.import_requested)

        new_btn = QPushButton("+ Nuovo")
        new_btn.setFont(theme.font_ui(11, bold=True))
        new_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        new_btn.setStyleSheet(f"""
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
        new_btn.clicked.connect(self.new_project_requested)

        footer_layout.addWidget(import_btn, 1)
        footer_layout.addWidget(new_btn, 1)
        layout.addWidget(footer)

        self._rows = []
        self._selected_id = None

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
