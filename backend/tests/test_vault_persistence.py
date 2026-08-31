"""Tests for vault persistence — migrations, snapshots, staleness.

The bug these guard against: the pipeline used to delete the database before
every fetch, so the vault never reached back further than one run and the
"re-parse instead of re-fetch" property did not actually exist.
"""

import gzip
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _run(code: str, data_dir: Path) -> subprocess.CompletedProcess:
    """Run code in a subprocess with its own data dir.

    settings is a module-level singleton resolved at import, so each database
    needs its own interpreter.
    """
    env = dict(os.environ, KESTREL_DATA_DIR=str(data_dir), PYTHONPATH=str(REPO_ROOT))
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True,
    )


def _seed_vault(data_dir: Path, entries: list[tuple[str, str, str]], stamp: str) -> None:
    """Put raw listings into a fresh vault. entries = (source, board_slug, source_id)."""
    code = (
        "from datetime import datetime\n"
        "from backend.app.database import init_db\n"
        "from backend.app.repository import store_raw_listing\n"
        "init_db()\n"
        f"for source, slug, sid in {entries!r}:\n"
        "    store_raw_listing(source, slug, sid, {'id': sid, 'title': 'engineer'},\n"
        f"                      datetime.fromisoformat({stamp!r}))\n"
    )
    r = _run(code, data_dir)
    assert r.returncode == 0, r.stderr


# --------------------------------------------------------------- migrations

def test_fresh_database_lands_on_current_schema(tmp_path):
    r = _run(
        "from backend.app.database import init_db, get_connection\n"
        "from backend.app.migrations import current_version, SCHEMA_VERSION\n"
        "init_db()\n"
        "c = get_connection()\n"
        "assert current_version(c) == SCHEMA_VERSION, current_version(c)\n"
        "print('ok')\n",
        tmp_path,
    )
    assert r.returncode == 0, r.stderr
    assert "ok" in r.stdout


def test_migration_is_idempotent(tmp_path):
    """init_db runs on every entrypoint — it must be safe to run repeatedly."""
    for _ in range(3):
        r = _run("from backend.app.database import init_db; init_db(); print('ok')", tmp_path)
        assert r.returncode == 0, r.stderr


def test_migration_preserves_existing_rows(tmp_path):
    """The whole point: upgrading the schema must not cost data."""
    _seed_vault(tmp_path, [("greenhouse", "jamf", "1"), ("greenhouse", "jamf", "2")],
                "2026-08-01T00:00:00")

    # Force a re-migration from the frozen baseline.
    db = sqlite3.connect(tmp_path / "kestrel.db")
    db.execute("UPDATE _meta SET value='4' WHERE key='schema_version'")
    db.commit()
    db.close()

    r = _run(
        "from backend.app.database import init_db, get_connection\n"
        "init_db()\n"
        "c = get_connection()\n"
        "print('rows', c.execute('select count(*) from raw_listings').fetchone()[0])\n",
        tmp_path,
    )
    assert r.returncode == 0, r.stderr
    assert "rows 2" in r.stdout


def test_database_newer_than_code_is_refused(tmp_path):
    """Silently running old code against a new schema corrupts data quietly."""
    _run("from backend.app.database import init_db; init_db()", tmp_path)

    db = sqlite3.connect(tmp_path / "kestrel.db")
    db.execute("UPDATE _meta SET value='999' WHERE key='schema_version'")
    db.commit()
    db.close()

    r = _run("from backend.app.database import init_db; init_db()", tmp_path)
    assert r.returncode != 0
    assert "999" in r.stderr
    assert "Refusing to run" in r.stderr


# ---------------------------------------------------------------- snapshots

def test_snapshot_round_trip_preserves_vault(tmp_path):
    src, dst = tmp_path / "a", tmp_path / "b"
    _seed_vault(src, [("greenhouse", "jamf", str(i)) for i in range(25)],
                "2026-08-01T00:00:00")

    snap = tmp_path / "snap.db.gz"
    r = _run(f"from backend.app.vault import export_snapshot; export_snapshot({str(snap)!r})", src)
    assert r.returncode == 0, r.stderr

    r = _run(
        "from backend.app.database import init_db, get_connection\n"
        "from backend.app.vault import import_snapshot\n"
        "init_db()\n"
        f"import_snapshot({str(snap)!r})\n"
        "c = get_connection()\n"
        "print('rows', c.execute('select count(*) from raw_listings').fetchone()[0])\n",
        dst,
    )
    assert r.returncode == 0, r.stderr
    assert "rows 25" in r.stdout


def test_snapshot_import_is_additive_not_destructive(tmp_path):
    """Restoring a snapshot must never drop rows the local vault already had."""
    src, dst = tmp_path / "a", tmp_path / "b"
    _seed_vault(src, [("greenhouse", "jamf", "shared")], "2026-08-01T00:00:00")
    _seed_vault(dst, [("lever", "neon", "local-only")], "2026-08-01T00:00:00")

    snap = tmp_path / "snap.db.gz"
    _run(f"from backend.app.vault import export_snapshot; export_snapshot({str(snap)!r})", src)

    r = _run(
        "from backend.app.vault import import_snapshot\n"
        "from backend.app.database import get_connection\n"
        f"import_snapshot({str(snap)!r})\n"
        "c = get_connection()\n"
        "print(sorted(r[0] for r in c.execute('select source_id from raw_listings')))\n",
        dst,
    )
    assert r.returncode == 0, r.stderr
    assert "local-only" in r.stdout
    assert "shared" in r.stdout


def test_snapshot_import_is_idempotent(tmp_path):
    src, dst = tmp_path / "a", tmp_path / "b"
    _seed_vault(src, [("greenhouse", "jamf", "x")], "2026-08-01T00:00:00")

    snap = tmp_path / "snap.db.gz"
    _run(f"from backend.app.vault import export_snapshot; export_snapshot({str(snap)!r})", src)

    r = _run(
        "from backend.app.database import init_db, get_connection\n"
        "from backend.app.vault import import_snapshot\n"
        "init_db()\n"
        f"import_snapshot({str(snap)!r})\n"
        f"import_snapshot({str(snap)!r})\n"
        "c = get_connection()\n"
        "print('rows', c.execute('select count(*) from raw_listings').fetchone()[0])\n",
        dst,
    )
    assert r.returncode == 0, r.stderr
    assert "rows 1" in r.stdout


def test_snapshot_never_contains_private_tables(tmp_path):
    """The snapshot is force-pushed to a branch of a PUBLIC repository.

    Application history, notes and resumes must be structurally incapable of
    riding along.
    """
    from backend.app.vault import PRIVATE_TABLES

    _seed_vault(tmp_path, [("greenhouse", "jamf", "1")], "2026-08-01T00:00:00")

    r = _run(
        "from backend.app.translator import translate_all\n"
        "from backend.app.database import get_connection\n"
        "translate_all()\n"
        "c = get_connection()\n"
        "lid = c.execute('select id from listings').fetchone()[0]\n"
        "c.execute('INSERT INTO resumes (label, filename, file_path, created_at) "
        "VALUES (?,?,?,?)', ('topsecretlabel', 'r.pdf', '/x', '2026-08-01'))\n"
        "c.execute('INSERT INTO notes (listing_id, content, created_at) "
        "VALUES (?,?,?)', (lid, 'topsecretnote', '2026-08-01'))\n"
        "c.execute('INSERT INTO status_history (listing_id, new_status, note, changed_at) "
        "VALUES (?,?,?,?)', (lid, 'applied', 'topsecrethistory', '2026-08-01'))\n"
        "c.commit()\n",
        tmp_path,
    )
    assert r.returncode == 0, r.stderr

    snap = tmp_path / "snap.db.gz"
    r = _run(
        f"from backend.app.vault import export_snapshot; export_snapshot({str(snap)!r})",
        tmp_path,
    )
    assert r.returncode == 0, r.stderr

    plain = tmp_path / "plain.db"
    with gzip.open(snap, "rb") as f_in:
        plain.write_bytes(f_in.read())

    conn = sqlite3.connect(plain)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()

    assert not (tables & set(PRIVATE_TABLES)), f"private tables leaked: {tables}"

    blob = plain.read_bytes()
    assert b"topsecretnote" not in blob
    assert b"topsecretlabel" not in blob
    assert b"topsecrethistory" not in blob


# ---------------------------------------------------------------- staleness

def test_listing_goes_stale_when_source_stops_returning_it(tmp_path):
    _seed_vault(tmp_path, [("greenhouse", "jamf", "gone")], "2026-08-01T00:00:00")
    r = _run(
        "from datetime import datetime, timedelta\n"
        "from backend.app.translator import translate_all\n"
        "from backend.app.repository import mark_stale, staleness_summary\n"
        "translate_all()\n"
        "now = datetime(2026, 8, 10)\n"
        "print(mark_stale({('greenhouse', 'jamf')}, now - timedelta(hours=24), now))\n"
        "print(staleness_summary())\n",
        tmp_path,
    )
    assert r.returncode == 0, r.stderr
    assert "'marked': 1" in r.stdout
    assert "'stale': 1" in r.stdout


def test_failed_source_does_not_mark_its_listings_stale(tmp_path):
    """An API erroring and an API returning nothing are different states.

    A source we could not reach has told us nothing about whether its listings
    still exist, and must not empty the board.
    """
    _seed_vault(tmp_path, [("greenhouse", "jamf", "still-there")], "2026-08-01T00:00:00")
    r = _run(
        "from datetime import datetime, timedelta\n"
        "from backend.app.translator import translate_all\n"
        "from backend.app.repository import mark_stale, staleness_summary\n"
        "translate_all()\n"
        "now = datetime(2026, 8, 10)\n"
        # greenhouse/jamf is NOT in the healthy set — it failed this run.
        "print(mark_stale({('lever', 'neon')}, now - timedelta(hours=24), now))\n"
        "print(staleness_summary())\n",
        tmp_path,
    )
    assert r.returncode == 0, r.stderr
    assert "'marked': 0" in r.stdout
    assert "'stale': 0" in r.stdout


def test_no_healthy_sources_marks_nothing(tmp_path):
    """A totally failed run must not wipe the board."""
    _seed_vault(tmp_path, [("greenhouse", "jamf", "a")], "2026-08-01T00:00:00")
    r = _run(
        "from datetime import datetime, timedelta\n"
        "from backend.app.translator import translate_all\n"
        "from backend.app.repository import mark_stale, staleness_summary\n"
        "translate_all()\n"
        "now = datetime(2026, 8, 10)\n"
        "print(mark_stale(set(), now - timedelta(hours=24), now))\n"
        "print(staleness_summary())\n",
        tmp_path,
    )
    assert r.returncode == 0, r.stderr
    assert "'marked': 0" in r.stdout
    assert "'stale': 0" in r.stdout


def test_stale_listing_revives_when_source_lists_it_again(tmp_path):
    _seed_vault(tmp_path, [("greenhouse", "jamf", "flappy")], "2026-08-01T00:00:00")
    r = _run(
        "from datetime import datetime, timedelta\n"
        "from backend.app.translator import translate_all\n"
        "from backend.app.repository import mark_stale, store_raw_listing, staleness_summary\n"
        "translate_all()\n"
        "now = datetime(2026, 8, 10)\n"
        "mark_stale({('greenhouse', 'jamf')}, now - timedelta(hours=24), now)\n"
        # The board lists it again; last_seen_at moves forward.
        "store_raw_listing('greenhouse', 'jamf', 'flappy', {'id': 'flappy'}, now)\n"
        "translate_all()\n"
        "print(mark_stale({('greenhouse', 'jamf')}, now - timedelta(hours=24), now))\n"
        "print(staleness_summary())\n",
        tmp_path,
    )
    assert r.returncode == 0, r.stderr
    assert "'revived': 1" in r.stdout
    assert "'stale': 0" in r.stdout


def test_reddit_source_label_mismatch_is_handled(tmp_path):
    """Reddit vaults under 'reddit' but surfaces as the subreddit.

    Keying staleness on listings.source alone would silently exclude every
    Reddit listing from ever being marked stale or revived.
    """
    _seed_vault(tmp_path, [("reddit", "r/forhire", "abc123")], "2026-08-01T00:00:00")
    r = _run(
        "from datetime import datetime, timedelta\n"
        "from backend.app.translator import translate_all\n"
        "from backend.app.repository import mark_stale\n"
        "from backend.app.database import get_connection\n"
        "translate_all()\n"
        "c = get_connection()\n"
        "row = c.execute('select source, vault_source, board_slug from listings').fetchone()\n"
        "print('labels', tuple(row))\n"
        "now = datetime(2026, 8, 10)\n"
        "print(mark_stale({('reddit', 'r/forhire')}, now - timedelta(hours=24), now))\n",
        tmp_path,
    )
    assert r.returncode == 0, r.stderr
    assert "'reddit'" in r.stdout          # vault_source retained
    assert "'marked': 1" in r.stdout       # and it is actually reachable


def test_raw_payload_is_write_once_but_last_seen_moves(tmp_path):
    """The vault keeps the first response verbatim so a fixed parser can be
    re-run against it; only last_seen_at advances."""
    _seed_vault(tmp_path, [("greenhouse", "jamf", "x")], "2026-08-01T00:00:00")
    r = _run(
        "import json\n"
        "from datetime import datetime\n"
        "from backend.app.repository import store_raw_listing\n"
        "from backend.app.database import get_connection\n"
        "store_raw_listing('greenhouse', 'jamf', 'x', {'id': 'x', 'title': 'CHANGED'},\n"
        "                  datetime(2026, 8, 20))\n"
        "c = get_connection()\n"
        "row = c.execute('select raw_json, fetched_at, last_seen_at from raw_listings').fetchone()\n"
        "print('payload', json.loads(row[0])['title'])\n"
        "print('fetched', row[1][:10])\n"
        "print('seen', row[2][:10])\n",
        tmp_path,
    )
    assert r.returncode == 0, r.stderr
    assert "payload engineer" in r.stdout      # original payload preserved
    assert "fetched 2026-08-01" in r.stdout    # first-seen unchanged
    assert "seen 2026-08-20" in r.stdout       # last-seen advanced
