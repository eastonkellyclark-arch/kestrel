"""Standalone entrypoint: python -m backend.rescore

Recomputes all scores from YAML profiles. Zero network calls.
"""

import logging
import sys

from app.database import init_db
from app.scoring.judge import score_all, print_top_bottom

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    init_db()

    print("=== Rescoring all listings from YAML ===")
    stats = score_all()
    print(f"  Scored: {stats['scored']}, Dealbreakers: {stats['dealbreakers']}")

    print("\n\n========== GLOBAL VIEW ==========")
    print_top_bottom(20)

    print("\n\n========== DIVERSITY VIEW (max 2 per company) ==========")
    print_top_bottom(20, per_company_cap=2)
