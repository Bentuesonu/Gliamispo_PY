from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel, QFrame
)
from PySide6.QtCore import Qt, Signal
from gliamispo.ui import theme


class _KPICard(QFrame):
    def __init__(self, title, unit, accent_hex, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background: {theme.BG2.name()};
                border: 1.5px solid {theme.qss_color(theme.BD1)};
                border-radius: 10px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(4)

        t = QLabel(title.upper())
        t.setFont(theme.font_ui(9))
        t.setStyleSheet(f"color:{theme.TEXT3.name()};border:none;background:transparent;")
        layout.addWidget(t)

        self._value_lbl = QLabel("---")
        self._value_lbl.setObjectName("value")
        self._value_lbl.setFont(theme.font_ui(28, bold=True))
        self._value_lbl.setStyleSheet(f"color:{accent_hex};border:none;background:transparent;")
        layout.addWidget(self._value_lbl)

        u = QLabel(unit)
        u.setFont(theme.font_ui(10))
        u.setStyleSheet(f"color:{theme.TEXT4.name()};border:none;background:transparent;")
        layout.addWidget(u)

    def set_value(self, v: str):
        self._value_lbl.setText(v)


class DashboardView(QWidget):
    open_project_requested = Signal()

    def __init__(self, container, parent=None):
        super().__init__(parent)
        self._container = container
        self._project_id = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(24)
        self.setStyleSheet(f"background:{theme.BG1.name()};")

        self._title = QLabel("Dashboard Progetto")
        self._title.setFont(theme.font_ui(22, bold=True))
        self._title.setStyleSheet(f"color:{theme.TEXT0.name()};")
        layout.addWidget(self._title)

        grid = QGridLayout()
        grid.setSpacing(16)

        self._kpi_breakdown = _KPICard("Breakdown", "elementi verificati", theme.STATUS_OK.name())
        self._kpi_days      = _KPICard("Giorni Lavorativi", "pianificati", theme.GOLD.name())
        self._kpi_budget    = _KPICard("Budget Totale", "Euro", theme.STATUS_WARN.name())
        self._kpi_ai        = _KPICard("Confidenza AI Media", "%", theme.STATUS_AI.name())

        grid.addWidget(self._kpi_breakdown, 0, 0)
        grid.addWidget(self._kpi_days,      0, 1)
        grid.addWidget(self._kpi_budget,    1, 0)
        grid.addWidget(self._kpi_ai,        1, 1)
        layout.addLayout(grid)
        layout.addStretch()

    def load_project(self, project_id: int):
        self._project_id = project_id
        db = self._container.database

        # KPI Breakdown
        try:
            r = db.execute(
                "SELECT COUNT(*) as tot, "
                "SUM(CASE WHEN user_verified=1 THEN 1 ELSE 0 END) as ver "
                "FROM scene_elements se "
                "JOIN scenes s ON s.id=se.scene_id "
                "WHERE s.project_id=?", (project_id,)
            ).fetchone()
            tot = r[0] or 1
            ver = r[1] or 0
            self._kpi_breakdown.set_value(f"{int(ver/tot*100)}%")
        except Exception:
            self._kpi_breakdown.set_value("---")

        # KPI Giorni
        try:
            days = db.execute(
                "SELECT COUNT(DISTINCT sd.day_number) FROM shooting_days sd "
                "JOIN shooting_schedules ss ON ss.id=sd.schedule_id "
                "WHERE ss.project_id=?", (project_id,)
            ).fetchone()[0]
            self._kpi_days.set_value(str(days or 0))
        except Exception:
            self._kpi_days.set_value("---")

        # KPI Budget
        try:
            budget = db.execute(
                "SELECT COALESCE(SUM(subtotal),0) FROM budget_accounts "
                "WHERE project_id=?", (project_id,)
            ).fetchone()[0]
            self._kpi_budget.set_value(f"\u20ac{budget:,.0f}")
        except Exception:
            self._kpi_budget.set_value("---")

        # KPI AI confidence
        try:
            conf = db.execute(
                "SELECT AVG(ai_confidence) FROM scene_elements se "
                "JOIN scenes s ON s.id=se.scene_id "
                "WHERE s.project_id=? AND ai_confidence IS NOT NULL",
                (project_id,)
            ).fetchone()[0]
            self._kpi_ai.set_value(f"{int((conf or 0)*100)}%")
        except Exception:
            self._kpi_ai.set_value("---")

    def clear(self):
        self._project_id = None
        for card in (self._kpi_breakdown, self._kpi_days,
                     self._kpi_budget, self._kpi_ai):
            card.set_value("---")
