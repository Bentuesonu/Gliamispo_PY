import sqlite3
import threading
from contextlib import contextmanager
from gliamispo.models.project import Project


class DatabaseManager:
    def __init__(self, db_path):
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.row_factory = sqlite3.Row

    @contextmanager
    def _transaction(self):
        with self._lock:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def execute(self, sql, params=()):
        with self._lock:
            return self._conn.execute(sql, params)

    def commit(self):
        with self._lock:
            self._conn.commit()

    def execute_script(self, sql):
        with self._lock:
            self._conn.executescript(sql)

    def leggi_progetti(self):
        with self._lock:
            rows = self._conn.execute("SELECT * FROM projects").fetchall()
            return [Project(**dict(r)) for r in rows]

    @property
    def user_version(self):
        with self._lock:
            return self._conn.execute("PRAGMA user_version").fetchone()[0]

    @user_version.setter
    def user_version(self, v):
        # FIX: il setter originale non acquisiva il lock
        with self._lock:
            self._conn.execute(f"PRAGMA user_version = {int(v)}")
            self._conn.commit()

    def column_missing(self, table, column):
        with self._lock:
            cols = self._conn.execute(f"PRAGMA table_info({table})").fetchall()
            return column not in [c["name"] for c in cols]

    def table_exists(self, table):
        with self._lock:
            r = self._conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            ).fetchone()
            return r is not None

    def get_low_confidence_elements(
        self, project_id: int, threshold: float = 0.60
    ) -> list:
        """
        Restituisce gli elementi AI con confidenza sotto soglia
        non ancora verificati dall'utente.

        Usato dalla UI per evidenziare elementi che necessitano revisione
        e dall'MLAnalyticsService per misurare la qualità del modello.

        Args:
            project_id: ID del progetto corrente.
            threshold:  Soglia di confidenza (default 0.60, come ml_min_confidence).

        Returns:
            Lista di sqlite3.Row con campi:
            id, element_name, category, ai_confidence, scene_id, scene_number
        """
        with self._lock:
            return self._conn.execute(
                """
                SELECT
                    se.id,
                    se.element_name,
                    se.category,
                    se.ai_confidence,
                    se.scene_id,
                    s.scene_number
                FROM scene_elements se
                JOIN scenes s ON s.id = se.scene_id
                WHERE s.project_id    = ?
                  AND se.ai_confidence < ?
                  AND se.user_verified  = 0
                  AND se.ai_suggested   = 1
                ORDER BY se.ai_confidence ASC
                """,
                (project_id, threshold),
            ).fetchall()

    def close(self):
        self._conn.close()