"""Static export — writes the public dataset to JSON.

Listings, scores, breakdowns. No private fields (notes, status).
This is what the showroom builds against. Hosting stays free because
the frontend reads static JSON, not a live API.
"""

import json
import logging
from pathlib import Path

from .database import get_connection

logger = logging.getLogger("kestrel.export")

# Fields explicitly excluded from the public export
_PRIVATE_FIELDS = {"status", "notes", "canonical_id", "dedupe_score", "created_at"}


def export_public(output_path: Path) -> int:
    """Export scored canonical listings to a JSON file. Returns count."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT id, listing_type, source, board_slug,
               company_display, title_display, location_display,
               department, url, posted_at,
               is_remote, remote_confidence, description_quality,
               score, score_breakdown
        FROM listings
        WHERE canonical_id IS NULL AND score IS NOT NULL
        ORDER BY score DESC
        """
    ).fetchall()
    conn.close()

    listings = []
    for row in rows:
        record = dict(row)
        if record["score_breakdown"]:
            record["score_breakdown"] = json.loads(record["score_breakdown"])
            # Strip internal detail from breakdown (descriptions, etc.)
            record["score_breakdown"].pop("detail", None)
        listings.append(record)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"exported_at": __import__("datetime").datetime.utcnow().isoformat(),
                    "count": len(listings),
                    "listings": listings}, f, indent=2)

    logger.info("Exported %d listings to %s", len(listings), output_path)
    return len(listings)
