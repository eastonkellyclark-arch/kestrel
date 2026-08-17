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
    """Create all tables if they don't exist."""
    conn = get_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS _meta (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS registry (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            company     TEXT NOT NULL,
            platform    TEXT NOT NULL,
            board_slug  TEXT NOT NULL,
            active      INTEGER NOT NULL DEFAULT 1,
            added_date  TEXT NOT NULL,
            UNIQUE(platform, board_slug)
        );

        CREATE TABLE IF NOT EXISTS raw_listings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            source      TEXT NOT NULL,
            board_slug  TEXT NOT NULL,
            source_id   TEXT NOT NULL,
            raw_json    TEXT NOT NULL,
            fetched_at  TEXT NOT NULL,
            UNIQUE(source, source_id)
        );

        INSERT OR IGNORE INTO _meta (key, value) VALUES ('schema_version', '1');
        """
    )
    conn.commit()
    conn.close()
