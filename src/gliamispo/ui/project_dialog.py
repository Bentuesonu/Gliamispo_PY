from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from gliamispo.ui import theme


class ProjectDialog(QDialog):
    def __init__(self, parent=None, project=None):
        super().__init__(parent)
        self.setWindowTitle("Nuovo Progetto" if project is None else "Modifica Progetto")
        self.setMinimumWidth(440)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {theme.BG1.name()};
            }}
            QLabel {{
                color: {theme.TEXT1.name()};
                font-size: 12px;
            }}
            QLineEdit {{
                background-color: {theme.BG0.name()};
                color: {theme.TEXT0.name()};
                border: 1px solid {theme.qss_color(theme.BD1)};
                border-radius: 4px;
                padding: 8px 10px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {theme.GOLD.name()};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Title
        header = QLabel("Nuovo Progetto" if project is None else "Modifica Progetto")
        header.setFont(theme.font_ui(16, bold=True))
        header.setStyleSheet(f"color: {theme.TEXT0.name()};")
        layout.addWidget(header)

        # Form
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("Titolo del progetto")
        form.addRow("Titolo *", self._title_edit)

        self._director_edit = QLineEdit()
        self._director_edit.setPlaceholderText("Nome del regista")
        form.addRow("Regista", self._director_edit)

        self._production_company_edit = QLineEdit()
        self._production_company_edit.setPlaceholderText("Casa di produzione")
        form.addRow("Produzione", self._production_company_edit)

        self._language_edit = QLineEdit()
        self._language_edit.setPlaceholderText("es. Italiano")
        form.addRow("Lingua", self._language_edit)

        self._currency_edit = QLineEdit()
        self._currency_edit.setPlaceholderText("es. EUR")
        form.addRow("Valuta", self._currency_edit)

        if project:
            self._title_edit.setText(project.title or "")
            self._director_edit.setText(project.director or "")
            self._production_company_edit.setText(project.production_company or "")
            self._language_edit.setText(project.language or "")
            self._currency_edit.setText(project.currency or "")

        layout.addLayout(form)
        layout.addSpacing(8)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Annulla")
        cancel_btn.setFont(theme.font_ui(11))
        cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        cancel_btn.setStyleSheet(f"""
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
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        ok_btn = QPushButton("Crea" if project is None else "Salva")
        ok_btn.setFont(theme.font_ui(11, bold=True))
        ok_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        ok_btn.setStyleSheet(f"""
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
        ok_btn.clicked.connect(self._on_accept)
        btn_row.addWidget(ok_btn)

        layout.addLayout(btn_row)

    def _on_accept(self):
        if not self._title_edit.text().strip():
            return
        self.accept()

    def get_data(self):
        return {
            "title": self._title_edit.text().strip(),
            "director": self._director_edit.text().strip() or None,
            "production_company": self._production_company_edit.text().strip() or None,
            "language": self._language_edit.text().strip() or None,
            "currency": self._currency_edit.text().strip() or None,
        }
