"""Standalone entrypoint: python -m backend.translate

Translates all raw listings and runs dedupe.
"""

import logging

from app.database import init_db
from app.translator import translate_all
from app.merger import merge_all
from app.settings import settings

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    init_db()

    print("=== Translating raw listings ===")
    stats = translate_all()
    print(f"  Raw: {stats['total']}, Translated: {stats['translated']}, "
          f"Skipped: {stats['skipped']}, Errors: {stats['errors']}")

    near_miss_path = str(settings.data_dir / "near_misses.txt")
    print("\n=== Running dedupe ===")
    dedupe_stats = merge_all(near_miss_file=near_miss_path)
    print(f"  Canonical: {dedupe_stats['total']}, "
          f"Duplicates linked: {dedupe_stats['duplicates']}, "
          f"Near-misses: {dedupe_stats['near_misses']}")
    print(f"  Near-miss log: {near_miss_path}")
