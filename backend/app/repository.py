"""Database access layer. All SQL lives here — the rest of the app uses these functions."""

import json
import sqlite3
from datetime import datetime

from .database import get_connection
from .models import ATSPlatform, RegistryEntry


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def get_active_companies() -> list[RegistryEntry]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, company, platform, board_slug, active, added_date "
        "FROM registry WHERE active = 1 ORDER BY company"
    ).fetchall()
    conn.close()
    return [
        RegistryEntry(
            id=r["id"], company=r["company"],
            platform=ATSPlatform(r["platform"]),
            board_slug=r["board_slug"],
            active=bool(r["active"]),
            added_date=r["added_date"],
        )
        for r in rows
    ]


def upsert_registry(entry: RegistryEntry) -> int:
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO registry (company, platform, board_slug, active, added_date)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(platform, board_slug)
        DO UPDATE SET company=excluded.company, active=excluded.active
        """,
        (entry.company, entry.platform.value, entry.board_slug,
         int(entry.active), entry.added_date),
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return row_id


# ---------------------------------------------------------------------------
# Raw listings (the Vault)
# ---------------------------------------------------------------------------

def store_raw_listing(
    source: str,
    board_slug: str,
    source_id: str,
    raw_json: dict | list,
    fetched_at: datetime,
) -> bool:
    """Store a raw listing. Returns True if inserted, False if already existed.

    `raw_json` and `fetched_at` are write-once: the vault keeps the first
    response verbatim so a fixed parser can be re-run against it. `last_seen_at`
    is refreshed every time the source still returns this listing — that is what
    tells us a posting is still live rather than gone.
    """
    conn = get_connection()
    seen = fetched_at.isoformat()
    try:
        conn.execute(
            """
            INSERT INTO raw_listings
                (source, board_slug, source_id, raw_json, fetched_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (source, board_slug, source_id, json.dumps(raw_json), seen, seen),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Already in the vault — keep the original payload, record that the
        # source still lists it.
        conn.execute(
            "UPDATE raw_listings SET last_seen_at = ? WHERE source = ? AND source_id = ?",
            (seen, source, source_id),
        )
        conn.commit()
        return False
    finally:
        conn.close()


def raw_listing_count() -> int:
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM raw_listings").fetchone()[0]
    conn.close()
    return count


# ---------------------------------------------------------------------------
# Staleness
# ---------------------------------------------------------------------------

def mark_stale(healthy: set[tuple[str, str]], cutoff: datetime, now: datetime) -> dict:
    """Flag listings their source has stopped returning; clear the flag on ones
    that came back.

    `healthy` is the set of (vault_source, board_slug) pairs that fetched
    successfully this run. Only those are judged. A source that timed out or
    429'd has told us nothing about whether its listings still exist, and
    treating its silence as death would empty the board on a bad run — an API
    erroring and an API returning nothing are different states.

    Listings are never deleted. `is_stale` is its own column so the apply
    tracker's `status` and its history survive a posting going quiet.
    """
    if not healthy:
        # Every source failed. Nothing can be concluded about any listing.
        return {"marked": 0, "revived": 0, "sources_considered": 0}

    conn = get_connection()
    try:
        pairs = sorted(healthy)
        clause = " OR ".join("(vault_source = ? AND board_slug = ?)" for _ in pairs)
        flat = [v for pair in pairs for v in pair]

        marked = conn.execute(
            f"""
            UPDATE listings SET is_stale = 1, stale_since = ?
            WHERE is_stale = 0
              AND ({clause})
              AND (last_seen_at IS NULL OR last_seen_at < ?)
            """,
            [now.isoformat()] + flat + [cutoff.isoformat()],
        ).rowcount

        revived = conn.execute(
            f"""
            UPDATE listings SET is_stale = 0, stale_since = NULL
            WHERE is_stale = 1
              AND ({clause})
              AND last_seen_at >= ?
            """,
            flat + [cutoff.isoformat()],
        ).rowcount

        conn.commit()
        return {
            "marked": marked,
            "revived": revived,
            "sources_considered": len(pairs),
        }
    finally:
        conn.close()


def staleness_summary() -> dict:
    conn = get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
        stale = conn.execute("SELECT COUNT(*) FROM listings WHERE is_stale = 1").fetchone()[0]
        never_seen = conn.execute(
            "SELECT COUNT(*) FROM listings WHERE last_seen_at IS NULL"
        ).fetchone()[0]
        return {"total": total, "stale": stale, "live": total - stale,
                "never_seen": never_seen}
    finally:
        conn.close()
