"""Schema migrations.

The pipeline used to run `rm -f data/kestrel.db` before every fetch because
"the schema may have changed since the last committed DB". That traded the
entire vault for the convenience of not writing migrations. This module is
the replacement: the database is migrated forward, never destroyed.

Rules:
  - The baseline schema (version 4) lives in database.py and is frozen.
    Never edit those CREATE TABLE statements again.
  - Every schema change from here on is a new entry in MIGRATIONS.
  - Migrations are applied in order, each in its own transaction, and the
    version is recorded only after the migration succeeds.
  - A database newer than the code is a hard error. Silently running old
    code against a new schema corrupts data quietly; refusing is loud.
"""

import logging
import sqlite3

from .database import get_connection

logger = logging.getLogger("kestrel.migrations")

BASELINE_VERSION = 4


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def _add_column(conn: sqlite3.Connection, table: str, column: str, decl: str) -> None:
    """ALTER TABLE ... ADD COLUMN, skipped if the column is already there.

    Makes migrations re-runnable: a half-applied migration that failed after
    its first statement can be retried instead of needing manual repair.
    """
    if column in _columns(conn, table):
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def _m5_staleness(conn: sqlite3.Connection) -> None:
    """Track when a listing was last seen at its source.

    Now that the database survives between runs, listings that disappear from
    their source would otherwise linger in the showroom forever. CLAUDE.md:
    "Never delete a listing. Mark it stale or closed."

    `status` is the apply-tracker's column and is not available for this —
    storing staleness there would destroy application history the first time
    a posting went quiet. These are separate columns on purpose.
    """
    _add_column(conn, "raw_listings", "last_seen_at", "TEXT")
    conn.execute("UPDATE raw_listings SET last_seen_at = fetched_at WHERE last_seen_at IS NULL")

    _add_column(conn, "listings", "is_stale", "INTEGER NOT NULL DEFAULT 0")
    _add_column(conn, "listings", "stale_since", "TEXT")

    # When the source last confirmed this listing still exists, copied from the
    # vault row at translate time. Kept on the listing so staleness is a plain
    # column comparison rather than a join back to raw_listings.
    _add_column(conn, "listings", "last_seen_at", "TEXT")

    # The vault's own source label for this listing. Needed because it does not
    # always equal listings.source: Reddit stores the vault row under 'reddit'
    # but the listing under the subreddit ('r/forhire'). Without this, Reddit
    # listings would silently fall outside every staleness check.
    _add_column(conn, "listings", "vault_source", "TEXT")

    conn.execute("CREATE INDEX IF NOT EXISTS idx_listings_stale ON listings(is_stale)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_listings_vault ON listings(vault_source, board_slug)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_raw_last_seen ON raw_listings(source, last_seen_at)"
    )


# (version, description, function). Applied in ascending order.
MIGRATIONS: list[tuple[int, str, object]] = [
    (5, "listing staleness tracking (last_seen_at, is_stale)", _m5_staleness),
]

SCHEMA_VERSION = MIGRATIONS[-1][0] if MIGRATIONS else BASELINE_VERSION


def current_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT value FROM _meta WHERE key = 'schema_version'").fetchone()
    if row is None:
        return BASELINE_VERSION
    return int(row[0])


def migrate() -> int:
    """Bring the database up to SCHEMA_VERSION. Returns the resulting version."""
    conn = get_connection()
    try:
        version = current_version(conn)

        if version > SCHEMA_VERSION:
            raise RuntimeError(
                f"Database schema is version {version} but this code understands "
                f"at most {SCHEMA_VERSION}. The database was written by a newer "
                f"version of Kestrel. Refusing to run — update the code rather "
                f"than downgrading the database."
            )

        pending = [m for m in MIGRATIONS if m[0] > version]
        if not pending:
            logger.info("Schema up to date (version %d)", version)
            return version

        for target, description, fn in pending:
            logger.info("Migrating %d -> %d: %s", version, target, description)
            try:
                fn(conn)
                conn.execute(
                    "INSERT INTO _meta (key, value) VALUES ('schema_version', ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (str(target),),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                logger.error("Migration %d -> %d FAILED: %s", version, target, description)
                raise
            version = target

        logger.info("Schema migrated to version %d", version)
        return version
    finally:
        conn.close()
