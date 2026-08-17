"""Standalone entrypoint: python -m backend.fetch

Fetches from all active registry companies and prints a report.
Runnable independently of the web server (CLAUDE.md portability rule).
"""

import logging

from app.collector import fetch_all, print_report
from app.repository import raw_listing_count

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    before = raw_listing_count()
    results = fetch_all()
    after = raw_listing_count()
    print_report(results)
    print(f"Raw listings in vault: {before} before → {after} after ({after - before} new)")
