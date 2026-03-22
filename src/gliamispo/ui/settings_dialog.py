from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QWidget, QFormLayout, QSlider, QCheckBox,
    QComboBox, QLineEdit, QFrame, QDoubleSpinBox, QScrollArea,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from gliamispo.ui import theme


class SettingsDialog(QDialog):
    def __init__(self, container, project=None, parent=None):
        super().__init__(parent)
        self._container = container
        self._project = project
        self.setWindowTitle("Impostazioni")
        self.setMinimumSize(540, 420)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {theme.BG1.name()};
            }}
            QLabel {{
                color: {theme.TEXT1.name()};
            }}
            QTabWidget::pane {{
                border: 1px solid {theme.qss_color(theme.BD1)};
                background-color: {theme.BG1.name()};
                border-radius: 4px;
            }}
            QTabBar::tab {{
                background-color: {theme.BG2.name()};
                color: {theme.TEXT2.name()};
                padding: 8px 20px;
                border: none;
                border-bottom: 2px solid transparent;
            }}
            QTabBar::tab:selected {{
                color: {theme.GOLD.name()};
                border-bottom: 2px solid {theme.GOLD.name()};
                background-color: {theme.BG1.name()};
            }}
            QLineEdit, QComboBox, QDoubleSpinBox {{
                background-color: {theme.BG0.name()};
                color: {theme.TEXT0.name()};
                border: 1px solid {theme.qss_color(theme.BD1)};
                border-radius: 4px;
                padding: 6px 10px;
            }}
            QCheckBox {{
                color: {theme.TEXT1.name()};
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
            }}
            QSlider::groove:horizontal {{
                height: 4px;
                background: {theme.qss_color(theme.BD2)};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {theme.GOLD.name()};
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        tabs = QTabWidget()

        # General tab
        general = QWidget()
        g_layout = QFormLayout(general)
        g_layout.setContentsMargins(20, 20, 20, 20)
        g_layout.setSpacing(12)

        self._language_combo = QComboBox()
        self._language_combo.addItems(["Italiano", "English", "Fran\u00e7ais", "Espa\u00f1ol"])
        g_layout.addRow("Lingua:", self._language_combo)

        self._currency_edit = QLineEdit()
        self._currency_edit.setPlaceholderText("EUR")
        g_layout.addRow("Valuta:", self._currency_edit)

        self._hours_spin = QDoubleSpinBox()
        self._hours_spin.setRange(4, 18)
        self._hours_spin.setValue(10.0)
        self._hours_spin.setSuffix(" ore")
        g_layout.addRow("Ore per giorno:", self._hours_spin)

        self._contingency_spin = QDoubleSpinBox()
        self._contingency_spin.setRange(0, 50)
        self._contingency_spin.setValue(10.0)
        self._contingency_spin.setSuffix(" %")
        g_layout.addRow("Contingenza:", self._contingency_spin)

        tabs.addTab(general, "Generale")

        # AI & ML tab
        ai_tab = QWidget()
        a_layout = QFormLayout(ai_tab)
        a_layout.setContentsMargins(20, 20, 20, 20)
        a_layout.setSpacing(12)

        self._ml_enabled = QCheckBox("Abilita suggerimenti ML")
        self._ml_enabled.setChecked(True)
        a_layout.addRow(self._ml_enabled)

        conf_widget = QWidget()
        conf_layout = QVBoxLayout(conf_widget)
        conf_layout.setContentsMargins(0, 0, 0, 0)
        conf_layout.setSpacing(4)

        self._confidence_slider = QSlider(Qt.Orientation.Horizontal)
        self._confidence_slider.setRange(0, 100)
        self._confidence_slider.setValue(60)
        self._confidence_slider.setTickInterval(10)
        self._confidence_slider.valueChanged.connect(self._on_confidence_changed)

        self._confidence_label = QLabel("60%")
        self._confidence_label.setFont(theme.font_ui(11, bold=True))
        self._confidence_label.setStyleSheet(f"color: {theme.GOLD.name()};")

        conf_row = QHBoxLayout()
        conf_row.addWidget(self._confidence_slider, 1)
        conf_row.addWidget(self._confidence_label)
        conf_layout.addLayout(conf_row)

        hint = QLabel("Soglia minima per mostrare suggerimenti automatici")
        hint.setFont(theme.font_ui(10))
        hint.setStyleSheet(f"color: {theme.TEXT4.name()};")
        conf_layout.addWidget(hint)

        a_layout.addRow("Confidenza minima:", conf_widget)

        tabs.addTab(ai_tab, "AI & ML")

        stats_tab = self._build_stats_tab()
        tabs.addTab(stats_tab, "\U0001f4ca Metriche")

        layout.addWidget(tabs, 1)

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

        save_btn = QPushButton("Salva")
        save_btn.setFont(theme.font_ui(11, bold=True))
        save_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        save_btn.setStyleSheet(f"""
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
        save_btn.clicked.connect(self.accept)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

        if project:
            self._load_project(project)

    def _load_project(self, p):
        lang = p.get("language") or "Italiano"
        idx = self._language_combo.findText(lang)
        if idx >= 0:
            self._language_combo.setCurrentIndex(idx)
        self._currency_edit.setText(p.get("currency") or "")
        self._hours_spin.setValue(p.get("hours_per_shooting_day") or 10.0)
        self._contingency_spin.setValue(p.get("contingency_percent") or 10.0)
        self._ml_enabled.setChecked(bool(p.get("ml_enabled", 1)))
        conf = int((p.get("ml_min_confidence") or 0.6) * 100)
        self._confidence_slider.setValue(conf)
        self._confidence_label.setText(f"{conf}%")

    def _build_stats_tab(self) -> QWidget:
        outer = QScrollArea()
        outer.setWidgetResizable(True)
        outer.setStyleSheet("QScrollArea { border: none; }")
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        db = self._container.database
        try:
            metrics = db.execute('''
                SELECT
                    CAST(period_start AS TEXT) as period,
                    total_predictions,
                    correct_predictions,
                    CASE WHEN total_predictions > 0
                         THEN ROUND(correct_predictions * 100.0 / total_predictions, 1)
                         ELSE 0 END as accuracy_pct
                FROM ml_performance_metrics
                ORDER BY period_start DESC LIMIT 10
            ''').fetchall()
            if metrics:
                hdr = QLabel("Ultime sessioni ML")
                hdr.setFont(theme.font_ui(11, bold=True))
                layout.addWidget(hdr)
                for m in metrics:
                    try:
                        total = m["total_predictions"]
                        correct = m["correct_predictions"]
                        pct = m["accuracy_pct"]
                    except (TypeError, KeyError):
                        total, correct, pct = m[1], m[2], m[3]
                    row_lbl = QLabel(
                        f"Predizioni: {total}  |  Corrette: {correct}  |  Accuratezza: {pct}%")
                    row_lbl.setFont(theme.font_ui(10))
                    layout.addWidget(row_lbl)
            else:
                layout.addWidget(QLabel("Nessuna metrica disponibile ancora."))
        except Exception:
            layout.addWidget(QLabel("Dati metriche non disponibili."))
        try:
            corrections = db.execute(
                'SELECT COUNT(*) FROM user_corrections').fetchone()[0]
            lbl = QLabel(f"Correzioni utente totali: {corrections}")
            lbl.setFont(theme.font_ui(11, bold=True))
            lbl.setStyleSheet(f"color: {theme.GOLD.name()};")
            layout.addWidget(lbl)
        except Exception:
            pass
        layout.addStretch()
        outer.setWidget(inner)
        return outer

    def _on_confidence_changed(self, value):
        self._confidence_label.setText(f"{value}%")

    def get_settings(self):
        return {
            "language": self._language_combo.currentText(),
            "currency": self._currency_edit.text().strip() or None,
            "hours_per_shooting_day": self._hours_spin.value(),
            "contingency_percent": self._contingency_spin.value(),
            "ml_enabled": 1 if self._ml_enabled.isChecked() else 0,
            "ml_min_confidence": self._confidence_slider.value() / 100.0,
        }
