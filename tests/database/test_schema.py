import sqlite3
import os
import pytest


SCHEMA_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "src", "gliamispo", "database", "schema.sql"
)


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())
    yield conn
    conn.close()


EXPECTED_TABLES = [
    "projects", "scenes", "scene_elements", "user_corrections",
    "training_data", "vocabulary_terms", "ml_model_versions",
    "element_confidence_history", "multiword_entities",
    "ml_performance_metrics", "ai_patterns", "shooting_schedules",
    "shooting_days", "shooting_day_scenes", "intimacy_protocols",
    "budget_templates", "budget_template_accounts", "budget_accounts",
    "budget_details", "call_sheets", "call_sheet_cast", "call_sheet_crew",
    "dood_entries", "project_stats",
]


class TestTablesExist:
    @pytest.mark.parametrize("table", EXPECTED_TABLES)
    def test_table_exists(self, db, table):
        r = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,)
        ).fetchone()
        assert r is not None, f"Table {table} not found"


EXPECTED_TRIGGERS = [
    "update_project_timestamp",
    "validate_confidence",
    "validate_category_insert",
    "validate_category_update",
    "validate_page_range",
    "update_project_stats_insert",
    "update_project_stats_verify",
    "track_confidence_on_insert",
    "track_confidence_on_update",
]


class TestTriggersExist:
    @pytest.mark.parametrize("trigger", EXPECTED_TRIGGERS)
    def test_trigger_exists(self, db, trigger):
        r = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='trigger' AND name=?",
            (trigger,)
        ).fetchone()
        assert r is not None, f"Trigger {trigger} not found"


class TestProjectInsert:
    def test_insert_project(self, db):
        db.execute("INSERT INTO projects (title) VALUES ('Test Film')")
        db.commit()
        row = db.execute("SELECT * FROM projects WHERE title='Test Film'").fetchone()
        assert row is not None
        assert row["ml_enabled"] == 1
        assert row["contingency_percent"] == 10.0


class TestSceneConstraints:
    def _insert_project(self, db):
        db.execute("INSERT INTO projects (title) VALUES ('P')")
        db.commit()
        return db.execute("SELECT last_insert_rowid()").fetchone()[0]

    def test_valid_scene(self, db):
        pid = self._insert_project(db)
        db.execute(
            "INSERT INTO scenes (project_id, int_ext, day_night, "
            "page_start_whole, page_start_eighths, page_end_whole, page_end_eighths) "
            "VALUES (?, 'INT', 'GIORNO', 1, 0, 1, 3)",
            (pid,)
        )
        db.commit()
        row = db.execute("SELECT page_start_decimal, page_end_decimal FROM scenes").fetchone()
        assert row["page_start_decimal"] == 1.0
        assert row["page_end_decimal"] == 1.375

    def test_invalid_int_ext(self, db):
        pid = self._insert_project(db)
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO scenes (project_id, int_ext, day_night) "
                "VALUES (?, 'OUTDOOR', 'GIORNO')",
                (pid,)
            )

    def test_invalid_page_range_trigger(self, db):
        pid = self._insert_project(db)
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO scenes (project_id, int_ext, day_night, "
                "page_start_whole, page_start_eighths, page_end_whole, page_end_eighths) "
                "VALUES (?, 'INT', 'GIORNO', 2, 0, 1, 0)",
                (pid,)
            )

    def test_eighths_range_check(self, db):
        pid = self._insert_project(db)
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO scenes (project_id, int_ext, day_night, "
                "page_start_eighths) VALUES (?, 'INT', 'GIORNO', 9)",
                (pid,)
            )


class TestSceneElementConstraints:
    def _setup(self, db):
        db.execute("INSERT INTO projects (title) VALUES ('P')")
        db.commit()
        pid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute(
            "INSERT INTO scenes (project_id, int_ext, day_night) "
            "VALUES (?, 'INT', 'GIORNO')",
            (pid,)
        )
        db.commit()
        return db.execute("SELECT last_insert_rowid()").fetchone()[0]

    def test_valid_element(self, db):
        sid = self._setup(db)
        db.execute(
            "INSERT INTO scene_elements (scene_id, category, element_name) "
            "VALUES (?, 'Cast', 'Actor A')",
            (sid,)
        )
        db.commit()
        row = db.execute("SELECT * FROM scene_elements").fetchone()
        assert row["ai_model_version"] == "v0.0.0"

    def test_invalid_category_trigger(self, db):
        sid = self._setup(db)
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO scene_elements (scene_id, category, element_name) "
                "VALUES (?, 'InvalidCat', 'X')",
                (sid,)
            )

    def test_invalid_confidence_trigger(self, db):
        sid = self._setup(db)
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO scene_elements (scene_id, category, element_name, ai_confidence) "
                "VALUES (?, 'Cast', 'X', 1.5)",
                (sid,)
            )

    def test_duplicate_element(self, db):
        sid = self._setup(db)
        db.execute(
            "INSERT INTO scene_elements (scene_id, category, element_name) "
            "VALUES (?, 'Cast', 'Actor A')",
            (sid,)
        )
        db.commit()
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO scene_elements (scene_id, category, element_name) "
                "VALUES (?, 'Cast', 'Actor A')",
                (sid,)
            )

    def test_quantity_check(self, db):
        sid = self._setup(db)
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO scene_elements (scene_id, category, element_name, quantity) "
                "VALUES (?, 'Cast', 'X', 0)",
                (sid,)
            )


class TestProjectStatsTrigger:
    def test_stats_increment(self, db):
        db.execute("INSERT INTO projects (title) VALUES ('P')")
        db.commit()
        pid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute(
            "INSERT INTO scenes (project_id, int_ext, day_night) "
            "VALUES (?, 'INT', 'GIORNO')",
            (pid,)
        )
        db.commit()
        sid = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        db.execute(
            "INSERT INTO scene_elements (scene_id, category, element_name, ai_suggested) "
            "VALUES (?, 'Cast', 'A', 1)",
            (sid,)
        )
        db.commit()
        stats = db.execute(
            "SELECT * FROM project_stats WHERE project_id=?", (pid,)
        ).fetchone()
        assert stats["total_elements"] == 1
        assert stats["ml_detected_elements"] == 1

        db.execute(
            "INSERT INTO scene_elements (scene_id, category, element_name, ai_suggested) "
            "VALUES (?, 'Props', 'Sword', 0)",
            (sid,)
        )
        db.commit()
        stats = db.execute(
            "SELECT * FROM project_stats WHERE project_id=?", (pid,)
        ).fetchone()
        assert stats["total_elements"] == 2
        assert stats["ml_detected_elements"] == 1


class TestConfidenceHistoryTrigger:
    def test_insert_with_confidence(self, db):
        db.execute("INSERT INTO projects (title) VALUES ('P')")
        db.commit()
        pid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute(
            "INSERT INTO scenes (project_id, int_ext, day_night) "
            "VALUES (?, 'INT', 'GIORNO')",
            (pid,)
        )
        db.commit()
        sid = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        db.execute(
            "INSERT INTO scene_elements "
            "(scene_id, category, element_name, ai_confidence, ai_model_version) "
            "VALUES (?, 'Cast', 'A', 0.85, 'v1.0.0')",
            (sid,)
        )
        db.commit()
        hist = db.execute("SELECT * FROM element_confidence_history").fetchall()
        assert len(hist) == 1
        assert hist[0]["confidence_score"] == 0.85
        assert hist[0]["model_version"] == "v1.0.0"

    def test_no_history_without_confidence(self, db):
        db.execute("INSERT INTO projects (title) VALUES ('P')")
        db.commit()
        pid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute(
            "INSERT INTO scenes (project_id, int_ext, day_night) "
            "VALUES (?, 'INT', 'GIORNO')",
            (pid,)
        )
        db.commit()
        sid = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        db.execute(
            "INSERT INTO scene_elements (scene_id, category, element_name) "
            "VALUES (?, 'Cast', 'A')",
            (sid,)
        )
        db.commit()
        hist = db.execute("SELECT * FROM element_confidence_history").fetchall()
        assert len(hist) == 0


class TestCascadeDelete:
    def test_delete_project_cascades_scenes(self, db):
        db.execute("INSERT INTO projects (title) VALUES ('P')")
        db.commit()
        pid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute(
            "INSERT INTO scenes (project_id, int_ext, day_night) "
            "VALUES (?, 'INT', 'GIORNO')",
            (pid,)
        )
        db.commit()
        db.execute("DELETE FROM projects WHERE id=?", (pid,))
        db.commit()
        assert db.execute("SELECT COUNT(*) FROM scenes").fetchone()[0] == 0

    def test_delete_scene_cascades_elements(self, db):
        db.execute("INSERT INTO projects (title) VALUES ('P')")
        db.commit()
        pid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute(
            "INSERT INTO scenes (project_id, int_ext, day_night) "
            "VALUES (?, 'INT', 'GIORNO')",
            (pid,)
        )
        db.commit()
        sid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute(
            "INSERT INTO scene_elements (scene_id, category, element_name) "
            "VALUES (?, 'Cast', 'A')",
            (sid,)
        )
        db.commit()
        db.execute("DELETE FROM scenes WHERE id=?", (sid,))
        db.commit()
        assert db.execute("SELECT COUNT(*) FROM scene_elements").fetchone()[0] == 0
