import pytest
from unittest.mock import MagicMock

from gliamispo.ui.main_window import MainWindow, ProjectSignals
from gliamispo.ui.project_dialog import ProjectDialog
from gliamispo.ui.breakdown_progress import BreakdownProgress
from gliamispo.ui.scene_detail import SceneDetail
from gliamispo.ui.call_sheet_view import CallSheetView


def _make_row(*values):
    row = MagicMock()
    row.__getitem__ = lambda self, i: values[i]
    return row


def _make_container(project_rows=None, scene_rows=None, element_rows=None):
    project_rows = project_rows or []
    scene_rows = scene_rows or []
    element_rows = element_rows or []

    def execute(sql, params=()):
        cursor = MagicMock()
        if "FROM projects" in sql:
            cursor.fetchall.return_value = project_rows
            cursor.fetchone.return_value = project_rows[0] if project_rows else None
        elif "FROM scenes" in sql:
            cursor.fetchall.return_value = scene_rows
            cursor.fetchone.return_value = scene_rows[0] if scene_rows else None
        elif "FROM scene_elements" in sql:
            cursor.fetchall.return_value = element_rows
            cursor.fetchone.return_value = (len(element_rows),)
        elif "FROM schedule_entries" in sql:
            cursor.fetchall.return_value = []
        elif "FROM budget_accounts" in sql:
            cursor.fetchall.return_value = []
        elif "FROM contacts" in sql:
            cursor.fetchall.return_value = []
        elif "FROM contact_availability" in sql:
            cursor.fetchall.return_value = []
        elif "FROM locations" in sql:
            cursor.fetchall.return_value = []
        elif "FROM distribution_log" in sql:
            cursor.fetchall.return_value = []
        elif "FROM shooting_days" in sql:
            cursor.fetchone.return_value = (0,)
        elif "AVG(ai_confidence)" in sql:
            cursor.fetchone.return_value = (0.85,)
        elif "COUNT" in sql and "user_verified" in sql:
            cursor.fetchone.return_value = (10, 5)
        elif "COUNT" in sql:
            cursor.fetchone.return_value = (0,)
        else:
            cursor.fetchall.return_value = []
            cursor.fetchone.return_value = None
        return cursor

    db = MagicMock()
    db.execute = execute
    db.commit = MagicMock()
    container = MagicMock()
    container.database = db
    return container


class TestMainWindowNew:
    def test_window_title(self, qtbot):
        win = MainWindow(_make_container())
        qtbot.addWidget(win)
        assert win.windowTitle() == "Gliamispo"

    def test_window_min_size(self, qtbot):
        win = MainWindow(_make_container())
        qtbot.addWidget(win)
        assert win.minimumWidth() == 900
        assert win.minimumHeight() == 600

    def test_window_initial_size(self, qtbot):
        win = MainWindow(_make_container())
        qtbot.addWidget(win)
        assert win.width() == 1400
        assert win.height() == 800

    def test_has_sidebar(self, qtbot):
        win = MainWindow(_make_container())
        qtbot.addWidget(win)
        assert win._sidebar is not None
        assert win._sidebar.width() == 248

    def test_has_top_bar(self, qtbot):
        win = MainWindow(_make_container())
        qtbot.addWidget(win)
        assert win._top_bar is not None
        assert win._top_bar.height() == 52

    def test_has_stack(self, qtbot):
        win = MainWindow(_make_container())
        qtbot.addWidget(win)
        assert win._stack is not None
        assert win._stack.count() == 11  # Dashboard + Welcome + 9 tabs

    def test_welcome_is_initial_view(self, qtbot):
        win = MainWindow(_make_container())
        qtbot.addWidget(win)
        assert win._stack.currentIndex() == 1  # Dashboard is idx 0, Welcome is idx 1
        assert win._stack.currentWidget() == win._welcome

    def test_tabs_count(self, qtbot):
        from gliamispo.ui import theme
        assert len(theme.TABS) == 9
        assert theme.TABS[6] == "Shot List"
        assert theme.TABS[7] == "Contact Book"
        assert theme.TABS[8] == "Location Manager"

    def test_has_signals(self, qtbot):
        win = MainWindow(_make_container())
        qtbot.addWidget(win)
        assert isinstance(win._signals, ProjectSignals)

    def test_no_project_selected_initially(self, qtbot):
        win = MainWindow(_make_container())
        qtbot.addWidget(win)
        assert win._current_project_id is None

    def test_tab_views_exist(self, qtbot):
        win = MainWindow(_make_container())
        qtbot.addWidget(win)
        assert win._breakdown is not None
        assert win._script_viewer is not None
        assert win._stripboard is not None
        assert win._budget is not None
        assert win._oneliner is not None
        assert win._dood is not None

    def test_has_dashboard(self, qtbot):
        win = MainWindow(_make_container())
        qtbot.addWidget(win)
        assert win._dashboard is not None
        assert win._stack.widget(0) == win._dashboard


class TestProjectDialog:
    def test_init_empty(self, qtbot):
        dlg = ProjectDialog()
        qtbot.addWidget(dlg)
        assert dlg.windowTitle() == "Nuovo Progetto"
        assert dlg._title_edit.text() == ""

    def test_init_with_project(self, qtbot):
        project = MagicMock()
        project.title = "Film"
        project.director = "Regista"
        project.production_company = "Casa Prod"
        project.language = "it"
        project.currency = "EUR"
        dlg = ProjectDialog(project=project)
        qtbot.addWidget(dlg)
        assert dlg.windowTitle() == "Modifica Progetto"
        assert dlg._title_edit.text() == "Film"
        assert dlg._director_edit.text() == "Regista"

    def test_get_data_returns_dict(self, qtbot):
        dlg = ProjectDialog()
        qtbot.addWidget(dlg)
        dlg._title_edit.setText("Test Film")
        dlg._director_edit.setText("Mario Rossi")
        data = dlg.get_data()
        assert data["title"] == "Test Film"
        assert data["director"] == "Mario Rossi"
        assert data["production_company"] is None

    def test_accept_requires_title(self, qtbot):
        dlg = ProjectDialog()
        qtbot.addWidget(dlg)
        dlg._title_edit.setText("")
        dlg._on_accept()
        assert not dlg.result()

    def test_accept_with_title(self, qtbot):
        dlg = ProjectDialog()
        qtbot.addWidget(dlg)
        dlg._title_edit.setText("Un Titolo")
        dlg._on_accept()
        assert dlg.result() == ProjectDialog.DialogCode.Accepted


class TestBreakdownProgress:
    def test_hidden_on_init(self, qtbot):
        bp = BreakdownProgress()
        qtbot.addWidget(bp)
        assert not bp.isVisible()

    def test_update_below_1_makes_visible(self, qtbot):
        bp = BreakdownProgress()
        qtbot.addWidget(bp)
        bp.show()
        bp.update_progress(0.3, "step 1")
        assert bp.isVisible()
        assert bp._progress_bar.value() == 30
        assert bp._status_label.text() == "step 1"

    def test_update_at_1_hides(self, qtbot):
        bp = BreakdownProgress()
        qtbot.addWidget(bp)
        bp.show()
        bp.update_progress(1.0, "done")
        assert not bp.isVisible()

    def test_reset(self, qtbot):
        bp = BreakdownProgress()
        qtbot.addWidget(bp)
        bp.show()
        bp.update_progress(0.5, "mezzo")
        bp.reset()
        assert not bp.isVisible()
        assert bp._progress_bar.value() == 0


class TestSceneDetail:
    def test_init_shows_placeholders(self, qtbot):
        sd = SceneDetail(_make_container())
        qtbot.addWidget(sd)
        assert sd._scene_number_label.text() == "\u2014"
        assert sd._location_label.text() == "\u2014"

    def test_clear_resets_labels(self, qtbot):
        sd = SceneDetail(_make_container())
        qtbot.addWidget(sd)
        sd._scene_number_label.setText("1A")
        sd.clear()
        assert sd._scene_number_label.text() == "\u2014"
        assert sd._scene_id is None


class TestCallSheetView:
    def test_init(self, qtbot):
        cs = CallSheetView(_make_container())
        qtbot.addWidget(cs)
        assert cs._table.columnCount() == 5
        assert cs._project_id is None

    def test_clear(self, qtbot):
        cs = CallSheetView(_make_container())
        qtbot.addWidget(cs)
        cs._project_id = 1
        cs.clear()
        assert cs._project_id is None
        assert cs._date_combo.count() == 0


