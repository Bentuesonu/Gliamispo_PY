# src/gliamispo/ui/contact_book_view.py
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QFormLayout, QLineEdit, QDoubleSpinBox, QComboBox,
    QTextEdit, QLabel, QSplitter, QMessageBox,
)
from PySide6.QtCore import Qt, QTimer
from gliamispo.ui import theme

DEPARTMENTS = [
    "", "Regia", "Produzione", "Fotografia", "Arte", "Costumi",
    "Trucco", "Suono", "Montaggio", "VFX", "Effetti Speciali",
    "Cascadeurs", "Cast", "Comparse", "Altro",
]


class ContactBookView(QWidget):
    def __init__(self, container, parent=None):
        super().__init__(parent)
        self._container  = container
        self._project_id = None
        self._current_id = None
        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._autosave)
        self._build_ui()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left.setMinimumWidth(220)
        left.setMaximumWidth(300)
        left.setStyleSheet(f"background-color: {theme.BG2.name()};")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(0)

        # Header
        header = QWidget()
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(16, 12, 16, 8)
        lbl = QLabel("CONTATTI")
        lbl.setFont(theme.font_ui(9, bold=True))
        lbl.setStyleSheet(f"color: {theme.TEXT3.name()};")
        h_layout.addWidget(lbl)
        h_layout.addStretch()
        ll.addWidget(header)

        # Search
        search_wrap = QWidget()
        sw_layout = QHBoxLayout(search_wrap)
        sw_layout.setContentsMargins(16, 0, 16, 8)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Cerca...")
        self._search.setStyleSheet(f"""
            QLineEdit {{
                background-color: {theme.BG1.name()};
                border: 1px solid {theme.qss_color(theme.BD1)};
                border-radius: 4px;
                padding: 6px 10px;
                color: {theme.TEXT1.name()};
            }}
        """)
        self._search.textChanged.connect(self._on_search)
        sw_layout.addWidget(self._search)
        ll.addWidget(search_wrap)

        self._list = QListWidget()
        self._list.setStyleSheet(f"""
            QListWidget {{
                background-color: {theme.BG2.name()};
                border: none;
                outline: none;
            }}
            QListWidget::item {{
                padding: 8px 16px;
                border-bottom: 1px solid {theme.qss_color(theme.BD0)};
                color: {theme.TEXT1.name()};
            }}
            QListWidget::item:selected {{
                background-color: {theme.BG1.name()};
                color: {theme.TEXT0.name()};
            }}
            QListWidget::item:hover {{
                background-color: {theme.qss_color(theme.BD0)};
            }}
        """)
        self._list.currentRowChanged.connect(self._on_contact_selected)
        ll.addWidget(self._list, 1)

        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(16, 8, 16, 8)
        btn_layout.setSpacing(8)
        self._add_btn = QPushButton("+ Nuovo")
        self._add_btn.setFont(theme.font_ui(10))
        self._add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_btn.setStyleSheet(f"""
            QPushButton {{
                color: {theme.GOLD.name()};
                background-color: {theme.qss_color(theme.GOLD_BG)};
                border: 1px solid {theme.qss_color(theme.GOLD_BD)};
                border-radius: 4px;
                padding: 5px 12px;
            }}
            QPushButton:hover {{
                background-color: {theme.qss_color(theme.GOLD_BD)};
            }}
            QPushButton:disabled {{
                color: {theme.TEXT4.name()};
                background-color: transparent;
                border-color: {theme.qss_color(theme.BD1)};
            }}
        """)
        self._add_btn.setEnabled(False)
        self._add_btn.clicked.connect(self._on_add_contact)
        self._del_btn = QPushButton("Elimina")
        self._del_btn.setFont(theme.font_ui(10))
        self._del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._del_btn.setStyleSheet(f"""
            QPushButton {{
                color: {theme.STATUS_ERR.name()};
                background: transparent;
                border: 1px solid {theme.qss_color(theme.BD1)};
                border-radius: 4px;
                padding: 5px 12px;
            }}
            QPushButton:hover {{
                background-color: rgba(192, 24, 32, 0.1);
                border-color: {theme.STATUS_ERR.name()};
            }}
            QPushButton:disabled {{
                color: {theme.TEXT4.name()};
                border-color: {theme.qss_color(theme.BD1)};
            }}
        """)
        self._del_btn.setEnabled(False)
        self._del_btn.clicked.connect(self._on_delete_contact)
        btn_layout.addWidget(self._add_btn)
        btn_layout.addWidget(self._del_btn)
        ll.addWidget(btn_row)

        autopop_wrap = QWidget()
        ap_layout = QHBoxLayout(autopop_wrap)
        ap_layout.setContentsMargins(16, 0, 16, 12)
        self._autopop_btn = QPushButton("\u270e Auto-popola da Cast")
        self._autopop_btn.setFont(theme.font_ui(10))
        self._autopop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._autopop_btn.setStyleSheet(f"""
            QPushButton {{
                color: {theme.TEXT2.name()};
                background: transparent;
                border: 1px solid {theme.qss_color(theme.BD1)};
                border-radius: 4px;
                padding: 5px 12px;
            }}
            QPushButton:hover {{
                background-color: {theme.qss_color(theme.BD0)};
                color: {theme.TEXT0.name()};
            }}
            QPushButton:disabled {{
                color: {theme.TEXT4.name()};
            }}
        """)
        self._autopop_btn.setEnabled(False)
        self._autopop_btn.clicked.connect(self._on_autopopulate)
        ap_layout.addWidget(self._autopop_btn)
        ll.addWidget(autopop_wrap)

        splitter.addWidget(left)

        right = QWidget()
        right.setStyleSheet(f"background-color: {theme.BG1.name()};")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)

        # Header
        detail_header = QWidget()
        dh_layout = QHBoxLayout(detail_header)
        dh_layout.setContentsMargins(24, 16, 24, 12)
        self._detail_label = QLabel("Seleziona un contatto")
        self._detail_label.setFont(theme.font_ui(14, bold=True))
        self._detail_label.setStyleSheet(f"color: {theme.TEXT0.name()};")
        dh_layout.addWidget(self._detail_label)
        rl.addWidget(detail_header)

        # Divider
        div = QWidget()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background-color: {theme.qss_color(theme.BD1)};")
        rl.addWidget(div)

        # Form container
        form_container = QWidget()
        fc_layout = QVBoxLayout(form_container)
        fc_layout.setContentsMargins(24, 16, 24, 16)
        fc_layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Style for form fields
        field_style = f"""
            QLineEdit, QComboBox, QDoubleSpinBox {{
                background-color: {theme.BG0.name()};
                border: 1px solid {theme.qss_color(theme.BD1)};
                border-radius: 4px;
                padding: 6px 10px;
                color: {theme.TEXT1.name()};
            }}
            QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus {{
                border-color: {theme.GOLD.name()};
            }}
            QLineEdit:disabled, QComboBox:disabled, QDoubleSpinBox:disabled {{
                background-color: {theme.BG2.name()};
                color: {theme.TEXT4.name()};
            }}
        """
        label_style = f"color: {theme.TEXT2.name()};"

        self._f_name  = QLineEdit()
        self._f_name.setStyleSheet(field_style)
        self._f_role  = QLineEdit()
        self._f_role.setStyleSheet(field_style)
        self._f_dept  = QComboBox()
        self._f_dept.setStyleSheet(field_style)
        self._f_dept.addItems(DEPARTMENTS)
        self._f_agent = QLineEdit()
        self._f_agent.setStyleSheet(field_style)
        self._f_phone = QLineEdit()
        self._f_phone.setStyleSheet(field_style)
        self._f_email = QLineEdit()
        self._f_email.setStyleSheet(field_style)
        self._f_rate  = QDoubleSpinBox()
        self._f_rate.setStyleSheet(field_style)
        self._f_rate.setRange(0, 99999)
        self._f_rate.setDecimals(2)
        self._f_rate.setSuffix(" EUR/g")
        self._f_notes = QTextEdit()
        self._f_notes.setFixedHeight(80)
        self._f_notes.setStyleSheet(f"""
            QTextEdit {{
                background-color: {theme.BG0.name()};
                border: 1px solid {theme.qss_color(theme.BD1)};
                border-radius: 4px;
                padding: 6px 10px;
                color: {theme.TEXT1.name()};
            }}
            QTextEdit:focus {{
                border-color: {theme.GOLD.name()};
            }}
            QTextEdit:disabled {{
                background-color: {theme.BG2.name()};
                color: {theme.TEXT4.name()};
            }}
        """)

        for lbl_text, widget in [
            ("Nome *:", self._f_name),
            ("Ruolo:", self._f_role),
            ("Reparto:", self._f_dept),
            ("Agente:", self._f_agent),
            ("Telefono:", self._f_phone),
            ("Email:", self._f_email),
            ("Tariffa:", self._f_rate),
            ("Note:", self._f_notes),
        ]:
            lbl = QLabel(lbl_text)
            lbl.setStyleSheet(label_style)
            lbl.setFont(theme.font_ui(11))
            form.addRow(lbl, widget)

        fc_layout.addLayout(form)
        fc_layout.addStretch()
        rl.addWidget(form_container, 1)

        for w in (self._f_name, self._f_role, self._f_agent,
                  self._f_phone, self._f_email):
            w.textChanged.connect(self._schedule_save)
        self._f_dept.currentIndexChanged.connect(self._schedule_save)
        self._f_rate.valueChanged.connect(self._schedule_save)
        self._f_notes.textChanged.connect(self._schedule_save)

        self._set_form_enabled(False)
        splitter.addWidget(right)
        splitter.setSizes([240, 600])
        root.addWidget(splitter)

    def load_project(self, project_id: int):
        self._project_id = project_id
        self._add_btn.setEnabled(True)
        self._autopop_btn.setEnabled(True)
        self._load_list()

    def _load_list(self, filter_text=""):
        self._list.blockSignals(True)
        self._list.clear()
        if self._project_id is None:
            self._list.blockSignals(False)
            return
        rows = self._container.database.execute(
            "SELECT id, full_name, role FROM contacts "
            "WHERE project_id = ? ORDER BY full_name",
            (self._project_id,)
        ).fetchall()
        ft = filter_text.lower()
        for r in rows:
            try:
                cid, name, role = r["id"], r["full_name"], r["role"] or ""
            except (TypeError, KeyError):
                cid, name, role = r[0], r[1], r[2] or ""
            if ft and ft not in name.lower() and ft not in role.lower():
                continue
            item = QListWidgetItem(f"{name}  — {role}" if role else name)
            item.setData(Qt.ItemDataRole.UserRole, cid)
            self._list.addItem(item)
        self._list.blockSignals(False)

    def _on_search(self, text):
        self._load_list(text)

    def _on_contact_selected(self, idx):
        item = self._list.item(idx)
        if item is None:
            self._current_id = None
            self._set_form_enabled(False)
            self._del_btn.setEnabled(False)
            return
        self._current_id = item.data(Qt.ItemDataRole.UserRole)
        self._del_btn.setEnabled(True)
        self._load_contact(self._current_id)

    def _load_contact(self, cid: int):
        row = self._container.database.execute(
            "SELECT full_name, role, department, agent_name, "
            "phone, email, daily_rate, currency, notes "
            "FROM contacts WHERE id = ?", (cid,)
        ).fetchone()
        if row is None:
            return
        self._set_form_enabled(True)
        for w in (self._f_name, self._f_role, self._f_agent,
                  self._f_phone, self._f_email):
            w.blockSignals(True)
        self._f_dept.blockSignals(True)
        self._f_rate.blockSignals(True)
        self._f_notes.blockSignals(True)

        def _v(i):
            try:
                v = row[i]; return v if v is not None else ""
            except Exception:
                return ""

        self._f_name.setText(_v(0))
        self._f_role.setText(_v(1))
        idx = self._f_dept.findText(_v(2))
        self._f_dept.setCurrentIndex(idx if idx >= 0 else 0)
        self._f_agent.setText(_v(3))
        self._f_phone.setText(_v(4))
        self._f_email.setText(_v(5))
        self._f_rate.setValue(float(row[6]) if row[6] else 0.0)
        self._f_notes.setPlainText(_v(8))
        self._detail_label.setText(self._f_name.text() or "Contatto")

        for w in (self._f_name, self._f_role, self._f_agent,
                  self._f_phone, self._f_email):
            w.blockSignals(False)
        self._f_dept.blockSignals(False)
        self._f_rate.blockSignals(False)
        self._f_notes.blockSignals(False)

    def _schedule_save(self):
        if self._current_id is not None:
            self._save_timer.start(600)

    def _autosave(self):
        if self._current_id is None or self._project_id is None:
            return
        name = self._f_name.text().strip()
        if not name:
            return
        self._container.database.execute(
            "UPDATE contacts SET full_name=?, role=?, department=?, "
            "agent_name=?, phone=?, email=?, daily_rate=?, notes=? WHERE id=?",
            (name,
             self._f_role.text().strip() or None,
             self._f_dept.currentText() or None,
             self._f_agent.text().strip() or None,
             self._f_phone.text().strip() or None,
             self._f_email.text().strip() or None,
             self._f_rate.value() if self._f_rate.value() > 0 else None,
             self._f_notes.toPlainText().strip() or None,
             self._current_id)
        )
        self._container.database.commit()
        self._detail_label.setText(name)
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == self._current_id:
                role_txt = self._f_role.text().strip()
                item.setText(f"{name}  — {role_txt}" if role_txt else name)
                break

    def _on_add_contact(self):
        if self._project_id is None:
            return
        self._container.database.execute(
            "INSERT INTO contacts (project_id, full_name) VALUES (?, ?)",
            (self._project_id, "Nuovo Contatto")
        )
        self._container.database.commit()
        self._load_list(self._search.text())
        self._list.setCurrentRow(self._list.count() - 1)

    def _on_delete_contact(self):
        if self._current_id is None:
            return
        name = self._f_name.text() or "questo contatto"
        if QMessageBox.question(
            self, "Elimina contatto", f"Eliminare {name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            self._container.database.execute(
                "DELETE FROM contacts WHERE id = ?", (self._current_id,))
            self._container.database.commit()
            self._current_id = None
            self._set_form_enabled(False)
            self._del_btn.setEnabled(False)
            self._load_list(self._search.text())

    def _on_autopopulate(self):
        if self._project_id is None:
            return
        db = self._container.database
        added = 0
        for name in db.get_cast_names_for_project(self._project_id):
            if not db.execute(
                "SELECT id FROM contacts WHERE project_id=? AND full_name=?",
                (self._project_id, name)
            ).fetchone():
                db.execute(
                    "INSERT INTO contacts (project_id, full_name, role, department) "
                    "VALUES (?, ?, ?, ?)",
                    (self._project_id, name, "Attore/Attrice", "Cast")
                )
                added += 1
        if added:
            db.commit()
            self._load_list(self._search.text())
            QMessageBox.information(self, "Auto-popola",
                f"Aggiunti {added} contatti dal breakdown Cast.")
        else:
            QMessageBox.information(self, "Auto-popola",
                "Nessun nuovo contatto da aggiungere.")

    def _set_form_enabled(self, enabled: bool):
        for w in (self._f_name, self._f_role, self._f_agent,
                  self._f_phone, self._f_email, self._f_notes):
            w.setEnabled(enabled)
        self._f_dept.setEnabled(enabled)
        self._f_rate.setEnabled(enabled)
        if not enabled:
            self._detail_label.setText("Seleziona un contatto")

    def clear(self):
        self._save_timer.stop()
        self._project_id = None
        self._current_id = None
        self._list.clear()
        self._search.clear()
        self._set_form_enabled(False)
        self._add_btn.setEnabled(False)
        self._del_btn.setEnabled(False)
        self._autopop_btn.setEnabled(False)
