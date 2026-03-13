from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGridLayout, QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QFont
from gliamispo.ui import theme


class RecentProjectCard(QFrame):
    clicked = pyqtSignal(int)

    def __init__(self, project_id, title, director, parent=None):
        super().__init__(parent)
        self._project_id = project_id
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setStyleSheet(f"""
            RecentProjectCard {{
                background-color: {theme.BG0.name()};
                border: 1px solid {theme.qss_color(theme.BD1)};
                border-radius: 8px;
            }}
            RecentProjectCard:hover {{
                border-color: {theme.GOLD.name()};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        icon_label = QLabel("\U0001F3AC")
        icon_label.setFont(QFont("", 14))
        icon_label.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(icon_label)

        title_label = QLabel(title or "Senza titolo")
        title_label.setFont(theme.font_ui(12, bold=True))
        title_label.setStyleSheet(f"color: {theme.TEXT0.name()}; background: transparent; border: none;")
        layout.addWidget(title_label)

        if director:
            dir_label = QLabel(f"Reg. {director}")
            dir_label.setFont(theme.font_ui(10))
            dir_label.setStyleSheet(f"color: {theme.TEXT3.name()}; background: transparent; border: none;")
            layout.addWidget(dir_label)

    def mousePressEvent(self, event):
        self.clicked.emit(self._project_id)


class WelcomeView(QWidget):
    import_requested = pyqtSignal()
    new_project_requested = pyqtSignal()
    project_selected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {theme.BG1.name()};")

        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        center = QWidget()
        center.setMaximumWidth(600)
        layout = QVBoxLayout(center)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(8)

        # Logo
        logo = QLabel("\U0001F3AC")
        logo.setFont(QFont("", 48))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet(f"""
            background-color: {theme.SIDEBAR_BG.name()};
            border-radius: 20px;
            padding: 20px;
            color: {theme.GOLD.name()};
        """)
        logo.setFixedSize(100, 100)
        logo_container = QHBoxLayout()
        logo_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_container.addWidget(logo)
        layout.addLayout(logo_container)

        layout.addSpacing(16)

        # Title
        title = QLabel("GLIAMISPO")
        title.setFont(theme.font_ui(28, bold=True))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {theme.TEXT0.name()};")
        layout.addWidget(title)

        subtitle = QLabel("Software di pre-produzione cinematografica")
        subtitle.setFont(theme.font_ui(13))
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(f"color: {theme.TEXT3.name()};")
        layout.addWidget(subtitle)

        version = QLabel("v7 \u00b7 Build 2026")
        version.setFont(theme.font_ui(11))
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setStyleSheet(f"color: {theme.TEXT4.name()};")
        layout.addWidget(version)

        layout.addSpacing(24)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_row.setSpacing(12)

        import_btn = QPushButton("Importa Script")
        import_btn.setFont(theme.font_ui(12))
        import_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        import_btn.setStyleSheet(f"""
            QPushButton {{
                color: {theme.TEXT2.name()};
                background: transparent;
                border: 1.5px solid {theme.qss_color(theme.BD1)};
                border-radius: 6px;
                padding: 7px 16px;
            }}
            QPushButton:hover {{
                background-color: {theme.qss_color(theme.BD0)};
            }}
        """)
        import_btn.clicked.connect(self.import_requested)

        new_btn = QPushButton("+ Nuovo Progetto")
        new_btn.setFont(theme.font_ui(12, bold=True))
        new_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        new_btn.setStyleSheet(f"""
            QPushButton {{
                color: {theme.GOLD.name()};
                background-color: {theme.qss_color(theme.GOLD_BG)};
                border: 1.5px solid {theme.qss_color(theme.GOLD_BD)};
                border-radius: 6px;
                padding: 7px 16px;
            }}
            QPushButton:hover {{
                background-color: {theme.qss_color(theme.GOLD_BD)};
            }}
        """)
        new_btn.clicked.connect(self.new_project_requested)

        btn_row.addWidget(import_btn)
        btn_row.addWidget(new_btn)
        layout.addLayout(btn_row)

        layout.addSpacing(32)

        # Recent projects section
        self._recent_header = QLabel("PROGETTI RECENTI")
        self._recent_header.setFont(theme.font_ui(9, bold=True))
        self._recent_header.setStyleSheet(f"color: {theme.TEXT3.name()};")
        self._recent_header.setVisible(False)
        layout.addWidget(self._recent_header)

        layout.addSpacing(8)

        self._grid = QGridLayout()
        self._grid.setSpacing(12)
        layout.addLayout(self._grid)

        outer.addWidget(center)
        self._cards = []

    def load_recent(self, projects):
        for card in self._cards:
            self._grid.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

        self._recent_header.setVisible(bool(projects))

        for i, p in enumerate(projects[:4]):
            card = RecentProjectCard(p["id"], p["title"], p.get("director"))
            card.clicked.connect(self.project_selected)
            self._grid.addWidget(card, i // 2, i % 2)
            self._cards.append(card)
