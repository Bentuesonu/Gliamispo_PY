from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QFrame,
    QVBoxLayout, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QCursor
from gliamispo.ui import theme


class TabButton(QPushButton):
    def __init__(self, label, parent=None):
        super().__init__(label, parent)
        self._active = False
        self._icon_inactive = theme.tab_qicon(label, theme.TEXT2.name(), 16)
        self._icon_active   = theme.tab_qicon(label, theme.GOLD.name(), 16)
        self.setIconSize(QSize(16, 16))
        self.setFont(theme.font_ui(12))
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setCheckable(True)
        self._update_style()

    def set_active(self, active):
        self._active = active
        self.setChecked(active)
        self._update_style()

    def _update_style(self):
        if self._active:
            self.setIcon(self._icon_active)
            self.setStyleSheet(f"""
                QPushButton {{
                    color: {theme.GOLD.name()};
                    background: transparent;
                    border: none;
                    border-bottom: 2px solid {theme.GOLD.name()};
                    padding: 8px 12px 6px 12px;
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
                    padding: 8px 12px 6px 12px;
                }}
                QPushButton:hover {{
                    color: {theme.TEXT0.name()};
                }}
            """)


class TopBarView(QWidget):
    tab_changed = pyqtSignal(int)
    export_requested = pyqtSignal()
    settings_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(52)
        self.setStyleSheet(f"background-color: {theme.BG1.name()};")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(0)

        # Project title area
        self._title_label = QLabel("")
        self._title_label.setFont(theme.font_ui(14, bold=True))
        self._title_label.setStyleSheet(f"color: {theme.TEXT0.name()};")

        self._director_label = QLabel("")
        self._director_label.setFont(theme.font_ui(12))
        self._director_label.setStyleSheet(f"color: {theme.TEXT3.name()};")

        title_area = QWidget()
        title_layout = QVBoxLayout(title_area)
        title_layout.setContentsMargins(0, 6, 20, 6)
        title_layout.setSpacing(0)
        title_layout.addWidget(self._title_label)
        title_layout.addWidget(self._director_label)
        layout.addWidget(title_area)

        layout.addStretch()

        # Tabs
        self._tab_buttons = []
        for i, label in enumerate(theme.TABS):
            btn = TabButton(label)
            btn.clicked.connect(lambda checked, idx=i: self._on_tab_clicked(idx))
            self._tab_buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        # Right buttons
        export_btn = QPushButton("Esporta")
        export_btn.setFont(theme.font_ui(11))
        export_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        export_btn.setStyleSheet(f"""
            QPushButton {{
                color: {theme.TEXT2.name()};
                background: transparent;
                border: 1.5px solid {theme.qss_color(theme.BD1)};
                border-radius: 6px;
                padding: 5px 14px;
            }}
            QPushButton:hover {{
                background-color: {theme.qss_color(theme.BD0)};
            }}
        """)
        export_btn.clicked.connect(self.export_requested)
        layout.addWidget(export_btn)

        settings_btn = QPushButton("\u2699")
        settings_btn.setFont(theme.font_ui(16))
        settings_btn.setFixedSize(34, 34)
        settings_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        settings_btn.setStyleSheet(f"""
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
        settings_btn.clicked.connect(self.settings_requested)
        layout.addWidget(settings_btn)

        outer.addWidget(bar, 1)

        # Bottom divider
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {theme.qss_color(theme.BD1)};")
        outer.addWidget(divider)

        self._current_tab = 0
        self._update_tabs()

    def set_project_info(self, title, director):
        self._title_label.setText(title or "")
        self._director_label.setText(f"Reg. {director}" if director else "")

    def _on_tab_clicked(self, idx):
        self._current_tab = idx
        self._update_tabs()
        self.tab_changed.emit(idx)

    def _update_tabs(self):
        for i, btn in enumerate(self._tab_buttons):
            btn.set_active(i == self._current_tab)

    def set_current_tab(self, idx):
        self._current_tab = idx
        self._update_tabs()

    def set_visible_state(self, has_project):
        for btn in self._tab_buttons:
            btn.setVisible(has_project)
