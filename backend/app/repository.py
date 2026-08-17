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
    """Store a raw listing. Returns True if inserted, False if already existed."""
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO raw_listings (source, board_slug, source_id, raw_json, fetched_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (source, board_slug, source_id, json.dumps(raw_json), fetched_at.isoformat()),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Duplicate — same source + source_id already stored
        return False
    finally:
        conn.close()


def raw_listing_count() -> int:
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM raw_listings").fetchone()[0]
    conn.close()
    return count
