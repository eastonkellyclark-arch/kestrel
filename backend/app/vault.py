"""Vault snapshots — how the raw vault survives between pipeline runs.

The pipeline runs on an ephemeral CI machine. For the vault to accumulate
(and for "re-parse instead of re-fetch" to mean anything) it has to be carried
from run to run. It used to be carried by committing the whole 35 MB SQLite
file to master every six hours, which grew the repository by ~140 MB/day and
would have pushed it past GitHub's limits within weeks.

A snapshot is different from the database in two ways that matter:

  1. It contains ONLY the vault: _meta, registry, raw_listings. Everything
     else — listings, dedupe links, scores — is derived, and is rebuilt by
     translate -> merge -> score on every run. Carrying derived data would
     mean carrying listing IDs, and imported IDs would collide with local ones
     and silently break canonical_id.

  2. It CANNOT contain private data. status_history, notes, resumes and
     portfolio_links are the desk's, they are local-only, and the repository
     is public. This is enforced structurally: the snapshot is built by
     copying an explicit allowlist of tables into a fresh database, so a
     private table cannot end up in one by omission or accident.

Snapshots are gzipped and published to a single-commit orphan branch, so the
repository carries exactly one copy rather than one per run.
"""

import gzip
import logging
import shutil
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

from .database import get_connection
from .settings import settings

logger = logging.getLogger("kestrel.vault")

# The only tables a snapshot may contain.
PUBLIC_TABLES = ("_meta", "registry", "raw_listings")

# Never leave this machine. Listed so the guard below can assert on them.
PRIVATE_TABLES = ("status_history", "notes", "resumes", "portfolio_links")

# Derived from the vault on every run — not carried.
DERIVED_TABLES = ("listings",)


def _table_sql(conn: sqlite3.Connection, name: str) -> list[str]:
    """CREATE statements for a table and its indexes."""
    rows = conn.execute(
        "SELECT sql FROM sqlite_master WHERE tbl_name = ? AND sql IS NOT NULL",
        (name,),
    ).fetchall()
    return [r[0] for r in rows]


def export_snapshot(dest: Path) -> dict:
    """Write a gzipped, vault-only snapshot of the database to `dest`."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    src = get_connection()
    tmpdir = Path(tempfile.mkdtemp(prefix="kestrel-snap-"))
    plain = tmpdir / "snapshot.db"

    try:
        out = sqlite3.connect(str(plain))
        out.execute("PRAGMA journal_mode=OFF")

        counts = {}
        for table in PUBLIC_TABLES:
            for stmt in _table_sql(src, table):
                out.execute(stmt)
            rows = src.execute(f"SELECT * FROM {table}").fetchall()  # noqa: S608 - allowlist
            if rows:
                placeholders = ",".join("?" for _ in rows[0].keys())
                out.executemany(
                    f"INSERT INTO {table} VALUES ({placeholders})",  # noqa: S608 - allowlist
                    [tuple(r) for r in rows],
                )
            counts[table] = len(rows)
        out.commit()

        # Structural guard: prove no private table rode along.
        present = {
            r[0] for r in out.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        leaked = present & set(PRIVATE_TABLES)
        if leaked:
            raise RuntimeError(
                f"Refusing to write snapshot: private tables present: {sorted(leaked)}. "
                f"Snapshots are published to a public branch."
            )

        out.execute("VACUUM")
        out.close()

        raw_bytes = plain.stat().st_size
        with open(plain, "rb") as f_in, gzip.open(dest, "wb", compresslevel=9) as f_out:
            shutil.copyfileobj(f_in, f_out, 1024 * 1024)

        gz_bytes = dest.stat().st_size
        logger.info(
            "Snapshot: %s (%.1f MB raw, %.1f MB gzipped) — %s",
            dest.name, raw_bytes / 1048576, gz_bytes / 1048576,
            ", ".join(f"{k}={v}" for k, v in counts.items()),
        )
        return {
            "path": str(dest),
            "raw_bytes": raw_bytes,
            "gz_bytes": gz_bytes,
            "tables": counts,
        }
    finally:
        src.close()
        shutil.rmtree(tmpdir, ignore_errors=True)


def import_snapshot(src: Path) -> dict:
    """Merge a gzipped snapshot into the local database.

    Additive and idempotent. Existing raw rows keep their original payload and
    fetched_at; only last_seen_at moves forward. Nothing is deleted, and no
    private table is touched.
    """
    src = Path(src)
    if not src.exists():
        raise FileNotFoundError(f"No vault snapshot at {src}")

    tmpdir = Path(tempfile.mkdtemp(prefix="kestrel-snap-"))
    plain = tmpdir / "snapshot.db"

    try:
        with gzip.open(src, "rb") as f_in, open(plain, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out, 1024 * 1024)

        conn = get_connection()
        conn.execute("ATTACH DATABASE ? AS snap", (str(plain),))

        before = conn.execute("SELECT COUNT(*) FROM raw_listings").fetchone()[0]

        conn.execute(
            """
            INSERT INTO raw_listings
                (source, board_slug, source_id, raw_json, fetched_at, last_seen_at)
            SELECT source, board_slug, source_id, raw_json, fetched_at, last_seen_at
            FROM snap.raw_listings
            WHERE true
            ON CONFLICT(source, source_id) DO UPDATE SET
                last_seen_at = MAX(
                    COALESCE(raw_listings.last_seen_at, raw_listings.fetched_at),
                    COALESCE(excluded.last_seen_at, excluded.fetched_at)
                )
            """
        )

        conn.execute(
            """
            INSERT INTO registry (company, platform, board_slug, active, added_date)
            SELECT company, platform, board_slug, active, added_date FROM snap.registry
            WHERE true
            ON CONFLICT(platform, board_slug) DO NOTHING
            """
        )

        conn.commit()
        after = conn.execute("SELECT COUNT(*) FROM raw_listings").fetchone()[0]
        conn.execute("DETACH DATABASE snap")
        conn.close()

        logger.info(
            "Vault restored: %d raw listings (%d already local, %d new)",
            after, before, after - before,
        )
        return {"total": after, "restored": after - before, "already_local": before}
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def default_snapshot_path() -> Path:
    return settings.data_dir / "vault-snapshot.db.gz"
