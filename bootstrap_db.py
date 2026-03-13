#!/usr/bin/env python3
# bootstrap_db.py
import sqlite3
import os
import sys

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "database", "schema.sql")
DB_DIR = os.path.expanduser("~/Library/Application Support/Gliamispo")
DB_PATH = os.path.join(DB_DIR, "gliamispo.sqlite")


def bootstrap(db_path=None):
    path = db_path or DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)

    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())

    # Importa ed esegui migrazioni
    from database.migrations import run_migrations
    run_migrations(conn)

    conn.close()
    return path


if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else None
    result = bootstrap(p)
    print(f"Database inizializzato: {result}")
