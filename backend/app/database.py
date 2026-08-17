"""SQLite initialisation. Creates the database file and base tables."""

import sqlite3
from pathlib import Path

from .settings import settings


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    _ensure_dir(settings.data_dir)
    conn = sqlite3.connect(str(settings.database_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist. Phase 0 creates only the meta table."""
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS _meta (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "INSERT OR IGNORE INTO _meta (key, value) VALUES ('schema_version', '0')"
    )
    conn.commit()
    conn.close()
