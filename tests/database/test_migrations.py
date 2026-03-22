import sqlite3
import pytest
from gliamispo.database.migrations import run_migrations, MIGRATIONS, column_missing, table_exists


def _create_v1_db():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript("""
        CREATE TABLE projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            director TEXT,
            production_company TEXT,
            created_date INTEGER DEFAULT (strftime('%s','now')),
            last_modified INTEGER DEFAULT (strftime('%s','now')),
            language TEXT,
            currency TEXT
        );
        CREATE TABLE scenes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            scene_number TEXT,
            location TEXT,
            int_ext TEXT NOT NULL CHECK(int_ext IN ('INT','EXT','INT/EXT')),
            day_night TEXT NOT NULL CHECK(day_night IN ('GIORNO','NOTTE','ALBA','TRAMONTO','CONTINUO')),
            page_start REAL DEFAULT 1.0,
            page_end REAL DEFAULT 1.0,
            synopsis TEXT,
            story_day INTEGER DEFAULT 1,
            created_at INTEGER DEFAULT (strftime('%s','now')),
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
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
            user_verified INTEGER DEFAULT 0,
            FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE
        );
    """)
    conn.execute("PRAGMA user_version = 1")
    conn.commit()
    return conn


class TestMigrationsRegistered:
    def test_all_versions_registered(self):
        for v in range(2, 25):
            assert v in MIGRATIONS, f"V{v} not registered"


class TestHelpers:
    def test_column_missing_true(self):
        conn = _create_v1_db()
        assert column_missing(conn, "scenes", "requires_intimacy_coordinator")
        conn.close()

    def test_column_missing_false(self):
        conn = _create_v1_db()
        assert not column_missing(conn, "scenes", "scene_number")
        conn.close()

    def test_table_exists_true(self):
        conn = _create_v1_db()
        assert table_exists(conn, "projects")
        conn.close()

    def test_table_exists_false(self):
        conn = _create_v1_db()
        assert not table_exists(conn, "nonexistent_table")
        conn.close()


class TestV2:
    def test_adds_intimacy_column(self):
        conn = _create_v1_db()
        MIGRATIONS[2](conn)
        conn.commit()
        assert not column_missing(conn, "scenes", "requires_intimacy_coordinator")
        conn.close()


class TestV3:
    def test_creates_schedule_tables(self):
        conn = _create_v1_db()
        MIGRATIONS[2](conn)
        MIGRATIONS[3](conn)
        conn.commit()
        assert table_exists(conn, "shooting_schedules")
        assert table_exists(conn, "shooting_days")
        assert table_exists(conn, "shooting_day_scenes")
        assert not column_missing(conn, "scenes", "estimated_crew_size")
        conn.close()


class TestV4:
    def test_creates_budget_tables(self):
        conn = _create_v1_db()
        for v in range(2, 5):
            MIGRATIONS[v](conn)
        conn.commit()
        assert table_exists(conn, "intimacy_protocols")
        assert table_exists(conn, "budget_templates")
        assert not column_missing(conn, "projects", "total_budget")
        conn.close()


class TestV5:
    def test_creates_call_sheet_tables(self):
        conn = _create_v1_db()
        for v in range(2, 6):
            MIGRATIONS[v](conn)
        conn.commit()
        assert table_exists(conn, "call_sheets")
        assert table_exists(conn, "call_sheet_cast")
        assert table_exists(conn, "call_sheet_crew")
        conn.close()


class TestV6:
    def test_full_v6_migration_empty_db(self):
        conn = _create_v1_db()
        for v in range(2, 7):
            MIGRATIONS[v](conn)
        conn.commit()

        assert table_exists(conn, "ml_model_versions")
        assert table_exists(conn, "training_data")
        assert table_exists(conn, "vocabulary_terms")
        assert table_exists(conn, "project_stats")

        assert not column_missing(conn, "scenes", "page_start_whole")
        assert not column_missing(conn, "scenes", "page_end_eighths")

        baseline = conn.execute(
            "SELECT * FROM ml_model_versions WHERE is_baseline=1"
        ).fetchone()
        assert baseline is not None
        conn.close()

    def test_v6_with_data(self):
        conn = _create_v1_db()
        conn.execute("INSERT INTO projects (title) VALUES ('Test')")
        conn.commit()
        pid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO scenes (project_id, int_ext, day_night, page_start, page_end) "
            "VALUES (?, 'INT', 'GIORNO', 1.0, 1.375)",
            (pid,)
        )
        conn.commit()

        for v in range(2, 7):
            MIGRATIONS[v](conn)
        conn.commit()

        row = conn.execute("SELECT page_start_whole, page_start_eighths, "
                           "page_end_whole, page_end_eighths FROM scenes").fetchone()
        assert row[0] == 1
        assert row[1] == 0
        assert row[2] == 1
        assert row[3] == 3
        conn.close()


class TestV7ToV10:
    def test_v7_backfill(self):
        conn = _create_v1_db()
        for v in range(2, 8):
            MIGRATIONS[v](conn)
        conn.commit()
        assert not column_missing(conn, "scene_elements", "ai_model_version")
        conn.close()

    def test_v8_manual_hours(self):
        conn = _create_v1_db()
        for v in range(2, 9):
            MIGRATIONS[v](conn)
        conn.commit()
        assert not column_missing(conn, "scenes", "manual_shooting_hours")
        conn.close()

    def test_v9_project_hours(self):
        conn = _create_v1_db()
        for v in range(2, 10):
            MIGRATIONS[v](conn)
        conn.commit()
        assert not column_missing(conn, "projects", "hours_per_shooting_day")
        assert not column_missing(conn, "scenes", "is_locked")
        conn.close()

    def test_v10_corrections_rebuilt(self):
        conn = _create_v1_db()
        for v in range(2, 11):
            MIGRATIONS[v](conn)
        conn.commit()
        assert table_exists(conn, "user_corrections")
        conn.close()


class TestFullMigration:
    def test_run_migrations_from_v1(self):
        conn = _create_v1_db()
        run_migrations(conn)
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == 26  # aggiornato a 26 (Budget templates)
        conn.close()

    def test_idempotent(self):
        conn = _create_v1_db()
        run_migrations(conn)
        run_migrations(conn)
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == 26  # aggiornato a 26 (Budget templates)
        conn.close()


class TestV17:
    def test_creates_script_revisions_table(self):
        conn = _create_v1_db()
        run_migrations(conn)
        assert table_exists(conn, "script_revisions")
        conn.close()

    def test_creates_revision_scene_changes_table(self):
        conn = _create_v1_db()
        run_migrations(conn)
        assert table_exists(conn, "revision_scene_changes")
        conn.close()

    def test_adds_revision_id_to_scenes(self):
        conn = _create_v1_db()
        run_migrations(conn)
        assert not column_missing(conn, "scenes", "revision_id")
        conn.close()

    def test_adds_revision_badge_to_scenes(self):
        conn = _create_v1_db()
        run_migrations(conn)
        assert not column_missing(conn, "scenes", "revision_badge")
        conn.close()

    def test_v17_idempotent(self):
        """Eseguire V17 due volte non deve sollevare eccezioni."""
        conn = _create_v1_db()
        run_migrations(conn)
        MIGRATIONS[17](conn)  # seconda esecuzione: IF NOT EXISTS / column_missing lo proteggono
        conn.commit()
        assert table_exists(conn, "script_revisions")
        conn.close()


class TestV24:
    def test_creates_distribution_log_table(self):
        conn = _create_v1_db()
        run_migrations(conn)
        assert table_exists(conn, "distribution_log")
        conn.close()

    def test_v24_idempotent(self):
        """Eseguire V24 due volte non deve sollevare eccezioni."""
        conn = _create_v1_db()
        run_migrations(conn)
        MIGRATIONS[24](conn)  # seconda esecuzione
        conn.commit()
        assert table_exists(conn, "distribution_log")
        conn.close()