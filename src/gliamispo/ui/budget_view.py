from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSplitter, QScrollArea, QFrame, QTableWidget, QTableWidgetItem,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor
from gliamispo.ui import theme


class AccountListPanel(QWidget):
    account_selected = pyqtSignal(int)
    account_created = pyqtSignal(str, str)   # code, name

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(280)
        self.setMaximumWidth(380)
        self.setStyleSheet(f"background-color: {theme.BG2.name()};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(16, 12, 16, 8)

        label = QLabel("CONTI")
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

        add_btn = QPushButton("+ Conto")
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
        add_btn.clicked.connect(self._on_add_account)
        h_layout.addWidget(add_btn)
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

        # Total
        total_bar = QWidget()
        total_bar.setStyleSheet(f"background-color: {theme.BG3.name()};")
        t_layout = QHBoxLayout(total_bar)
        t_layout.setContentsMargins(16, 10, 16, 10)

        total_label = QLabel("TOTALE GEN.")
        total_label.setFont(theme.font_ui(10, bold=True))
        total_label.setStyleSheet(f"color: {theme.TEXT2.name()};")
        t_layout.addWidget(total_label)

        t_layout.addStretch()

        self._total_value = QLabel("\u20ac 0")
        self._total_value.setFont(theme.font_ui(14, bold=True))
        self._total_value.setStyleSheet(f"color: {theme.TEXT0.name()};")
        t_layout.addWidget(self._total_value)

        layout.addWidget(total_bar)

        self._account_rows = []
        self._selected_id = None

    def _on_add_account(self):
        from PyQt6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle('Nuovo Conto')
        form = QFormLayout(dlg)
        code_edit = QLineEdit()
        name_edit = QLineEdit()
        form.addRow('Codice:', code_edit)
        form.addRow('Nome:', name_edit)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)
        if dlg.exec() and name_edit.text().strip():
            self.account_created.emit(
                code_edit.text().strip(), name_edit.text().strip()
            )

    def load_accounts(self, accounts):
        for w in self._account_rows:
            self._list_layout.removeWidget(w)
            w.deleteLater()
        self._account_rows.clear()

        self._count_label.setText(str(len(accounts)))
        total = 0

        for acc in accounts:
            row = self._make_account_row(acc)
            self._list_layout.insertWidget(
                self._list_layout.count() - 1, row
            )
            self._account_rows.append(row)
            total += acc.get("subtotal", 0) or 0

        self._total_value.setText(f"\u20ac {total:,.0f}")

    def _make_account_row(self, acc):
        row = QFrame()
        row.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        acc_id = acc.get("id", 0)
        row.setStyleSheet(f"""
            QFrame {{
                background: transparent;
                padding: 0;
            }}
            QFrame:hover {{
                background-color: {theme.qss_color(theme.BD0)};
            }}
        """)

        layout = QHBoxLayout(row)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(8)

        code = acc.get("code", "")
        name = acc.get("name", "")

        code_label = QLabel(code)
        code_label.setFont(theme.font_mono(10))
        code_label.setStyleSheet(f"color: {theme.TEXT3.name()};")
        code_label.setFixedWidth(50)
        layout.addWidget(code_label)

        name_label = QLabel(name)
        name_label.setFont(theme.font_ui(11))
        name_label.setStyleSheet(f"color: {theme.TEXT1.name()};")
        layout.addWidget(name_label, 1)

        sub = acc.get("subtotal", 0) or 0
        sub_label = QLabel(f"\u20ac {sub:,.0f}")
        sub_label.setFont(theme.font_ui(11, bold=True))
        sub_label.setStyleSheet(f"color: {theme.TEXT0.name()};")
        layout.addWidget(sub_label)

        row.mousePressEvent = lambda e, aid=acc_id: self._on_account_clicked(aid)
        return row

    def _on_account_clicked(self, acc_id):
        self._selected_id = acc_id
        self.account_selected.emit(acc_id)


class AccountDetailPanel(QWidget):
    item_created = pyqtSignal(int, str, float)  # account_id, description, cost

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_account_id = None
        self.setMinimumWidth(400)
        self.setStyleSheet(f"background-color: {theme.BG1.name()};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        self._header = QWidget()
        h_layout = QHBoxLayout(self._header)
        h_layout.setContentsMargins(24, 16, 24, 12)

        self._acc_name = QLabel("")
        self._acc_name.setFont(theme.font_ui(14, bold=True))
        self._acc_name.setStyleSheet(f"color: {theme.TEXT0.name()};")
        h_layout.addWidget(self._acc_name)

        h_layout.addStretch()

        self._acc_total = QLabel("")
        self._acc_total.setFont(theme.font_ui(14, bold=True))
        self._acc_total.setStyleSheet(f"color: {theme.TEXT0.name()};")
        h_layout.addWidget(self._acc_total)

        layout.addWidget(self._header)

        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background-color: {theme.qss_color(theme.BD1)};")
        layout.addWidget(div)

        # Table
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Descrizione", "Tipo", "Costo", "Fringes %"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {theme.BG1.name()};
                border: none;
                gridline-color: {theme.qss_color(theme.BD0)};
            }}
            QHeaderView::section {{
                background-color: {theme.BG2.name()};
                color: {theme.TEXT2.name()};
                border: none;
                border-bottom: 1px solid {theme.qss_color(theme.BD1)};
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 600;
            }}
            QTableWidget::item {{
                padding: 6px 12px;
                border-bottom: 1px solid {theme.qss_color(theme.BD0)};
            }}
        """)
        layout.addWidget(self._table, 1)

        # Add button
        add_row = QWidget()
        a_layout = QHBoxLayout(add_row)
        a_layout.setContentsMargins(24, 8, 24, 12)
        a_layout.addStretch()
        add_btn = QPushButton("+ Voce")
        add_btn.setFont(theme.font_ui(11))
        add_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        add_btn.setStyleSheet(f"""
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
        add_btn.clicked.connect(self._on_add_item)
        a_layout.addWidget(add_btn)
        layout.addWidget(add_row)

        self._placeholder = QLabel("Seleziona un conto")
        self._placeholder.setFont(theme.font_ui(14))
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet(f"color: {theme.TEXT4.name()};")
        layout.addWidget(self._placeholder)

        self._header.setVisible(False)
        self._table.setVisible(False)

    def _on_add_item(self):
        if self._current_account_id is None:
            return
        from PyQt6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDoubleSpinBox, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle('Nuova Voce')
        form = QFormLayout(dlg)
        desc_edit = QLineEdit()
        cost_spin = QDoubleSpinBox()
        cost_spin.setRange(0, 9999999)
        cost_spin.setDecimals(2)
        form.addRow('Descrizione:', desc_edit)
        form.addRow('Costo (\u20ac):', cost_spin)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)
        if dlg.exec() and desc_edit.text().strip():
            self.item_created.emit(
                self._current_account_id,
                desc_edit.text().strip(),
                cost_spin.value()
            )

    def load_account(self, acc_id, name, subtotal, items):
        self._current_account_id = acc_id
        self._placeholder.setVisible(False)
        self._header.setVisible(True)
        self._table.setVisible(True)

        self._acc_name.setText(name)
        self._acc_total.setText(f"\u20ac {subtotal:,.0f}")

        self._table.setRowCount(len(items))
        for i, item in enumerate(items):
            for j, val in enumerate([
                item.get("description", ""),
                item.get("cost_type", ""),
                f"\u20ac {item.get('cost', 0):,.0f}",
                f"{item.get('fringes', 0):.0f}%",
            ]):
                cell = QTableWidgetItem(str(val))
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._table.setItem(i, j, cell)

    def clear(self):
        self._current_account_id = None
        self._placeholder.setVisible(True)
        self._header.setVisible(False)
        self._table.setVisible(False)
        self._table.setRowCount(0)


class BudgetView(QWidget):
    def __init__(self, container, parent=None):
        super().__init__(parent)
        self._container = container
        self._project_id = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        self._account_list = AccountListPanel()
        self._account_detail = AccountDetailPanel()

        splitter.addWidget(self._account_list)
        splitter.addWidget(self._account_detail)
        splitter.setSizes([300, 600])

        layout.addWidget(splitter)

        self._account_list.account_selected.connect(self._on_account_selected)
        self._account_list.account_created.connect(self._create_account)
        self._account_detail.item_created.connect(self._create_item)

    def load_project(self, project_id):
        self._project_id = project_id
        db = self._container.database

        try:
            rows = db.execute(
                "SELECT id, account_code, account_name, subtotal FROM budget_accounts "
                "WHERE project_id = ? ORDER BY account_code", (project_id,)
            ).fetchall()
        except Exception:
            rows = []

        accounts = [
            {"id": r[0], "code": r[1], "name": r[2], "subtotal": r[3]}
            for r in rows
        ]
        self._account_list.load_accounts(accounts)
        self._account_detail.clear()

    def _on_account_selected(self, acc_id):
        db = self._container.database
        try:
            acc = db.execute(
                "SELECT account_name, subtotal FROM budget_accounts WHERE id = ?", (acc_id,)
            ).fetchone()
            if not acc:
                return
            items = db.execute(
                "SELECT description, unit_type, rate * units, fringes_percent "
                "FROM budget_details WHERE account_id = ? ORDER BY id", (acc_id,)
            ).fetchall()
            item_list = [
                {"description": i[0], "cost_type": i[1], "cost": i[2], "fringes": i[3] or 0}
                for i in items
            ]
            self._account_detail.load_account(acc_id, acc[0], acc[1] or 0, item_list)
        except Exception:
            self._account_detail.clear()

    def _create_account(self, code, name):
        if self._project_id is None:
            return
        db = self._container.database
        db.execute(
            'INSERT INTO budget_accounts'
            ' (project_id, account_code, account_name, level, sort_order)'
            ' VALUES (?, ?, ?, 1, 0)',
            (self._project_id, code or None, name)
        )
        db.commit()
        self.load_project(self._project_id)

    def _create_item(self, account_id, description, cost):
        db = self._container.database
        db.execute(
            'INSERT INTO budget_details'
            ' (account_id, description, rate, units, unit_type)'
            ' VALUES (?, ?, ?, 1, "flat")',
            (account_id, description, cost)
        )
        db.execute(
            'UPDATE budget_accounts'
            ' SET subtotal = ('
            '   SELECT COALESCE(SUM(rate * units * (1 + fringes_percent/100.0)), 0)'
            '   FROM budget_details WHERE account_id = ?'
            ' ) WHERE id = ?',
            (account_id, account_id)
        )
        db.commit()
        if self._project_id:
            self._on_account_selected(account_id)
            self.load_project(self._project_id)

    def clear(self):
        self._project_id = None
        self._account_list.load_accounts([])
        self._account_detail.clear()
