import os
import sqlite3
import tempfile

import pytest

from gliamispo.export.call_sheet_pdf import CallSheetGenerator
from gliamispo.import_.swift_db_importer import SwiftDbImporter

SCHEMA_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "src", "gliamispo", "database", "schema.sql"
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_python_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())
    conn.execute("PRAGMA user_version = 10")
    conn.commit()
    return conn


def _make_swift_pre_v6_file(scenes=None, elements=None):
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            director TEXT
        );
        CREATE TABLE scenes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            scene_number TEXT,
            location TEXT,
            int_ext TEXT NOT NULL DEFAULT 'INT',
            day_night TEXT NOT NULL DEFAULT 'GIORNO',
            page_start REAL DEFAULT 1.0,
            page_end REAL DEFAULT 2.0,
            synopsis TEXT,
            story_day INTEGER DEFAULT 1,
            requires_intimacy_coordinator INTEGER DEFAULT 0,
            estimated_crew_size INTEGER,
            special_requirements TEXT,
            created_at INTEGER DEFAULT (strftime('%s','now'))
        );
        CREATE TABLE scene_elements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scene_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            element_name TEXT NOT NULL,
            quantity INTEGER DEFAULT 1,
            notes TEXT,
            ai_suggested INTEGER DEFAULT 0,
            ai_confidence REAL,
            user_verified INTEGER DEFAULT 0
        );
    """)
    conn.execute("INSERT INTO projects (title) VALUES ('Film di Test')")
    if scenes is not None:
        for s in scenes:
            conn.execute(
                "INSERT INTO scenes"
                " (project_id, int_ext, day_night, page_start, page_end,"
                " synopsis, estimated_crew_size, special_requirements)"
                " VALUES (1,?,?,?,?,?,?,?)",
                s,
            )
    if elements is not None:
        for e in elements:
            conn.execute(
                "INSERT INTO scene_elements"
                " (scene_id, category, element_name, quantity)"
                " VALUES (?,?,?,?)",
                e,
            )
    conn.commit()
    conn.close()
    return path


def _make_swift_post_v6_buggy_file():
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL
        );
        CREATE TABLE scenes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            scene_number TEXT,
            location TEXT,
            int_ext TEXT NOT NULL DEFAULT 'INT',
            day_night TEXT NOT NULL DEFAULT 'GIORNO',
            page_start_whole INTEGER NOT NULL DEFAULT 1,
            page_start_eighths INTEGER NOT NULL DEFAULT 0,
            page_end_whole INTEGER NOT NULL DEFAULT 2,
            page_end_eighths INTEGER NOT NULL DEFAULT 0,
            synopsis TEXT,
            story_day INTEGER DEFAULT 1,
            requires_intimacy_coordinator INTEGER DEFAULT 0,
            created_at INTEGER DEFAULT (strftime('%s','now'))
        );
        CREATE TABLE scenes_backup_v5 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            int_ext TEXT NOT NULL DEFAULT 'INT',
            day_night TEXT NOT NULL DEFAULT 'GIORNO',
            page_start REAL DEFAULT 1.0,
            page_end REAL DEFAULT 2.0,
            synopsis TEXT,
            story_day INTEGER DEFAULT 1,
            estimated_crew_size INTEGER,
            special_requirements TEXT,
            created_at INTEGER DEFAULT (strftime('%s','now'))
        );
        CREATE TABLE scene_elements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scene_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            element_name TEXT NOT NULL,
            quantity INTEGER DEFAULT 1,
            notes TEXT,
            ai_suggested INTEGER DEFAULT 0,
            ai_confidence REAL,
            user_verified INTEGER DEFAULT 0
        );
    """)
    conn.execute("INSERT INTO projects (title) VALUES ('Film Buggy')")
    conn.execute(
        "INSERT INTO scenes"
        " (project_id, int_ext, day_night, page_start_whole, page_end_whole)"
        " VALUES (1,'INT','GIORNO',1,2)"
    )
    conn.execute(
        "INSERT INTO scenes_backup_v5"
        " (project_id, int_ext, day_night,"
        " estimated_crew_size, special_requirements)"
        " VALUES (1,'INT','GIORNO',50,'Requires cranes')"
    )
    conn.execute(
        "INSERT INTO scene_elements (scene_id, category, element_name)"
        " VALUES (1,'Cast','MARIO')"
    )
    conn.commit()
    conn.close()
    return path


# ---------------------------------------------------------------------------
# CallSheetGenerator tests
# ---------------------------------------------------------------------------


class TestCallSheetGenerator:
    def _setup_call_sheet(self, db):
        db.execute("INSERT INTO projects (title) VALUES ('P')")
        db.commit()
        pid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute(
            "INSERT INTO shooting_schedules (project_id, schedule_name)"
            " VALUES (?, 'Schedule A')",
            (pid,),
        )
        db.commit()
        sched_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute(
            "INSERT INTO shooting_days"
            " (schedule_id, day_number, shoot_date, location_primary)"
            " VALUES (?,1,'2025-07-01','Studio A')",
            (sched_id,),
        )
        db.commit()
        day_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute(
            "INSERT INTO call_sheets"
            " (shooting_day_id, crew_call, weather_forecast, general_notes)"
            " VALUES (?,'07:30','Sunny','Silenzio sul set')",
            (day_id,),
        )
        db.commit()
        cs_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute(
            "INSERT INTO call_sheet_cast"
            " (call_sheet_id, actor_name, character_name, call_time)"
            " VALUES (?,'Anna Rossi','Maria','07:00')",
            (cs_id,),
        )
        db.execute(
            "INSERT INTO call_sheet_crew"
            " (call_sheet_id, crew_member_name, department, call_time)"
            " VALUES (?,'Luca Neri','Fotografia','06:30')",
            (cs_id,),
        )
        db.commit()
        return cs_id

    def test_generate_creates_file(self, tmp_path):
        db = _make_python_db()
        cs_id = self._setup_call_sheet(db)
        out = str(tmp_path / "sheet.txt")
        gen = CallSheetGenerator()
        result = gen.generate(db, cs_id, out)
        assert result is True
        assert os.path.exists(out)
        db.close()

    def test_generate_content(self, tmp_path):
        db = _make_python_db()
        cs_id = self._setup_call_sheet(db)
        out = str(tmp_path / "sheet.txt")
        gen = CallSheetGenerator()
        gen.generate(db, cs_id, out)
        content = open(out, encoding="utf-8").read()
        assert "FOGLIO DI LAVORAZIONE" in content
        assert "Anna Rossi" in content
        assert "Luca Neri" in content
        assert "07:30" in content
        assert "Fotografia" in content
        db.close()

    def test_generate_to_bytes(self):
        db = _make_python_db()
        cs_id = self._setup_call_sheet(db)
        gen = CallSheetGenerator()
        data = gen.generate_to_bytes(db, cs_id)
        assert isinstance(data, bytes)
        assert len(data) > 0
        assert b"FOGLIO DI LAVORAZIONE" in data
        db.close()

    def test_generate_missing_id_returns_false(self, tmp_path):
        db = _make_python_db()
        gen = CallSheetGenerator()
        result = gen.generate(db, 9999, str(tmp_path / "x.txt"))
        assert result is False
        db.close()

    def test_generate_to_bytes_missing_id_returns_empty(self):
        db = _make_python_db()
        gen = CallSheetGenerator()
        data = gen.generate_to_bytes(db, 9999)
        assert data == b""
        db.close()

    def test_generate_no_cast_no_crew(self, tmp_path):
        db = _make_python_db()
        db.execute("INSERT INTO projects (title) VALUES ('P')")
        db.commit()
        pid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute(
            "INSERT INTO shooting_schedules (project_id, schedule_name)"
            " VALUES (?, 'S')",
            (pid,),
        )
        db.commit()
        sched_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute(
            "INSERT INTO shooting_days (schedule_id, day_number) VALUES (?,1)",
            (sched_id,),
        )
        db.commit()
        day_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute(
            "INSERT INTO call_sheets (shooting_day_id) VALUES (?)", (day_id,)
        )
        db.commit()
        cs_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        out = str(tmp_path / "empty.txt")
        gen = CallSheetGenerator()
        gen.generate(db, cs_id, out)
        content = open(out, encoding="utf-8").read()
        assert "Nessun cast" in content
        assert "Nessuna troupe" in content
        db.close()


# ---------------------------------------------------------------------------
# SwiftDbImporter — schema detection
# ---------------------------------------------------------------------------


class TestSwiftDbImporterDetection:
    def test_detect_pre_v6(self):
        path = _make_swift_pre_v6_file(
            scenes=[("INT", "GIORNO", 1.0, 2.0, None, None, None)]
        )
        try:
            src = sqlite3.connect(path)
            src.row_factory = sqlite3.Row
            imp = SwiftDbImporter()
            assert imp._detect_schema(src) == "pre_v6"
            src.close()
        finally:
            os.unlink(path)

    def test_detect_post_v6_buggy(self):
        path = _make_swift_post_v6_buggy_file()
        try:
            src = sqlite3.connect(path)
            src.row_factory = sqlite3.Row
            imp = SwiftDbImporter()
            assert imp._detect_schema(src) == "post_v6_buggy"
            src.close()
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# SwiftDbImporter — pre-V6 import
# ---------------------------------------------------------------------------


class TestSwiftImportPreV6:
    def test_basic_import(self):
        path = _make_swift_pre_v6_file(
            scenes=[("INT", "GIORNO", 1.0, 2.0, "Desc", None, None)],
            elements=[(1, "Cast", "MARIO", 1)],
        )
        target = _make_python_db()
        try:
            imp = SwiftDbImporter()
            stats = imp.import_db(path, target)
            assert stats["schema_type"] == "pre_v6"
            assert stats["projects"] == 1
            assert stats["scenes"] == 1
            assert stats["elements"] == 1
        finally:
            os.unlink(path)
            target.close()

    def test_eighths_conversion(self):
        # page_start=1.5 → whole=1, eighths=4
        # page_end=2.375 → whole=2, eighths=3
        path = _make_swift_pre_v6_file(
            scenes=[("INT", "GIORNO", 1.5, 2.375, None, None, None)],
        )
        target = _make_python_db()
        try:
            SwiftDbImporter().import_db(path, target)
            row = target.execute(
                "SELECT page_start_whole, page_start_eighths,"
                " page_end_whole, page_end_eighths FROM scenes"
            ).fetchone()
            assert row["page_start_whole"] == 1
            assert row["page_start_eighths"] == 4
            assert row["page_end_whole"] == 2
            assert row["page_end_eighths"] == 3
        finally:
            os.unlink(path)
            target.close()

    def test_deduplication_keeps_highest_id(self):
        # Due righe con stessa (scene_id, category, element_name) ma quantity diversa
        # Deve essere mantenuta quella con id più alto (quantity=2)
        path = _make_swift_pre_v6_file(
            scenes=[("INT", "GIORNO", 1.0, 2.0, None, None, None)],
            elements=[
                (1, "Cast", "MARIO", 1),  # id=1, quantity=1
                (1, "Cast", "MARIO", 2),  # id=2, quantity=2 ← MAX(id) = kept
                (1, "Props", "pistola", 1),  # id=3, non duplicato
            ],
        )
        target = _make_python_db()
        try:
            stats = SwiftDbImporter().import_db(path, target)
            assert stats["elements"] == 2  # MARIO (dedup) + pistola
            mario = target.execute(
                "SELECT quantity FROM scene_elements WHERE element_name='MARIO'"
            ).fetchone()
            assert mario is not None
            assert mario["quantity"] == 2
        finally:
            os.unlink(path)
            target.close()

    def test_deduplication_across_scenes(self):
        # Stessa terna (category, element_name) in scene diverse: NON deduplicate
        path = _make_swift_pre_v6_file(
            scenes=[
                ("INT", "GIORNO", 1.0, 2.0, None, None, None),
                ("EXT", "NOTTE", 2.0, 3.0, None, None, None),
            ],
            elements=[
                (1, "Cast", "MARIO", 1),  # scene 1
                (2, "Cast", "MARIO", 1),  # scene 2 — stessa terna ma scene diversa
            ],
        )
        target = _make_python_db()
        try:
            stats = SwiftDbImporter().import_db(path, target)
            assert stats["elements"] == 2
        finally:
            os.unlink(path)
            target.close()

    def test_preserves_estimated_crew_size(self):
        path = _make_swift_pre_v6_file(
            scenes=[("INT", "GIORNO", 1.0, 2.0, None, 30, "Grù")],
        )
        target = _make_python_db()
        try:
            SwiftDbImporter().import_db(path, target)
            row = target.execute(
                "SELECT estimated_crew_size, special_requirements FROM scenes"
            ).fetchone()
            assert row["estimated_crew_size"] == 30
            assert row["special_requirements"] == "Grù"
        finally:
            os.unlink(path)
            target.close()

    def test_invalid_category_skipped(self):
        path = _make_swift_pre_v6_file(
            scenes=[("INT", "GIORNO", 1.0, 2.0, None, None, None)],
            elements=[
                (1, "Cast", "MARIO", 1),
                (1, "InvalidCategory", "x", 1),  # deve essere saltato
            ],
        )
        target = _make_python_db()
        try:
            stats = SwiftDbImporter().import_db(path, target)
            assert stats["elements"] == 1  # solo MARIO inserito
        finally:
            os.unlink(path)
            target.close()


# ---------------------------------------------------------------------------
# SwiftDbImporter — post-V6 buggy import con recovery
# ---------------------------------------------------------------------------


class TestSwiftImportPostV6Buggy:
    def test_recovery_from_backup(self):
        path = _make_swift_post_v6_buggy_file()
        target = _make_python_db()
        try:
            stats = SwiftDbImporter().import_db(path, target)
            assert stats["schema_type"] == "post_v6_buggy"
            assert stats["scenes"] == 1
            row = target.execute(
                "SELECT estimated_crew_size, special_requirements FROM scenes"
            ).fetchone()
            assert row["estimated_crew_size"] == 50
            assert row["special_requirements"] == "Requires cranes"
        finally:
            os.unlink(path)
            target.close()

    def test_elements_imported(self):
        path = _make_swift_post_v6_buggy_file()
        target = _make_python_db()
        try:
            stats = SwiftDbImporter().import_db(path, target)
            assert stats["elements"] == 1
            row = target.execute(
                "SELECT element_name FROM scene_elements"
            ).fetchone()
            assert row["element_name"] == "MARIO"
        finally:
            os.unlink(path)
            target.close()

    def test_project_imported(self):
        path = _make_swift_post_v6_buggy_file()
        target = _make_python_db()
        try:
            stats = SwiftDbImporter().import_db(path, target)
            assert stats["projects"] == 1
            row = target.execute("SELECT title FROM projects").fetchone()
            assert row["title"] == "Film Buggy"
        finally:
            os.unlink(path)
            target.close()


# ---------------------------------------------------------------------------
# Full breakdown pipeline (integrazione asincrona)
# ---------------------------------------------------------------------------

FOUNTAIN_SCRIPT = """\
INT. CUCINA - GIORNO

MARIO
Buongiorno, LUCIA.

LUCIA
Ciao, MARIO!

EXT. STRADA - NOTTE

MARIO
Non vado da solo.
"""


class TestFullBreakdownPipeline:
    async def test_scenes_inserted(self, tmp_path):
        from gliamispo.breakdown.orchestrator import BreakdownOrchestrator
        from gliamispo.ml.feedback_loop import FeedbackLoopService
        from gliamispo.ml.inference import DummyInference
        from gliamispo.nlp.context_engine import ContextEngine
        from gliamispo.nlp.ner_extractor import NERExtractor
        from gliamispo.nlp.pattern_matcher import DynamicPatternMatcher
        from gliamispo.nlp.pipeline import NLPPipelineCoordinator
        from gliamispo.nlp.term_normalizer import TermNormalizer
        from gliamispo.nlp.vocabulary_manager import VocabularyManager
        from gliamispo.parsing.fountain_parser import FountainParser

        script = tmp_path / "test.fountain"
        script.write_text(FOUNTAIN_SCRIPT, encoding="utf-8")

        db = _make_python_db()
        db.execute("INSERT INTO projects (title) VALUES ('Test Film')")
        db.commit()
        project_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        nlp = NLPPipelineCoordinator(
            ner=NERExtractor(),
            vocabulary=VocabularyManager([("pistola", "Props")]),
            pattern_matcher=DynamicPatternMatcher([]),
            context_engine=ContextEngine(),
            normalizer=TermNormalizer(),
        )
        orch = BreakdownOrchestrator(
            parser=FountainParser(),
            nlp_pipeline=nlp,
            database=db,
            feedback_loop=FeedbackLoopService(db),
            ml_inference=DummyInference(),
        )

        await orch.run_breakdown(str(script), project_id)
        db.commit()

        scene_count = db.execute("SELECT COUNT(*) FROM scenes").fetchone()[0]
        assert scene_count == 2

        db.close()

    async def test_elements_inserted(self, tmp_path):
        from gliamispo.breakdown.orchestrator import BreakdownOrchestrator
        from gliamispo.ml.feedback_loop import FeedbackLoopService
        from gliamispo.ml.inference import DummyInference
        from gliamispo.nlp.context_engine import ContextEngine
        from gliamispo.nlp.ner_extractor import NERExtractor
        from gliamispo.nlp.pattern_matcher import DynamicPatternMatcher
        from gliamispo.nlp.pipeline import NLPPipelineCoordinator
        from gliamispo.nlp.term_normalizer import TermNormalizer
        from gliamispo.nlp.vocabulary_manager import VocabularyManager
        from gliamispo.parsing.fountain_parser import FountainParser

        script = tmp_path / "test.fountain"
        script.write_text(FOUNTAIN_SCRIPT, encoding="utf-8")

        db = _make_python_db()
        db.execute("INSERT INTO projects (title) VALUES ('Test Film')")
        db.commit()
        project_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        nlp = NLPPipelineCoordinator(
            ner=NERExtractor(),
            vocabulary=VocabularyManager([]),
            pattern_matcher=DynamicPatternMatcher([]),
            context_engine=ContextEngine(),
            normalizer=TermNormalizer(),
        )
        orch = BreakdownOrchestrator(
            parser=FountainParser(),
            nlp_pipeline=nlp,
            database=db,
            feedback_loop=FeedbackLoopService(db),
            ml_inference=DummyInference(),
        )

        await orch.run_breakdown(str(script), project_id)
        db.commit()

        # Almeno MARIO e LUCIA devono essere nei Cast (dalla lista characters)
        cast = db.execute(
            "SELECT element_name FROM scene_elements WHERE category='Cast'"
        ).fetchall()
        names = {r["element_name"] for r in cast}
        assert "Mario" in names
        assert "Lucia" in names

        db.close()

    async def test_progress_callback(self, tmp_path):
        from gliamispo.breakdown.orchestrator import BreakdownOrchestrator
        from gliamispo.ml.feedback_loop import FeedbackLoopService
        from gliamispo.ml.inference import DummyInference
        from gliamispo.nlp.context_engine import ContextEngine
        from gliamispo.nlp.ner_extractor import NERExtractor
        from gliamispo.nlp.pattern_matcher import DynamicPatternMatcher
        from gliamispo.nlp.pipeline import NLPPipelineCoordinator
        from gliamispo.nlp.term_normalizer import TermNormalizer
        from gliamispo.nlp.vocabulary_manager import VocabularyManager
        from gliamispo.parsing.fountain_parser import FountainParser

        script = tmp_path / "test.fountain"
        script.write_text(FOUNTAIN_SCRIPT, encoding="utf-8")

        db = _make_python_db()
        db.execute("INSERT INTO projects (title) VALUES ('Test Film')")
        db.commit()
        project_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        nlp = NLPPipelineCoordinator(
            ner=NERExtractor(),
            vocabulary=VocabularyManager([]),
            pattern_matcher=DynamicPatternMatcher([]),
            context_engine=ContextEngine(),
            normalizer=TermNormalizer(),
        )
        orch = BreakdownOrchestrator(
            parser=FountainParser(),
            nlp_pipeline=nlp,
            database=db,
            feedback_loop=FeedbackLoopService(db),
            ml_inference=DummyInference(),
        )

        progress = []
        await orch.run_breakdown(
            str(script), project_id,
            on_progress=lambda p, m: progress.append(p)
        )

        assert len(progress) > 0
        assert progress[-1] == 1.0

        db.close()
