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
    """Export scored canonical listings with per-profile scores.

    Each listing in the index carries scores for ALL profiles so the
    showroom can switch rankings client-side with no backend.
    """
    from .scoring.judge import (
        _load_profile_yaml, score_listing, score_gig_listing, _PROFILES_DIR,
    )
    from datetime import datetime as dt

    # Load all profiles
    profiles_index = _load_profile_yaml("profiles.yaml")
    active_name = profiles_index.get("active", "fullstack")
    all_profiles = {}
    for pname, pinfo in profiles_index.get("profiles", {}).items():
        profile_path = _PROFILES_DIR / pinfo["profile"]
        weights_path = _PROFILES_DIR / pinfo["weights"]
        import yaml
        with open(profile_path, encoding="utf-8") as f:
            profile = yaml.safe_load(f)
        with open(weights_path, encoding="utf-8") as f:
            weights = yaml.safe_load(f)
        all_profiles[pname] = (pinfo.get("label", pname), profile, weights)

    # Load gig weights once — fail loudly if missing
    gig_weights_path = _PROFILES_DIR.parent / "gig_weights.yaml"
    if not gig_weights_path.exists():
        raise FileNotFoundError(
            f"config/gig_weights.yaml not found at {gig_weights_path}. "
            f"Required for scoring gig listings. No fallback."
        )
    with open(gig_weights_path, encoding="utf-8") as f:
        gig_weights = yaml.safe_load(f)

    conn = get_connection()
    rows = conn.execute(
        """
        SELECT id, listing_type, source, board_slug,
               company_display, title_display, location_display,
               department, url, posted_at,
               is_remote, remote_confidence, description_quality,
               description, description_quality,
               score, score_breakdown, degree_hard_required,
               experience_required, bid_count
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

    now = dt.utcnow()
    index_entries = []
    for row in rows:
        record = dict(row)
        listing_id = record["id"]
        breakdown = json.loads(record["score_breakdown"]) if record["score_breakdown"] else {}

        # Score this listing under each profile
        profile_scores = {}
        profile_breakdowns = {}
        for pname, (plabel, profile, weights) in all_profiles.items():
            lt = record["listing_type"]
            if lt == "gig":
                composite, bd = score_gig_listing(record, profile, gig_weights, now)
            else:
                composite, bd = score_listing(record, profile, weights, now)
            profile_scores[pname] = {
                "score": composite,
                "skill_factor": bd.get("skill_factor"),
                "scale_label": bd.get("scale_label"),
                "hygiene_score": bd.get("hygiene_score"),
            }
            profile_breakdowns[pname] = {
                "composite": bd.get("composite"),
                "hygiene_score": bd.get("hygiene_score"),
                "skill_factor": bd.get("skill_factor"),
                "scale_label": bd.get("scale_label"),
                "dimensions": bd.get("dimensions", {}),
                "detail": {
                    k: bd.get("detail", {}).get(k, {})
                    for k in ("skill_match", "degree_posture", "freshness",
                              "location_fit", "seniority_fit", "experience_fit",
                              "source_quality", "budget_signal", "locality", "competition")
                    if k in bd.get("detail", {})
                },
            }

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
            "profiles": profile_scores,
        })

        # Per-listing detail file: full description + per-profile breakdowns
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
            "breakdown": profile_breakdowns.get(active_name, {}),
            "profile_breakdowns": profile_breakdowns,
        }
        detail_path = listings_dir / f"{listing_id}.json"
        with open(detail_path, "w", encoding="utf-8") as f:
            json.dump(detail, f)

    # Load profile info for the index
    from .scoring.judge import load_active_profile, _load_profile_yaml
    active_name, _, _ = load_active_profile()
    try:
        profiles_index = _load_profile_yaml("profiles.yaml")
        profiles_meta = [
            {"name": n, "label": info.get("label", n), "active": n == active_name}
            for n, info in profiles_index.get("profiles", {}).items()
        ]
    except Exception:
        profiles_meta = []

    # Write index
    index_path = output_dir / "index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump({
            "exported_at": datetime.utcnow().isoformat(),
            "count": len(index_entries),
            "active_profile": active_name,
            "profiles": profiles_meta,
            "listings": index_entries,
        }, f)

    logger.info("Exported %d listings to %s (index + per-listing detail)", len(index_entries), output_dir)
    return len(index_entries)
