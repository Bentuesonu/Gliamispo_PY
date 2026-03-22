"""Test per il modulo di backup del database."""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from gliamispo.database.backup import (
    BACKUP_PREFIX,
    BACKUP_SUFFIX,
    RETENTION_DAYS,
    run_daily_backup,
)


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """Crea un database SQLite temporaneo per i test."""
    db_path = tmp_path / "test.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO test (name) VALUES ('test_data')")
    conn.commit()
    conn.close()
    return db_path


class TestBackupCreation:
    """Test per la creazione del backup."""

    def test_backup_file_created(self, temp_db: Path, tmp_path: Path):
        """Verifica che il file di backup venga creato correttamente."""
        backup_dir = tmp_path / "backups"

        result = run_daily_backup(str(temp_db), str(backup_dir))

        assert result is not None
        assert result.exists()
        assert result.parent == backup_dir

        today_str = datetime.now().strftime("%Y%m%d")
        expected_name = f"{BACKUP_PREFIX}{today_str}{BACKUP_SUFFIX}"
        assert result.name == expected_name

    def test_backup_contains_data(self, temp_db: Path, tmp_path: Path):
        """Verifica che il backup contenga i dati del database originale."""
        backup_dir = tmp_path / "backups"

        result = run_daily_backup(str(temp_db), str(backup_dir))

        assert result is not None
        conn = sqlite3.connect(str(result))
        row = conn.execute("SELECT name FROM test WHERE id = 1").fetchone()
        conn.close()

        assert row is not None
        assert row[0] == "test_data"

    def test_default_backup_dir(self, temp_db: Path):
        """Verifica che la directory di default sia <db_dir>/backups/."""
        result = run_daily_backup(str(temp_db))

        assert result is not None
        assert result.parent == temp_db.parent / "backups"

    def test_creates_backup_dir_if_not_exists(self, temp_db: Path, tmp_path: Path):
        """Verifica che la directory di backup venga creata se non esiste."""
        backup_dir = tmp_path / "nested" / "backup" / "dir"
        assert not backup_dir.exists()

        result = run_daily_backup(str(temp_db), str(backup_dir))

        assert result is not None
        assert backup_dir.exists()


class TestNoOverwrite:
    """Test per verificare che non si sovrascriva un backup esistente."""

    def test_no_overwrite_same_day(self, temp_db: Path, tmp_path: Path):
        """Verifica che un secondo run nella stessa giornata non sovrascriva."""
        backup_dir = tmp_path / "backups"

        first_result = run_daily_backup(str(temp_db), str(backup_dir))
        assert first_result is not None

        first_mtime = first_result.stat().st_mtime

        conn = sqlite3.connect(str(temp_db))
        conn.execute("INSERT INTO test (name) VALUES ('new_data')")
        conn.commit()
        conn.close()

        second_result = run_daily_backup(str(temp_db), str(backup_dir))

        assert second_result is None
        assert first_result.stat().st_mtime == first_mtime

        conn = sqlite3.connect(str(first_result))
        rows = conn.execute("SELECT name FROM test").fetchall()
        conn.close()
        names = [r[0] for r in rows]
        assert "new_data" not in names


class TestCleanupOldBackups:
    """Test per la pulizia dei backup vecchi."""

    def test_cleanup_old_backups(self, temp_db: Path, tmp_path: Path):
        """Verifica la pulizia dei file più vecchi di 30 giorni."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir(parents=True)

        old_date = datetime.now() - timedelta(days=RETENTION_DAYS + 5)
        old_filename = f"{BACKUP_PREFIX}{old_date.strftime('%Y%m%d')}{BACKUP_SUFFIX}"
        old_backup = backup_dir / old_filename
        old_backup.write_bytes(b"old backup data")

        very_old_date = datetime.now() - timedelta(days=RETENTION_DAYS + 100)
        very_old_filename = f"{BACKUP_PREFIX}{very_old_date.strftime('%Y%m%d')}{BACKUP_SUFFIX}"
        very_old_backup = backup_dir / very_old_filename
        very_old_backup.write_bytes(b"very old backup data")

        recent_date = datetime.now() - timedelta(days=RETENTION_DAYS - 5)
        recent_filename = f"{BACKUP_PREFIX}{recent_date.strftime('%Y%m%d')}{BACKUP_SUFFIX}"
        recent_backup = backup_dir / recent_filename
        recent_backup.write_bytes(b"recent backup data")

        assert old_backup.exists()
        assert very_old_backup.exists()
        assert recent_backup.exists()

        result = run_daily_backup(str(temp_db), str(backup_dir))

        assert result is not None
        assert not old_backup.exists(), "Old backup should be deleted"
        assert not very_old_backup.exists(), "Very old backup should be deleted"
        assert recent_backup.exists(), "Recent backup should be kept"
        assert result.exists(), "Today's backup should exist"

    def test_cleanup_ignores_non_backup_files(self, temp_db: Path, tmp_path: Path):
        """Verifica che i file non di backup non vengano toccati."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir(parents=True)

        other_file = backup_dir / "other_file.txt"
        other_file.write_text("some content")

        old_date = datetime.now() - timedelta(days=RETENTION_DAYS + 10)
        fake_old = backup_dir / f"other_{old_date.strftime('%Y%m%d')}.sqlite"
        fake_old.write_bytes(b"fake")

        run_daily_backup(str(temp_db), str(backup_dir))

        assert other_file.exists()
        assert fake_old.exists()


class TestErrorHandling:
    """Test per la gestione degli errori."""

    def test_corrupted_db_returns_none(self, tmp_path: Path):
        """Verifica che un database corrotto restituisca None."""
        corrupted_db = tmp_path / "corrupted.sqlite"
        corrupted_db.write_text("this is not a valid sqlite database")
        backup_dir = tmp_path / "backups"

        result = run_daily_backup(str(corrupted_db), str(backup_dir))

        assert result is None

    def test_invalid_backup_dir_returns_none(self, temp_db: Path):
        """Verifica che una directory di backup non valida restituisca None."""
        result = run_daily_backup(str(temp_db), "/nonexistent/root/path/backups")

        assert result is None
