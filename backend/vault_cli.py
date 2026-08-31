"""Standalone entrypoint: python -m backend.vault_cli {export|import|status}

Moves the raw vault between the local database and a gzipped snapshot file.
The pipeline uses this to carry the vault across CI runs; locally it is how
you pull the accumulated vault down without re-fetching anything.

    python -m backend.vault_cli export --to data/vault-snapshot.db.gz
    python -m backend.vault_cli import --from data/vault-snapshot.db.gz
    python -m backend.vault_cli status
"""

import argparse
import logging
import sys
from pathlib import Path

from backend.app.database import init_db
from backend.app.repository import staleness_summary
from backend.app.vault import default_snapshot_path, export_snapshot, import_snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vault_cli", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_exp = sub.add_parser("export", help="write a vault snapshot")
    p_exp.add_argument("--to", type=Path, default=None)

    p_imp = sub.add_parser("import", help="merge a vault snapshot into the database")
    p_imp.add_argument("--from", dest="src", type=Path, default=None)
    p_imp.add_argument(
        "--allow-missing", action="store_true",
        help="treat a missing snapshot as an empty vault instead of an error. "
             "Only for bootstrapping the very first run.",
    )

    p_man = sub.add_parser(
        "manifest", help="write a JSON summary of the vault (published alongside the snapshot)"
    )
    p_man.add_argument("--to", type=Path, default=None)

    sub.add_parser("status", help="report vault size and staleness")

    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    init_db()

    if args.command == "export":
        dest = args.to or default_snapshot_path()
        info = export_snapshot(dest)
        print(
            f"Wrote {info['path']} — {info['gz_bytes'] / 1048576:.2f} MB gzipped, "
            f"{info['tables']['raw_listings']} raw listings"
        )
        return 0

    if args.command == "import":
        src = args.src or default_snapshot_path()
        if not Path(src).exists():
            if args.allow_missing:
                # Loud on purpose. A missing vault is normal exactly once.
                print(
                    f"::warning::No vault snapshot at {src} — starting a NEW, EMPTY vault. "
                    f"This is only correct on the first run after enabling vault "
                    f"persistence. If you see this twice, the snapshot is not being "
                    f"published and history is being lost every run.",
                    file=sys.stderr,
                )
                print("Vault: starting empty (no snapshot found)")
                return 0
            print(f"::error::No vault snapshot at {src}", file=sys.stderr)
            return 1
        info = import_snapshot(src)
        print(
            f"Vault restored: {info['total']} raw listings "
            f"({info['restored']} new, {info['already_local']} already local)"
        )
        return 0

    if args.command == "manifest":
        import json
        import os

        from backend.app.database import get_connection

        conn = get_connection()
        by_source = {
            r[0]: r[1]
            for r in conn.execute(
                "SELECT source, COUNT(*) FROM raw_listings GROUP BY source ORDER BY 2 DESC"
            )
        }
        oldest = conn.execute("SELECT MIN(fetched_at) FROM raw_listings").fetchone()[0]
        newest = conn.execute("SELECT MAX(last_seen_at) FROM raw_listings").fetchone()[0]
        conn.close()

        snap = default_snapshot_path()
        manifest = {
            "raw_listings": sum(by_source.values()),
            "by_source": by_source,
            "oldest_entry": oldest,
            "last_seen": newest,
            "snapshot_bytes": snap.stat().st_size if snap.exists() else None,
            "run": os.environ.get("GITHUB_RUN_ID", ""),
        }
        text = json.dumps(manifest, indent=2) + chr(10)
        if args.to:
            Path(args.to).write_text(text, encoding="utf-8")
            print(f"Wrote {args.to}")
        else:
            print(text, end="")
        return 0

    if args.command == "status":
        from backend.app.database import get_connection

        conn = get_connection()
        rows = conn.execute(
            "SELECT source, COUNT(*) n, MIN(fetched_at) first, MAX(last_seen_at) last "
            "FROM raw_listings GROUP BY source ORDER BY n DESC"
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM raw_listings").fetchone()[0]
        conn.close()

        print(f"Vault: {total} raw listings")
        for r in rows:
            print(f"  {r['source']:16} {r['n']:6}  first {r['first'][:10]}  last seen {str(r['last'])[:16]}")
        s = staleness_summary()
        print(f"Listings: {s['total']} total, {s['live']} live, {s['stale']} stale")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
