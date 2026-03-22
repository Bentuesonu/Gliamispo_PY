import time
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStackedWidget, QFileDialog, QMessageBox,
)
from PySide6.QtCore import Qt, Signal, QObject, QThread
from PySide6.QtGui import QKeySequence, QShortcut
from gliamispo.ui import theme
from gliamispo.ui.sidebar import SidebarView
from gliamispo.ui.top_bar import TopBarView
from gliamispo.ui.welcome_view import WelcomeView
from gliamispo.ui.breakdown_view import BreakdownView
from gliamispo.ui.script_viewer import ScriptViewerView
from gliamispo.ui.stripboard_view import StripboardView
from gliamispo.ui.budget_view import BudgetView
from gliamispo.ui.oneliner_view import OneLinerView
from gliamispo.ui.dood_view import DayOutOfDaysView
from gliamispo.ui.shot_list_view import ShotListView
from gliamispo.ui.contact_book_view import ContactBookView
from gliamispo.ui.location_view import LocationView
from gliamispo.ui.dashboard_view import DashboardView
from gliamispo.ui.project_dialog import ProjectDialog
from gliamispo.ui.settings_dialog import SettingsDialog
from gliamispo.models.project import Project


class _ImportWorker(QThread):
    progress = Signal(float, str)
    finished = Signal(int)
    error    = Signal(str)

    def __init__(self, orchestrator, path, project_id):
        super().__init__()
        self._orchestrator = orchestrator
        self._path         = path
        self._project_id   = project_id

    def run(self):
        import asyncio
        try:
            asyncio.run(
                self._orchestrator.run_breakdown(
                    self._path, self._project_id,
                    on_progress=self.progress.emit,
                )
            )
            self.finished.emit(self._project_id)
        except Exception as e:
            self.error.emit(str(e))


class ProjectSignals(QObject):
    project_selected = Signal(int)
    scene_selected = Signal(int)
    breakdown_progress = Signal(float, str)


class MainWindow(QMainWindow):
    # Soglia per collasso automatico sidebar
    WIDTH_AUTO_COLLAPSE = 1100

    def __init__(self, container):
        super().__init__()
        self._container = container
        self._signals = ProjectSignals()
        self._current_project_id = None
        self._auto_collapsed = False
        self.setWindowTitle("Gliamispo")
        self.setMinimumSize(900, 600)
        self.resize(1400, 800)

        self.setStyleSheet(theme.APP_STYLE)

        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Sidebar
        self._sidebar = SidebarView()
        root_layout.addWidget(self._sidebar)

        # Right side: top bar + content
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self._top_bar = TopBarView()
        right_layout.addWidget(self._top_bar)

        # Stacked content
        self._stack = QStackedWidget()

        # Dashboard view (index 0)
        self._dashboard = DashboardView(container)
        self._stack.addWidget(self._dashboard)

        # Welcome view (index 1)
        self._welcome = WelcomeView()
        self._stack.addWidget(self._welcome)

        # Tab content views (indices 1-6)
        self._breakdown     = BreakdownView(container)
        self._script_viewer = ScriptViewerView(container)
        self._stripboard    = StripboardView(container)
        self._budget        = BudgetView(container)
        self._oneliner      = OneLinerView(container)
        self._dood          = DayOutOfDaysView(container)

        self._shot_list    = ShotListView(container)
        self._contact_book = ContactBookView(container)
        self._location_mgr = LocationView(container)

        self._stack.addWidget(self._breakdown)
        self._stack.addWidget(self._script_viewer)
        self._stack.addWidget(self._stripboard)
        self._stack.addWidget(self._budget)
        self._stack.addWidget(self._oneliner)
        self._stack.addWidget(self._dood)
        self._stack.addWidget(self._shot_list)      # indice 7
        self._stack.addWidget(self._contact_book)   # indice 8
        self._stack.addWidget(self._location_mgr)   # indice 9

        right_layout.addWidget(self._stack, 1)
        root_layout.addWidget(right, 1)

        # Connect signals
        self._sidebar.project_selected.connect(self._on_project_selected)
        self._sidebar.new_project_requested.connect(self._new_project)
        self._sidebar.import_requested.connect(self._import_script)
        self._sidebar.edit_project_requested.connect(self._edit_project)
        self._sidebar.delete_project_requested.connect(self._delete_project)

        self._welcome.project_selected.connect(self._on_project_selected)
        self._welcome.new_project_requested.connect(self._new_project)
        self._welcome.import_requested.connect(self._import_script)

        self._top_bar.tab_changed.connect(self._on_tab_changed)
        self._top_bar.settings_requested.connect(self._open_settings)
        self._top_bar.export_pdf_requested.connect(self._export_pdf)
        self._top_bar.export_xlsx_requested.connect(self._export_xlsx)
        # ✅ Feature 1.5: ricerca FTS5 — collegato una sola volta qui
        self._top_bar.search_triggered.connect(self._on_search)

        # Initial state
        self._top_bar.set_visible_state(False)
        self._stack.setCurrentIndex(1)  # Show Welcome (Dashboard is idx 0)
        self._setup_shortcuts()
        self.load_projects()

    # ── Responsive resize handling ──────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._adapt_sidebar_to_width()

    def _adapt_sidebar_to_width(self):
        """Collassa/espande automaticamente la sidebar in base alla larghezza."""
        w = self.width()
        should_collapse = w < self.WIDTH_AUTO_COLLAPSE

        if should_collapse and not self._sidebar.is_collapsed():
            self._auto_collapsed = True
            self._sidebar.set_collapsed(True)
        elif not should_collapse and self._auto_collapsed and self._sidebar.is_collapsed():
            self._auto_collapsed = False
            self._sidebar.set_collapsed(False)

    # -------------------------------------------------------------------------

    def _setup_shortcuts(self):
        shortcuts = [
            # Tab navigation (Ctrl+1..9)
            ("Ctrl+1", lambda: self._top_bar._on_tab_clicked(0)),  # Breakdown
            ("Ctrl+2", lambda: self._top_bar._on_tab_clicked(1)),  # Script
            ("Ctrl+3", lambda: self._top_bar._on_tab_clicked(2)),  # Stripboard
            ("Ctrl+4", lambda: self._top_bar._on_tab_clicked(3)),  # Budget
            ("Ctrl+5", lambda: self._top_bar._on_tab_clicked(4)),  # One-Liner
            ("Ctrl+6", lambda: self._top_bar._on_tab_clicked(5)),  # Day Out of Days
            ("Ctrl+7", lambda: self._top_bar._on_tab_clicked(6)),  # Shot List
            ("Ctrl+8", lambda: self._top_bar._on_tab_clicked(7)),  # Contact Book
            ("Ctrl+9", lambda: self._top_bar._on_tab_clicked(8)),  # Location Manager
            # Azioni progetto
            ("Ctrl+N", self._new_project),
            ("Ctrl+Shift+B", self._import_script),
            # Ricerca
            ("Ctrl+F", lambda: self._top_bar._search_edit.setFocus()),
            # Dashboard
            ("Ctrl+Home", lambda: self._stack.setCurrentIndex(0)),
        ]
        for key, handler in shortcuts:
            sc = QShortcut(QKeySequence(key), self)
            sc.activated.connect(handler)

    # -------------------------------------------------------------------------

    def load_projects(self):
        db = self._container.database
        rows = db.execute(
            "SELECT id, title, director FROM projects ORDER BY last_modified DESC"
        ).fetchall()
        projects = [{"id": r[0], "title": r[1], "director": r[2]} for r in rows]
        self._sidebar.load_projects(projects)
        self._welcome.load_recent(projects)

    def _on_project_selected(self, project_id):
        self._current_project_id = project_id
        db = self._container.database

        row = db.execute(
            "SELECT title, director FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if row:
            self._top_bar.set_project_info(row[0], row[1])

        self._top_bar.set_visible_state(True)
        self._top_bar.set_export_visible(False)  # Dashboard non supporta export
        self._sidebar.select_project(project_id)
        # Load dashboard KPIs and show it
        self._dashboard.load_project(project_id)
        self._stack.setCurrentIndex(0)  # Show Dashboard

    def _on_tab_changed(self, idx):
        if self._current_project_id is None:
            self._stack.setCurrentIndex(1)  # Show Welcome
            return

        pid = self._current_project_id
        self._stack.setCurrentIndex(idx + 2)  # +2 because Dashboard=0, Welcome=1

        # Tab che supportano esportazione: Breakdown(0), Stripboard(2), Budget(3), OneLiner(4), DOOD(5)
        export_tabs = {0, 2, 3, 4, 5}
        self._top_bar.set_export_visible(idx in export_tabs)

        if idx == 0:
            self._breakdown.load_project(pid)
        elif idx == 1:
            self._script_viewer.load_project(pid)
        elif idx == 2:
            self._stripboard.load_project(pid)
        elif idx == 3:
            self._budget.load_project(pid)
        elif idx == 4:
            self._oneliner.load_project(pid)
        elif idx == 5:
            self._dood.load_project(pid)
        elif idx == 6:
            self._shot_list.load_project(pid)
        elif idx == 7:
            self._contact_book.load_project(pid)
        elif idx == 8:
            self._location_mgr.load_project(pid)

    def _new_project(self):
        dialog = ProjectDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            db = self._container.database
            now = int(time.time())
            db.execute(
                "INSERT INTO projects (title, director, production_company, "
                "language, currency, created_date, last_modified) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (data["title"], data["director"], data["production_company"],
                 data["language"], data["currency"], now, now)
            )
            db.commit()
            self.load_projects()

    def _edit_project(self, project_id):
        db = self._container.database
        row = db.execute(
            "SELECT title, director, production_company, language, currency "
            "FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if not row:
            return

        p = Project()
        p.id = project_id
        p.title = row[0]
        p.director = row[1]
        p.production_company = row[2]
        p.language = row[3]
        p.currency = row[4]

        dialog = ProjectDialog(self, project=p)
        if dialog.exec():
            data = dialog.get_data()
            db.execute(
                "UPDATE projects SET title=?, director=?, production_company=?, "
                "language=?, currency=?, last_modified=? WHERE id=?",
                (data["title"], data["director"], data["production_company"],
                 data["language"], data["currency"], int(time.time()), project_id)
            )
            db.commit()
            self.load_projects()
            if self._current_project_id == project_id:
                self._on_project_selected(project_id)

    def _delete_project(self, project_id):
        reply = QMessageBox.question(
            self, "Elimina progetto",
            "Sei sicuro di voler eliminare questo progetto?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                db = self._container.database
                # Pulisci search_index FTS5 prima di eliminare le scene
                db.execute(
                    "DELETE FROM search_index WHERE content_type='element' "
                    "AND content_id IN (SELECT se.id FROM scene_elements se "
                    "JOIN scenes s ON s.id = se.scene_id WHERE s.project_id = ?)",
                    (project_id,)
                )
                db.execute(
                    "DELETE FROM search_index WHERE content_type='scene' "
                    "AND content_id IN (SELECT id FROM scenes WHERE project_id = ?)",
                    (project_id,)
                )
                # Elimina il progetto - le FK con ON DELETE CASCADE eliminano tutto il resto
                db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
                db.commit()
            except Exception as e:
                QMessageBox.critical(
                    self, "Errore",
                    f"Impossibile eliminare il progetto:\n{e}"
                )
                return

            if self._current_project_id == project_id:
                self._current_project_id = None
                self._top_bar.set_visible_state(False)
                self._stack.setCurrentIndex(1)  # Welcome view

            self.load_projects()

    def _import_script(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importa Sceneggiatura", "",
            "Sceneggiature (*.fountain *.txt *.pdf *.docx *.doc *.sqlite *.db);;Tutti i file (*)"
        )
        if not path:
            return
        lower = path.lower()
        if lower.endswith((".sqlite", ".db")):
            self._import_swift_db(path)
        elif lower.endswith((".fountain", ".txt", ".pdf", ".docx", ".doc")):
            self._import_fountain_file(path)
        else:
            QMessageBox.warning(self, "Formato non supportato",
                                "Formato file non riconosciuto.")

    def _import_fountain_file(self, path):
        import time, os

        lower = path.lower()
        try:
            if lower.endswith(".pdf"):
                try:
                    import pdfplumber
                    with pdfplumber.open(path) as pdf:
                        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
                except ImportError:
                    QMessageBox.warning(self, "Dipendenza mancante",
                        "Per importare PDF installa pdfplumber:\n  pip install pdfplumber")
                    return
            elif lower.endswith((".docx", ".doc")):
                try:
                    from docx import Document
                    doc = Document(path)
                    text = "\n".join(p.text for p in doc.paragraphs)
                except ImportError:
                    QMessageBox.warning(self, "Dipendenza mancante",
                        "Per importare DOCX installa python-docx:\n  pip install python-docx")
                    return
            else:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
        except Exception as e:
            QMessageBox.warning(self, "Errore lettura file", str(e))
            return

        if not text.strip():
            QMessageBox.warning(self, "File vuoto",
                                "Il file non contiene testo leggibile.")
            return

        from gliamispo.ui.project_dialog import ProjectDialog
        default_title = os.path.splitext(os.path.basename(path))[0]
        dialog = ProjectDialog(self)
        dialog._title_edit.setText(default_title)
        if not dialog.exec():
            return
        data = dialog.get_data()

        db = self._container.database
        now = int(time.time())
        db.execute(
            "INSERT INTO projects (title, director, production_company, "
            "language, currency, created_date, last_modified) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (data["title"], data["director"], data["production_company"],
             data["language"], data["currency"], now, now)
        )
        db.commit()
        project_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        import tempfile
        if lower.endswith((".pdf", ".docx", ".doc")):
            tmp = tempfile.NamedTemporaryFile(
                mode="w", suffix=".fountain", encoding="utf-8", delete=False
            )
            tmp.write(text)
            tmp.close()
            import_path = tmp.name
            self._import_tmp_path = import_path
        else:
            import_path = path
            self._import_tmp_path = None

        self._import_worker = _ImportWorker(
            self._container.breakdown_orchestrator,
            import_path, project_id
        )
        self._import_worker.progress.connect(lambda v, m: None)
        self._import_worker.finished.connect(self._on_import_done)
        self._import_worker.error.connect(self._on_import_error)
        self._import_worker.start()

    def _cleanup_import_tmp(self):
        import os
        tmp = getattr(self, '_import_tmp_path', None)
        if tmp:
            try:
                os.unlink(tmp)
            except Exception:
                pass
            self._import_tmp_path = None

    def _on_import_done(self, project_id):
        self._cleanup_import_tmp()
        self.load_projects()
        self._on_project_selected(project_id)

    def _on_import_error(self, msg):
        self._cleanup_import_tmp()
        QMessageBox.warning(self, 'Errore import', msg)

    def _import_swift_db(self, path):
        from gliamispo.import_.swift_db_importer import SwiftDbImporter
        importer = SwiftDbImporter()
        db = self._container.database
        conn = db._conn if hasattr(db, "_conn") else db.connect()
        try:
            stats = importer.import_db(path, conn)
            QMessageBox.information(
                self, "Importazione completata",
                f"Progetti: {stats.get('projects', 0)}\n"
                f"Scene: {stats.get('scenes', 0)}\n"
                f"Elementi: {stats.get('elements', 0)}"
            )
            self.load_projects()

            row = db.execute(
                "SELECT id FROM projects ORDER BY last_modified DESC LIMIT 1"
            ).fetchone()
            if row:
                self._on_project_selected(row[0])

        except Exception as e:
            QMessageBox.warning(self, "Errore importazione", str(e))

    def _open_settings(self):
        project_data = None
        if self._current_project_id:
            db = self._container.database
            row = db.execute(
                "SELECT language, currency, hours_per_shooting_day, "
                "contingency_percent, ml_enabled, ml_min_confidence "
                "FROM projects WHERE id = ?", (self._current_project_id,)
            ).fetchone()
            if row:
                project_data = {
                    "language": row[0], "currency": row[1],
                    "hours_per_shooting_day": row[2], "contingency_percent": row[3],
                    "ml_enabled": row[4], "ml_min_confidence": row[5],
                }

        dialog = SettingsDialog(self._container, project_data, self)
        if dialog.exec() and self._current_project_id:
            settings = dialog.get_settings()
            db = self._container.database
            db.execute(
                "UPDATE projects SET language=?, currency=?, "
                "hours_per_shooting_day=?, contingency_percent=?, "
                "ml_enabled=?, ml_min_confidence=?, last_modified=? WHERE id=?",
                (settings["language"], settings["currency"],
                 settings["hours_per_shooting_day"], settings["contingency_percent"],
                 settings["ml_enabled"], settings["ml_min_confidence"],
                 int(time.time()), self._current_project_id)
            )
            db.commit()

    def _export_pdf(self):
        if not self._current_project_id:
            return
        current_widget = self._stack.currentWidget()
        if hasattr(current_widget, '_on_export_pdf'):
            try:
                current_widget._on_export_pdf()
            except Exception as e:
                QMessageBox.critical(
                    self, "Errore Esportazione PDF",
                    f"Si è verificato un errore:\n{e}"
                )
        else:
            QMessageBox.information(
                self, "Esportazione",
                "L'esportazione PDF non è disponibile per questa vista."
            )

    def _export_xlsx(self):
        if not self._current_project_id:
            return
        current_widget = self._stack.currentWidget()
        if hasattr(current_widget, '_on_export_excel'):
            try:
                current_widget._on_export_excel()
            except Exception as e:
                QMessageBox.critical(
                    self, "Errore Esportazione Excel",
                    f"Si è verificato un errore:\n{e}"
                )
        else:
            QMessageBox.information(
                self, "Esportazione",
                "L'esportazione Excel non è disponibile per questa vista."
            )

    # =========================================================================
    # ✅ Feature 1.5 — Ricerca Globale FTS5
    # =========================================================================

    def _on_search(self, query: str):
        """
        Slot collegato a TopBarView.search_triggered.
        Apre SearchResultsDialog filtrata per il progetto corrente.
        """
        if not query:
            return
        if self._current_project_id is None:
            return

        from gliamispo.ui.search_dialog import SearchResultsDialog

        dlg = SearchResultsDialog(
            self._container.database,
            self._current_project_id,
            query,
            self,
        )
        dlg.result_selected.connect(self._on_search_result_selected)
        dlg.exec()

    def _on_search_result_selected(self, content_type: str, content_id: int):
        """
        Naviga alla vista corretta in base al tipo di risultato.
        """
        tab_map = {
            "scene":    0,   # Breakdown
            "element":  0,   # Breakdown
            "location": 2,   # Stripboard (futuro)
        }
        idx = tab_map.get(content_type, 0)
        self._top_bar._on_tab_clicked(idx)
        self._top_bar.set_current_tab(idx)