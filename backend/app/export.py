"""Static export — writes the public dataset as split JSON files.

- index.json: listing summaries (no descriptions) for the ranked list view
- listings/{id}.json: full detail per listing (description + breakdown)

No private fields (notes, status) in any export file. This is what the
showroom builds against. Hosting stays free because the frontend reads
static JSON, not a live API.
"""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

from .database import get_connection

logger = logging.getLogger("kestrel.export")


def export_public(output_dir: Path) -> int:
    """Export scored canonical listings to split JSON files. Returns count."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT id, listing_type, source, board_slug,
               company_display, title_display, location_display,
               department, url, posted_at,
               is_remote, remote_confidence, description_quality,
               description,
               score, score_breakdown, degree_hard_required,
               experience_required
        FROM listings
        WHERE canonical_id IS NULL AND score IS NOT NULL
        ORDER BY score DESC
        """
    ).fetchall()
    conn.close()

    # Clean and recreate the output directory
    listings_dir = output_dir / "listings"
    if listings_dir.exists():
        shutil.rmtree(listings_dir)
    listings_dir.mkdir(parents=True, exist_ok=True)

    index_entries = []
    for row in rows:
        record = dict(row)
        listing_id = record["id"]
        breakdown = json.loads(record["score_breakdown"]) if record["score_breakdown"] else {}

        # Index entry: summary without description
        index_entries.append({
            "id": listing_id,
            "listing_type": record["listing_type"],
            "source": record["source"],
            "company": record["company_display"],
            "title": record["title_display"],
            "location": record["location_display"],
            "department": record["department"],
            "url": record["url"],
            "posted_at": record["posted_at"],
            "is_remote": bool(record["is_remote"]),
            "score": record["score"],
            "degree_hard_required": bool(record["degree_hard_required"]),
            "hygiene_score": breakdown.get("hygiene_score"),
            "skill_factor": breakdown.get("skill_factor"),
            "scale_label": breakdown.get("scale_label"),
            "experience_required": record["experience_required"],
        })

        # Per-listing detail file: full description + breakdown
        detail = {
            "id": listing_id,
            "listing_type": record["listing_type"],
            "source": record["source"],
            "company": record["company_display"],
            "title": record["title_display"],
            "location": record["location_display"],
            "department": record["department"],
            "url": record["url"],
            "posted_at": record["posted_at"],
            "is_remote": bool(record["is_remote"]),
            "description_quality": record["description_quality"],
            "description": record["description"],
            "score": record["score"],
            "degree_hard_required": bool(record["degree_hard_required"]),
            "breakdown": {
                "composite": breakdown.get("composite"),
                "hygiene_score": breakdown.get("hygiene_score"),
                "skill_factor": breakdown.get("skill_factor"),
                "scale_label": breakdown.get("scale_label"),
                "dimensions": breakdown.get("dimensions", {}),
                "detail": {
                    "skill_match": breakdown.get("detail", {}).get("skill_match", {}),
                    "degree_posture": breakdown.get("detail", {}).get("degree_posture", {}),
                    "freshness": breakdown.get("detail", {}).get("freshness", {}),
                    "location_fit": breakdown.get("detail", {}).get("location_fit", {}),
                    "seniority_fit": breakdown.get("detail", {}).get("seniority_fit", {}),
                },
            },
        }
        detail_path = listings_dir / f"{listing_id}.json"
        with open(detail_path, "w", encoding="utf-8") as f:
            json.dump(detail, f)

    # Write index
    index_path = output_dir / "index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump({
            "exported_at": datetime.utcnow().isoformat(),
            "count": len(index_entries),
            "listings": index_entries,
        }, f)

    logger.info("Exported %d listings to %s (index + per-listing detail)", len(index_entries), output_dir)
    return len(index_entries)
