import pytest
from unittest.mock import MagicMock
from PySide6.QtCore import Qt

from gliamispo.ui import theme
from gliamispo.ui.sidebar import SidebarView, SidebarProjectRow
from gliamispo.ui.top_bar import TopBarView, TabButton
from gliamispo.ui.welcome_view import WelcomeView, RecentProjectCard
from gliamispo.ui.breakdown_view import (
    BreakdownView, SceneListColumn, SceneDetailColumn, ElementsPanel,
)
from gliamispo.ui.script_viewer import ScriptViewerView, CategorySidebar, ScriptContentView
from gliamispo.ui.stripboard_view import StripboardView, SceneStripRow, DayBreakHeader
from gliamispo.ui.budget_view import BudgetView, AccountListPanel, AccountDetailPanel
from gliamispo.ui.oneliner_view import OneLinerView
from gliamispo.ui.dood_view import DayOutOfDaysView
from gliamispo.ui.settings_dialog import SettingsDialog
# ✅ Feature 1.5: import nuovo modulo
from gliamispo.ui.search_dialog import SearchResultsDialog


def _make_container():
    def execute(sql, params=()):
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        cursor.fetchone.return_value = (0,)
        return cursor

    db = MagicMock()
    db.execute = execute
    db.commit = MagicMock()
    container = MagicMock()
    container.database = db
    return container


# ── Helpers per SearchResultsDialog ─────────────────────────────────────────

def _make_search_db(rows=None, raise_exc=False):
    """
    Mock di DatabaseManager.execute() per SearchResultsDialog.

    rows=None oppure raise_exc=True → simula DB senza FTS5 (exception).
    rows=[...]                       → restituisce quei risultati.
    """
    db = MagicMock()
    cursor = MagicMock()
    if raise_exc or rows is None:
        cursor.fetchall.side_effect = Exception("no such table: search_index")
    else:
        cursor.fetchall.return_value = rows
    db.execute.return_value = cursor
    return db


# ── Theme tests ──────────────────────────────────────────────────────────────

class TestTheme:
    def test_colors_are_qcolor(self):
        assert theme.BG0.isValid()
        assert theme.BG1.isValid()
        assert theme.BG2.isValid()
        assert theme.BG3.isValid()
        assert theme.TEXT0.isValid()
        assert theme.GOLD.isValid()

    def test_sidebar_bg_is_dark(self):
        assert theme.SIDEBAR_BG.red() < 50
        assert theme.SIDEBAR_BG.green() < 50

    def test_gold_color(self):
        assert theme.GOLD.name() == "#c8940a"

    def test_strip_color_for(self):
        c = theme.strip_color_for("INT", "GIORNO")
        assert c.isValid()
        assert c.name() == "#7a4a0e"

    def test_strip_color_default(self):
        c = theme.strip_color_for("UNKNOWN", "UNKNOWN")
        assert c.isValid()
        assert c.name() == "#5a5048"

    def test_category_color(self):
        c = theme.category_color("Cast")
        assert c.isValid()
        assert c.name() == "#b06000"

    def test_confidence_color_high(self):
        c = theme.confidence_color(0.95)
        assert c == theme.STATUS_OK

    def test_confidence_color_medium(self):
        c = theme.confidence_color(0.75)
        assert c == theme.STATUS_WARN

    def test_confidence_color_low(self):
        c = theme.confidence_color(0.5)
        assert c == theme.STATUS_ERR

    def test_confidence_color_none(self):
        c = theme.confidence_color(None)
        assert c == theme.TEXT3

    def test_font_ui(self):
        f = theme.font_ui(12, bold=True)
        assert f.pointSize() == 12
        assert f.bold()

    def test_font_mono(self):
        f = theme.font_mono(13)
        assert f.pointSize() == 13

    def test_category_icons_complete(self):
        for cat in theme.CATEGORY_COLORS:
            assert cat in theme.CATEGORY_ICON_FILES

    def test_tabs_list(self):
        # 9 tabs: Breakdown, Script, Stripboard, Budget, One-Liner, Day Out of Days,
        # Shot List, Contact Book, Location Manager
        assert len(theme.TABS) == 9
        assert theme.TABS[0] == "Breakdown"

    def test_app_style_not_empty(self):
        assert len(theme.APP_STYLE) > 100


# ── Sidebar tests ─────────────────────────────────────────────────────────────

class TestSidebarView:
    def test_init_width(self, qtbot):
        sb = SidebarView()
        qtbot.addWidget(sb)
        assert sb.width() == 248

    def test_load_projects(self, qtbot):
        sb = SidebarView()
        qtbot.addWidget(sb)
        projects = [
            {"id": 1, "title": "Film A", "director": "Dir A"},
            {"id": 2, "title": "Film B", "director": None},
        ]
        sb.load_projects(projects)
        assert len(sb._rows) == 2

    def test_select_project(self, qtbot):
        sb = SidebarView()
        qtbot.addWidget(sb)
        sb.load_projects([{"id": 1, "title": "A", "director": "X"}])
        sb.select_project(1)
        assert sb._selected_id == 1
        assert sb._rows[0]._selected

    def test_project_selected_signal(self, qtbot):
        sb = SidebarView()
        qtbot.addWidget(sb)
        sb.load_projects([{"id": 5, "title": "Z", "director": None}])
        received = []
        sb.project_selected.connect(received.append)
        sb._on_row_clicked(5)
        assert received == [5]


class TestSidebarProjectRow:
    def test_init(self, qtbot):
        row = SidebarProjectRow(1, "Titolo", "Regista")
        qtbot.addWidget(row)
        assert row._project_id == 1
        assert not row._selected

    def test_set_selected(self, qtbot):
        row = SidebarProjectRow(1, "Titolo", "Regista")
        qtbot.addWidget(row)
        row.set_selected(True)
        assert row._selected


# ── Top Bar tests ─────────────────────────────────────────────────────────────

class TestTopBarView:
    def test_init_height(self, qtbot):
        tb = TopBarView()
        qtbot.addWidget(tb)
        assert tb.height() == 52

    def test_has_tab_buttons(self, qtbot):
        tb = TopBarView()
        qtbot.addWidget(tb)
        assert len(tb._tab_buttons) == 9

    def test_tab_changed_signal(self, qtbot):
        tb = TopBarView()
        qtbot.addWidget(tb)
        received = []
        tb.tab_changed.connect(received.append)
        tb._on_tab_clicked(2)
        assert received == [2]

    def test_set_project_info(self, qtbot):
        tb = TopBarView()
        qtbot.addWidget(tb)
        tb.set_project_info("Film Test", "Regista")
        assert tb._title_label.text() == "Film Test"
        assert "Regista" in tb._director_label.text()

    # ✅ MODIFICATO: aggiunge verifica _search_edit (Feature 1.5)
    def test_set_visible_state(self, qtbot):
        tb = TopBarView()
        qtbot.addWidget(tb)
        tb.show()

        tb.set_visible_state(False)
        for btn in tb._tab_buttons:
            assert btn.isHidden()
        # ✅ Feature 1.5: _search_edit si nasconde insieme ai tab
        assert tb._search_edit.isHidden()

        tb.set_visible_state(True)
        for btn in tb._tab_buttons:
            assert not btn.isHidden()
        # ✅ Feature 1.5: _search_edit torna visibile con il progetto
        assert not tb._search_edit.isHidden()

    # ✅ NUOVO: verifica che _search_edit esista ed abbia il placeholder corretto
    def test_search_edit_exists(self, qtbot):
        tb = TopBarView()
        qtbot.addWidget(tb)
        assert hasattr(tb, "_search_edit")
        assert "Cerca" in tb._search_edit.placeholderText()

    # ✅ NUOVO: _search_edit inizialmente nascosto (nessun progetto aperto)
    def test_search_edit_initially_hidden(self, qtbot):
        tb = TopBarView()
        qtbot.addWidget(tb)
        tb.show()
        assert tb._search_edit.isHidden()

    # ✅ NUOVO: search_triggered emesso dopo >= 2 caratteri
    def test_search_triggered_signal_emits(self, qtbot):
        tb = TopBarView()
        qtbot.addWidget(tb)
        received = []
        tb.search_triggered.connect(received.append)

        # Forza emissione diretta bypassando il debounce timer
        tb._search_edit.setText("pi")
        tb._emit_search()

        assert len(received) == 1
        assert received[0] == "pi"

    # ✅ NUOVO: ricerca con 1 solo carattere NON emette il segnale
    def test_search_triggered_not_emitted_for_single_char(self, qtbot):
        tb = TopBarView()
        qtbot.addWidget(tb)
        received = []
        tb.search_triggered.connect(received.append)

        tb._search_edit.setText("p")
        tb._emit_search()   # il timer chiama _emit_search, che controlla len >= 2

        assert len(received) == 0

    # ✅ NUOVO: svuotare il campo emette stringa vuota (reset)
    def test_search_clear_emits_empty_string(self, qtbot):
        tb = TopBarView()
        qtbot.addWidget(tb)
        received = []
        tb.search_triggered.connect(received.append)

        # Imposta testo, poi svuota — deve emettere ""
        tb._search_edit.setText("pistola")
        received.clear()
        tb._search_edit.clear()   # textChanged → len==0 → emit ""

        assert "" in received

    # ✅ NUOVO: set_visible_state(False) cancella il testo della ricerca
    def test_set_visible_state_false_clears_search(self, qtbot):
        tb = TopBarView()
        qtbot.addWidget(tb)
        tb.show()
        tb.set_visible_state(True)
        tb._search_edit.setText("qualcosa")
        tb.set_visible_state(False)
        assert tb._search_edit.text() == ""


class TestTabButton:
    def test_init(self, qtbot):
        btn = TabButton("Breakdown")
        qtbot.addWidget(btn)
        assert not btn._active

    def test_set_active(self, qtbot):
        btn = TabButton("Breakdown")
        qtbot.addWidget(btn)
        btn.set_active(True)
        assert btn._active
        assert btn.isChecked()


# ── Welcome View tests ────────────────────────────────────────────────────────

class TestWelcomeView:
    def test_init(self, qtbot):
        wv = WelcomeView()
        qtbot.addWidget(wv)
        assert len(wv._cards) == 0

    def test_load_recent(self, qtbot):
        wv = WelcomeView()
        qtbot.addWidget(wv)
        wv.load_recent([
            {"id": 1, "title": "A", "director": "X"},
            {"id": 2, "title": "B", "director": "Y"},
        ])
        assert len(wv._cards) == 2
        assert not wv._recent_header.isHidden()

    def test_load_recent_empty(self, qtbot):
        wv = WelcomeView()
        qtbot.addWidget(wv)
        wv.load_recent([])
        assert len(wv._cards) == 0
        assert wv._recent_header.isHidden()

    def test_project_selected_signal(self, qtbot):
        wv = WelcomeView()
        qtbot.addWidget(wv)
        received = []
        wv.project_selected.connect(received.append)
        wv.load_recent([{"id": 3, "title": "C", "director": None}])
        wv._cards[0].clicked.emit(3)
        assert received == [3]


# ── Breakdown View tests ──────────────────────────────────────────────────────

class TestSceneListColumn:
    def test_init(self, qtbot):
        slc = SceneListColumn()
        qtbot.addWidget(slc)
        assert slc.minimumWidth() == 268
        assert len(slc._rows) == 0

    def test_load_scenes(self, qtbot):
        slc = SceneListColumn()
        qtbot.addWidget(slc)
        scenes = [
            {"id": 1, "scene_number": "1", "location": "CUCINA",
             "int_ext": "INT", "day_night": "GIORNO",
             "page_start_whole": 1, "page_start_eighths": 0,
             "page_end_whole": 1, "page_end_eighths": 3},
        ]
        slc.load_scenes(scenes, 5, "1 3/8")
        assert len(slc._rows) == 1
        assert slc._count_label.text() == "1"

    def test_scene_selected_signal(self, qtbot):
        slc = SceneListColumn()
        qtbot.addWidget(slc)
        slc.load_scenes([
            {"id": 7, "scene_number": "1", "location": "A",
             "int_ext": "INT", "day_night": "GIORNO",
             "page_start_whole": 0, "page_start_eighths": 0,
             "page_end_whole": 0, "page_end_eighths": 0},
        ])
        received = []
        slc.scene_selected.connect(received.append)
        slc._on_row_clicked(7)
        assert received == [7]


class TestSceneDetailColumn:
    def test_init_shows_placeholder(self, qtbot):
        sdc = SceneDetailColumn()
        qtbot.addWidget(sdc)
        assert not sdc._placeholder.isHidden()
        assert sdc._scroll.isHidden()

    def test_load_scene(self, qtbot):
        sdc = SceneDetailColumn()
        qtbot.addWidget(sdc)
        scene = {"scene_number": "1", "int_ext": "INT", "location": "CUCINA",
                 "day_night": "GIORNO", "synopsis": "Testo scena"}
        elements = [{"category": "Cast", "element_name": "Marco"}]
        sdc.load_scene(scene, elements)
        assert sdc._placeholder.isHidden()
        assert not sdc._scroll.isHidden()
        assert "1" in sdc._scene_header.text()

    def test_clear(self, qtbot):
        sdc = SceneDetailColumn()
        qtbot.addWidget(sdc)
        sdc.load_scene({"scene_number": "1", "int_ext": "INT",
                        "location": "X", "day_night": "GIORNO", "synopsis": ""},
                       [])
        sdc.clear()
        assert not sdc._placeholder.isHidden()


class TestElementsPanel:
    def test_init(self, qtbot):
        ep = ElementsPanel()
        qtbot.addWidget(ep)
        assert ep._count_label.text() == "0"

    def test_load_elements(self, qtbot):
        ep = ElementsPanel()
        qtbot.addWidget(ep)
        elements = [
            {"category": "Cast", "element_name": "Marco",
             "ai_confidence": 0.9, "user_verified": 1, "ai_suggested": 1},
            {"category": "Props", "element_name": "Coltello",
             "ai_confidence": 0.7, "user_verified": 0, "ai_suggested": 1},
        ]
        ep.load_elements(elements)
        assert ep._count_label.text() == "2"
        assert len(ep._category_widgets) == 2

    def test_clear(self, qtbot):
        ep = ElementsPanel()
        qtbot.addWidget(ep)
        ep.load_elements([{"category": "Cast", "element_name": "X",
                          "ai_confidence": None, "user_verified": 0,
                          "ai_suggested": 0}])
        ep.clear()
        assert ep._count_label.text() == "0"
        assert len(ep._category_widgets) == 0


class TestBreakdownView:
    def test_init(self, qtbot):
        bv = BreakdownView(_make_container())
        qtbot.addWidget(bv)
        assert bv._project_id is None
        assert bv._scene_list is not None
        assert bv._scene_detail is not None
        assert bv._elements_panel is not None

    def test_clear(self, qtbot):
        bv = BreakdownView(_make_container())
        qtbot.addWidget(bv)
        bv.clear()
        assert bv._project_id is None


# ── Script Viewer tests ───────────────────────────────────────────────────────

class TestCategorySidebar:
    def test_init(self, qtbot):
        cs = CategorySidebar()
        qtbot.addWidget(cs)
        assert cs.minimumWidth() == 220

    def test_load_categories(self, qtbot):
        cs = CategorySidebar()
        qtbot.addWidget(cs)
        cs.load_categories([("Cast", 3), ("Props", 2)], 5, 5)
        assert len(cs._buttons) > 0


class TestScriptContentView:
    def test_init(self, qtbot):
        sv = ScriptContentView()
        qtbot.addWidget(sv)
        assert len(sv._scene_widgets) == 0

    def test_clear(self, qtbot):
        sv = ScriptContentView()
        qtbot.addWidget(sv)
        sv.clear()
        assert len(sv._scene_widgets) == 0


class TestScriptViewerView:
    def test_init(self, qtbot):
        sv = ScriptViewerView(_make_container())
        qtbot.addWidget(sv)
        assert sv._project_id is None

    def test_clear(self, qtbot):
        sv = ScriptViewerView(_make_container())
        qtbot.addWidget(sv)
        sv.clear()
        assert sv._project_id is None
        assert sv._all_data == []


# ── Stripboard tests ──────────────────────────────────────────────────────────

class TestSceneStripRow:
    def test_init(self, qtbot):
        scene = {"id": 1, "scene_number": "1", "location": "CUCINA",
                 "int_ext": "INT", "day_night": "GIORNO", "is_locked": 0,
                 "requires_intimacy_coordinator": 0,
                 "page_start_whole": 0, "page_start_eighths": 0,
                 "page_end_whole": 0, "page_end_eighths": 0}
        row = SceneStripRow(scene)
        qtbot.addWidget(row)
        assert row._scene_id == 1
        assert row.height() == 44

    def test_compact(self, qtbot):
        scene = {"id": 1, "scene_number": "1", "location": "A",
                 "int_ext": "INT", "day_night": "GIORNO", "is_locked": 0,
                 "requires_intimacy_coordinator": 0,
                 "page_start_whole": 0, "page_start_eighths": 0,
                 "page_end_whole": 0, "page_end_eighths": 0}
        row = SceneStripRow(scene, compact=True)
        qtbot.addWidget(row)
        assert row.height() == 26


class TestDayBreakHeader:
    def test_init(self, qtbot):
        hdr = DayBreakHeader(1, 3, "2 1/8", 5.5, ["CUCINA", "STRADA"])
        qtbot.addWidget(hdr)
        assert hdr.height() == 32


class TestStripboardView:
    def test_init(self, qtbot):
        sv = StripboardView(_make_container())
        qtbot.addWidget(sv)
        assert sv._project_id is None
        assert not sv._compact

    def test_clear(self, qtbot):
        sv = StripboardView(_make_container())
        qtbot.addWidget(sv)
        sv.clear()
        assert sv._project_id is None


# ── Budget tests ──────────────────────────────────────────────────────────────

class TestAccountListPanel:
    def test_init(self, qtbot):
        ap = AccountListPanel()
        qtbot.addWidget(ap)
        assert ap._count_label.text() == "0"

    def test_load_accounts(self, qtbot):
        ap = AccountListPanel()
        qtbot.addWidget(ap)
        accounts = [
            {"id": 1, "code": "1000", "name": "Attori", "subtotal": 5000},
            {"id": 2, "code": "2000", "name": "Troupe", "subtotal": 3000},
        ]
        ap.load_accounts(accounts)
        assert ap._count_label.text() == "2"
        assert len(ap._account_rows) == 2


class TestAccountDetailPanel:
    def test_init_placeholder(self, qtbot):
        adp = AccountDetailPanel()
        qtbot.addWidget(adp)
        assert not adp._placeholder.isHidden()
        assert adp._table.isHidden()

    def test_clear(self, qtbot):
        adp = AccountDetailPanel()
        qtbot.addWidget(adp)
        adp.clear()
        assert not adp._placeholder.isHidden()


class TestBudgetView:
    def test_init(self, qtbot):
        bv = BudgetView(_make_container())
        qtbot.addWidget(bv)
        assert bv._project_id is None

    def test_clear(self, qtbot):
        bv = BudgetView(_make_container())
        qtbot.addWidget(bv)
        bv.clear()
        assert bv._project_id is None


# ── One-Liner tests ───────────────────────────────────────────────────────────

class TestOneLinerView:
    def test_init(self, qtbot):
        ov = OneLinerView(_make_container())
        qtbot.addWidget(ov)
        assert ov._table.columnCount() == 9
        assert ov._project_id is None

    def test_clear(self, qtbot):
        ov = OneLinerView(_make_container())
        qtbot.addWidget(ov)
        ov.clear()
        assert ov._project_id is None
        assert ov._table.rowCount() == 0


# ── DOOD tests ────────────────────────────────────────────────────────────────

class TestDayOutOfDaysView:
    def test_init(self, qtbot):
        dv = DayOutOfDaysView(_make_container())
        qtbot.addWidget(dv)
        assert dv._project_id is None

    def test_clear(self, qtbot):
        dv = DayOutOfDaysView(_make_container())
        qtbot.addWidget(dv)
        dv.clear()
        assert dv._project_id is None
        assert dv._table.rowCount() == 0


# ── Settings Dialog tests ─────────────────────────────────────────────────────

class TestSettingsDialog:
    def test_init(self, qtbot):
        sd = SettingsDialog(_make_container())
        qtbot.addWidget(sd)
        assert sd.windowTitle() == "Impostazioni"
        assert sd.minimumWidth() == 540

    def test_init_with_project(self, qtbot):
        project_data = {
            "language": "English",
            "currency": "USD",
            "hours_per_shooting_day": 12.0,
            "contingency_percent": 15.0,
            "ml_enabled": 1,
            "ml_min_confidence": 0.75,
        }
        sd = SettingsDialog(_make_container(), project_data)
        qtbot.addWidget(sd)
        assert sd._hours_spin.value() == 12.0
        assert sd._contingency_spin.value() == 15.0
        assert sd._ml_enabled.isChecked()
        assert sd._confidence_slider.value() == 75

    def test_get_settings(self, qtbot):
        sd = SettingsDialog(_make_container())
        qtbot.addWidget(sd)
        settings = sd.get_settings()
        assert "language" in settings
        assert "currency" in settings
        assert "ml_enabled" in settings
        assert "ml_min_confidence" in settings
        assert isinstance(settings["ml_min_confidence"], float)

    def test_confidence_slider_updates_label(self, qtbot):
        sd = SettingsDialog(_make_container())
        qtbot.addWidget(sd)
        sd._confidence_slider.setValue(80)
        assert sd._confidence_label.text() == "80%"


# ── ✅ Feature 1.5: SearchResultsDialog tests ─────────────────────────────────

class TestSearchResultsDialog:

    def test_no_crash_without_fts5(self, qtbot):
        """Non crasha se FTS5 non è disponibile (DB non ancora a V18)."""
        db = _make_search_db(raise_exc=True)
        dlg = SearchResultsDialog(db, project_id=1, query="pistola")
        qtbot.addWidget(dlg)
        assert dlg._table.rowCount() == 0
        assert "0" in dlg._count_label.text()

    def test_shows_results(self, qtbot):
        """Popola la tabella con i risultati restituiti da FTS5."""
        rows = [
            ("scene",   1, "1 INT CASA GIORNO - Marco entra con una pistola"),
            ("element", 5, "pistola Props"),
            ("element", 9, "pistola Props"),
        ]
        db = _make_search_db(rows=rows)
        dlg = SearchResultsDialog(db, project_id=1, query="pistola")
        qtbot.addWidget(dlg)
        assert dlg._table.rowCount() == 3
        assert "3" in dlg._count_label.text()

    def test_singular_count_label(self, qtbot):
        """Con 1 risultato usa 'risultato' (non 'risultati')."""
        rows = [("scene", 1, "1 EXT PIAZZA - Rissa")]
        db = _make_search_db(rows=rows)
        dlg = SearchResultsDialog(db, project_id=1, query="rissa")
        qtbot.addWidget(dlg)
        assert "1 risultato" in dlg._count_label.text()

    def test_zero_results(self, qtbot):
        """Zero risultati: tabella vuota, label mostra '0 risultati'."""
        db = _make_search_db(rows=[])
        dlg = SearchResultsDialog(db, project_id=1, query="inesistente")
        qtbot.addWidget(dlg)
        assert dlg._table.rowCount() == 0
        assert "0" in dlg._count_label.text()

    def test_result_selected_signal(self, qtbot):
        """
        Doppio click su una riga emette result_selected(content_type, content_id).
        """
        rows = [("scene", 42, "1 EXT PIAZZA - Inseguimento")]
        db = _make_search_db(rows=rows)
        dlg = SearchResultsDialog(db, project_id=1, query="inseguimento")
        qtbot.addWidget(dlg)

        received = []
        dlg.result_selected.connect(lambda t, i: received.append((t, i)))

        dlg._table.doubleClicked.emit(
            dlg._table.model().index(0, 0)
        )
        assert received == [("scene", 42)]

    def test_type_labels_shown(self, qtbot):
        """Le etichette tipo mostrano le emoji corrette."""
        rows = [
            ("scene",   1, "Scena test"),
            ("element", 2, "Elemento test"),
        ]
        db = _make_search_db(rows=rows)
        dlg = SearchResultsDialog(db, project_id=1, query="test")
        qtbot.addWidget(dlg)
        item_scene   = dlg._table.item(0, 0)
        item_element = dlg._table.item(1, 0)
        assert "Scena"    in item_scene.text()
        assert "Elemento" in item_element.text()

    def test_text_truncated_to_120_chars(self, qtbot):
        """Il testo visualizzato non supera 120 caratteri."""
        long_text = "x" * 200
        rows = [("scene", 1, long_text)]
        db = _make_search_db(rows=rows)
        dlg = SearchResultsDialog(db, project_id=1, query="x")
        qtbot.addWidget(dlg)
        displayed = dlg._table.item(0, 1).text()
        assert len(displayed) <= 120

    def test_id_stored_in_userdata(self, qtbot):
        """
        L'id viene salvato in UserRole dell'item della colonna ID,
        in modo che _on_double_click possa recuperarlo senza fare
        int(item.text()) su testo potenzialmente formattato.
        """
        rows = [("element", 99, "Coltello Props")]
        db = _make_search_db(rows=rows)
        dlg = SearchResultsDialog(db, project_id=1, query="coltello")
        qtbot.addWidget(dlg)
        id_item = dlg._table.item(0, 2)
        data = id_item.data(Qt.ItemDataRole.UserRole)
        assert data == ("element", 99)

    def test_window_title_contains_query(self, qtbot):
        """Il titolo del dialog include la query di ricerca."""
        db = _make_search_db(rows=[])
        dlg = SearchResultsDialog(db, project_id=1, query="elicottero")
        qtbot.addWidget(dlg)
        assert "elicottero" in dlg.windowTitle()