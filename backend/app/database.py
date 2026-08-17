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

        CREATE TABLE IF NOT EXISTS listings (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_type        TEXT NOT NULL DEFAULT 'job',  -- 'job' or 'gig'
            source              TEXT NOT NULL,
            source_id           TEXT NOT NULL,
            board_slug          TEXT NOT NULL,

            -- Display versions (as received)
            title_display       TEXT NOT NULL,
            company_display     TEXT NOT NULL,
            location_display    TEXT,

            -- Normalized versions (for matching)
            title_normalized    TEXT NOT NULL,
            company_normalized  TEXT NOT NULL,

            -- Content
            description         TEXT,
            url                 TEXT,
            posted_at           TEXT,
            department          TEXT,

            -- Remote detection
            is_remote           INTEGER NOT NULL DEFAULT 0,
            remote_confidence   REAL NOT NULL DEFAULT 0.0,

            -- Description quality: good, empty, title_only, non_english
            description_quality TEXT NOT NULL DEFAULT 'good',

            -- Dedupe
            canonical_id        INTEGER REFERENCES listings(id),
            dedupe_score        REAL,

            -- Scoring (Phase 3)
            score               REAL,
            score_breakdown     TEXT,  -- JSON per-dimension breakdown

            -- Status (Phase 6)
            status              TEXT NOT NULL DEFAULT 'new',

            created_at          TEXT NOT NULL,

            UNIQUE(source, source_id)
        );

        CREATE INDEX IF NOT EXISTS idx_listings_canonical ON listings(canonical_id);
        CREATE INDEX IF NOT EXISTS idx_listings_company_norm ON listings(company_normalized);
        CREATE INDEX IF NOT EXISTS idx_listings_type ON listings(listing_type);
        CREATE INDEX IF NOT EXISTS idx_listings_score ON listings(score);

        INSERT OR IGNORE INTO _meta (key, value) VALUES ('schema_version', '3');
        """
    )
    conn.commit()
    conn.close()
