import sys
import os
import sqlite3
from platformdirs import user_data_dir
from PyQt6.QtWidgets import QApplication
from gliamispo._frozen import resource_path
from gliamispo.services.container import ServiceContainer
from gliamispo.ui.main_window import MainWindow
from gliamispo.database.migrations import run_migrations, MIGRATIONS

DB_DIR = user_data_dir("Gliamispo", appauthor=False)
DB_PATH = os.path.join(DB_DIR, "gliamispo.sqlite")


def init_database():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    current = conn.execute("PRAGMA user_version").fetchone()[0]
    has_tables = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='projects'"
    ).fetchone()

    if current == 0 and not has_tables:
        schema_text = resource_path("gliamispo.database", "schema.sql").read_text(encoding="utf-8")
        conn.executescript(schema_text)
        max_version = max(MIGRATIONS.keys())
        conn.execute(f"PRAGMA user_version = {max_version}")
        conn.commit()
    else:
        run_migrations(conn)

    conn.close()


def main():
    init_database()
    app = QApplication(sys.argv)
    container = ServiceContainer(DB_PATH)
    container.ml_scheduler
    window = MainWindow(container)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
