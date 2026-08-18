"""The Merger — confidence-scored dedupe over normalized listings.

Matches on normalized company + normalized title + location proximity.
Duplicates are linked to a canonical listing, never deleted.
Near-misses (just below threshold) are logged for tuning.
"""

import logging
from dataclasses import dataclass
from difflib import SequenceMatcher

from .database import get_connection
from .settings import settings

logger = logging.getLogger("kestrel.merger")

DEDUPE_THRESHOLD = 0.82
NEAR_MISS_THRESHOLD = 0.65  # anything between this and DEDUPE is a near-miss


@dataclass
class DedupeMatch:
    listing_id: int
    canonical_id: int
    score: float
    title_a: str
    title_b: str
    company_a: str
    company_b: str
    location_a: str
    location_b: str


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def _location_similarity(loc_a: str, loc_b: str) -> float:
    """Location matching — exact match, city extraction, or fuzzy."""
    if not loc_a or not loc_b:
        return 0.5  # unknown locations get neutral score
    a = loc_a.lower().strip()
    b = loc_b.lower().strip()
    if a == b:
        return 1.0
    # Both "Remote" variants
    if "remote" in a and "remote" in b:
        return 0.9
    return _similarity(a, b)


def compute_dedupe_score(
    company_a: str, company_b: str,
    title_a: str, title_b: str,
    location_a: str, location_b: str,
) -> float:
    """Weighted similarity score for two listings."""
    company_sim = _similarity(company_a, company_b)
    title_sim = _similarity(title_a, title_b)
    location_sim = _location_similarity(location_a, location_b)

    # Company match is the gate — different companies are never dupes
    if company_sim < 0.7:
        return 0.0

    # Weighted combination
    return company_sim * 0.35 + title_sim * 0.50 + location_sim * 0.15


def merge_all(near_miss_file: str | None = None) -> dict:
    """Find and link duplicates. Returns stats."""
    conn = get_connection()

    # Only consider canonical listings (not already marked as dupes)
    rows = conn.execute(
        """
        SELECT id, company_normalized, title_normalized, location_display,
               company_display, title_display, source, source_id
        FROM listings
        WHERE canonical_id IS NULL
        ORDER BY id
        """
    ).fetchall()
    conn.close()

    stats = {"total": len(rows), "duplicates": 0, "near_misses": 0}
    matches: list[DedupeMatch] = []
    near_misses: list[DedupeMatch] = []

    # Compare each listing to all earlier canonical listings
    # Group by company to avoid O(n^2) across unrelated companies
    by_company: dict[str, list] = {}
    for row in rows:
        cn = row["company_normalized"]
        if cn not in by_company:
            by_company[cn] = []
        by_company[cn].append(row)

    # Also check across similar company names
    company_names = list(by_company.keys())

    for i, cn_a in enumerate(company_names):
        # Find similar company names
        similar_companies = [cn_a]
        for cn_b in company_names[i + 1:]:
            if _similarity(cn_a, cn_b) >= 0.7:
                similar_companies.append(cn_b)

        # Collect all listings from similar companies
        all_listings = []
        for cn in similar_companies:
            all_listings.extend(by_company[cn])

        # Compare within this cluster
        for j in range(len(all_listings)):
            row_a = all_listings[j]
            for k in range(j + 1, len(all_listings)):
                row_b = all_listings[k]

                # Skip same-source comparisons (same source can't produce dupes
                # because of UNIQUE(source, source_id))
                if row_a["source"] == row_b["source"]:
                    continue

                score = compute_dedupe_score(
                    row_a["company_normalized"], row_b["company_normalized"],
                    row_a["title_normalized"], row_b["title_normalized"],
                    row_a["location_display"] or "", row_b["location_display"] or "",
                )

                if score >= DEDUPE_THRESHOLD:
                    match = DedupeMatch(
                        listing_id=row_b["id"],
                        canonical_id=row_a["id"],
                        score=score,
                        title_a=row_a["title_display"],
                        title_b=row_b["title_display"],
                        company_a=row_a["company_display"],
                        company_b=row_b["company_display"],
                        location_a=row_a["location_display"] or "",
                        location_b=row_b["location_display"] or "",
                    )
                    matches.append(match)
                elif score >= NEAR_MISS_THRESHOLD:
                    near_miss = DedupeMatch(
                        listing_id=row_b["id"],
                        canonical_id=row_a["id"],
                        score=score,
                        title_a=row_a["title_display"],
                        title_b=row_b["title_display"],
                        company_a=row_a["company_display"],
                        company_b=row_b["company_display"],
                        location_a=row_a["location_display"] or "",
                        location_b=row_b["location_display"] or "",
                    )
                    near_misses.append(near_miss)

    # Apply matches — mark duplicates and inherit remote status
    conn = get_connection()
    for m in matches:
        conn.execute(
            "UPDATE listings SET canonical_id = ?, dedupe_score = ? WHERE id = ? AND canonical_id IS NULL",
            (m.canonical_id, m.score, m.listing_id),
        )

    # Cross-reference: when a gmail_alert/adzuna listing is linked to an ATS
    # canonical, inherit the ATS version's remote status (it has structured data).
    conn.execute(
        """
        UPDATE listings SET
            is_remote = (SELECT c.is_remote FROM listings c WHERE c.id = listings.canonical_id),
            remote_confidence = (SELECT c.remote_confidence FROM listings c WHERE c.id = listings.canonical_id)
        WHERE canonical_id IS NOT NULL
          AND source IN ('gmail_alert', 'adzuna')
          AND (SELECT c.source FROM listings c WHERE c.id = listings.canonical_id)
              IN ('greenhouse', 'lever', 'ashby', 'recruitee')
        """
    )
    conn.commit()
    conn.close()

    stats["duplicates"] = len(matches)
    stats["near_misses"] = len(near_misses)

    # Write near-misses to file for tuning
    if near_miss_file and near_misses:
        with open(near_miss_file, "w", encoding="utf-8") as f:
            f.write("# Near-miss dedupe entries (score between "
                    f"{NEAR_MISS_THRESHOLD} and {DEDUPE_THRESHOLD})\n")
            f.write(f"# {len(near_misses)} entries\n\n")
            for nm in sorted(near_misses, key=lambda x: -x.score):
                f.write(f"Score: {nm.score:.3f}\n")
                f.write(f"  A: [{nm.company_a}] {nm.title_a} @ {nm.location_a}\n")
                f.write(f"  B: [{nm.company_b}] {nm.title_b} @ {nm.location_b}\n\n")
        logger.info("Wrote %d near-misses to %s", len(near_misses), near_miss_file)

    if matches:
        logger.info("Linked %d duplicates", len(matches))
    logger.info("Found %d near-misses", len(near_misses))

    return stats
