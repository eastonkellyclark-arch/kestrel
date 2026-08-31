"""The Merger — confidence-scored dedupe over normalized listings.

Matches on normalized company + normalized title + location proximity.
Duplicates are linked to a canonical listing, never deleted.
Near-misses (just below threshold) are logged for tuning.
"""

import logging
import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from .database import get_connection
from .settings import settings

logger = logging.getLogger("kestrel.merger")

DEDUPE_THRESHOLD = 0.82
LOCATION_GATE = 0.50  # below this the two postings are different places
CROSS_SOURCE_TITLE_GATE = 0.85  # fuzzy titles across sources, but not this fuzzy
NEAR_MISS_THRESHOLD = 0.65  # anything between this and DEDUPE is a near-miss
NEAR_MISS_LOG_LIMIT = 500  # the file is a tuning aid, not an audit log


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
    blocked_by: str | None = None


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


_REMOTE_WORDS = {"remote", "distributed", "anywhere", "virtual", "worldwide"}

# Administrative filler that carries no discriminating information.
_GENERIC_PLACE_WORDS = {
    "county", "city", "area", "metro", "greater", "region", "the",
    # "saint" alone matched Saint Cloud against Saint Louis County and
    # merged two postings 150 miles apart.
    "saint", "st", "ste",
}

# The same place written several ways. Sources mix "MN" and "Minnesota",
# "USA" and "United States"; without this they look like different places and
# real duplicates survive.
_PLACE_ALIASES = {
    "usa": "us", "united": "us", "states": "us",
    "uk": "gb", "britain": "gb", "england": "gb",
    "mn": "minnesota", "wi": "wisconsin", "ia": "iowa", "nd": "northdakota",
    "sd": "southdakota", "il": "illinois", "ca": "california", "ny": "newyork",
    "tx": "texas", "wa": "washington", "ma": "massachusetts", "co": "colorado",
    "fl": "florida", "ga": "georgia", "az": "arizona", "or": "oregon",
    "nc": "northcarolina", "va": "virginia", "pa": "pennsylvania", "oh": "ohio",
    "mi": "michigan", "nj": "newjersey", "md": "maryland", "ut": "utah",
}


def _location_parts(loc: str) -> tuple[bool, frozenset[str]]:
    """Split a location into (is_remote, distinguishing place tokens).

    "Remote (USA)"                      -> (True,  {"us"})
    "US, Minnesota, Hennepin County, Minneapolis"
                                        -> (False, {"us","minnesota","hennepin","minneapolis"})
    "Minneapolis, MN"                   -> (False, {"minneapolis","minnesota"})
    """
    text = re.sub(r"[^a-z0-9]+", " ", loc.lower()).strip()
    tokens = [t for t in text.split() if t]
    is_remote = any(t in _REMOTE_WORDS for t in tokens)
    place = {
        _PLACE_ALIASES.get(t, t)
        for t in tokens
        if t not in _REMOTE_WORDS and t not in _GENERIC_PLACE_WORDS
    }
    return is_remote, frozenset(place)


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _location_similarity(loc_a: str, loc_b: str) -> float:
    """Location matching by overlapping place tokens.

    Two failures this replaces, both of which merged genuinely different
    postings:

      - Any two strings containing "remote" scored 0.90, so "Remote (USA)" and
        "Remote (Peru)" were the same posting.
      - Raw string similarity on Adzuna's hierarchical locations is dominated
        by the shared prefix: "US, Minnesota, Hennepin County, Minneapolis" and
        "US, Minnesota, Saint Louis County, Duluth" scored 0.95. Merging those
        hides a metro-area job behind one 150 miles away and corrupts the
        location score that ranking depends on.

    Comparing the set of distinguishing tokens is insensitive to ordering and
    to how deep the hierarchy goes, which is what actually varies by source.
    """
    if not loc_a or not loc_b:
        return 0.5  # unknown locations get neutral score

    a = loc_a.lower().strip()
    b = loc_b.lower().strip()
    if a == b:
        return 1.0

    remote_a, place_a = _location_parts(loc_a)
    remote_b, place_b = _location_parts(loc_b)

    if remote_a and remote_b:
        if not place_a and not place_b:
            return 0.9              # both just "Remote"
        if not place_a or not place_b:
            return 0.5              # one unqualified — unknown, not different
        if place_a == place_b:
            return 1.0
        # Different named regions. These are different jobs.
        return _jaccard(place_a, place_b) * 0.4

    if place_a and place_b:
        return _jaccard(place_a, place_b)

    return _similarity(a, b)


def compute_dedupe_score(
    company_a: str, company_b: str,
    title_a: str, title_b: str,
    location_a: str, location_b: str,
    same_source: bool = False,
) -> float:
    """Weighted similarity score for two listings.

    `same_source` tightens the title rule. Within one source a company's own
    board distinguishes its roles by title, so two different titles are two
    different jobs — "Senior Systems Engineer, Workers AI" and "...Workers
    Runtime" are 0.90 similar as strings and are not the same posting. Across
    sources titles get truncated and decorated ("… - Remote", agency
    prefixes), so fuzzy matching is what finds the real duplicates there.
    """
    score, blocked = dedupe_verdict(
        company_a, company_b, title_a, title_b, location_a, location_b, same_source
    )
    return 0.0 if blocked else score


def dedupe_verdict(
    company_a: str, company_b: str,
    title_a: str, title_b: str,
    location_a: str, location_b: str,
    same_source: bool = False,
) -> tuple[float, str | None]:
    """Return (score, block_reason).

    A blocked pair scores 0.0 and names the gate that blocked it, so the
    near-miss log can show what the gates are actually rejecting. A gate that
    silently returns zero is untunable.
    """
    company_sim = _similarity(company_a, company_b)
    title_sim = _similarity(title_a, title_b)
    location_sim = _location_similarity(location_a, location_b)
    weighted = company_sim * 0.35 + title_sim * 0.50 + location_sim * 0.15

    # Company match is the gate — different companies are never dupes
    if company_sim < 0.7:
        return 0.0, "different company"

    # Location is a gate too. Company and title alone are not enough: the same
    # role posted in eight countries shares both, and the weighted score would
    # clear the threshold on title similarity even with the location term at
    # zero (0.35 + 0.50 = 0.85 > 0.82).
    if location_sim < LOCATION_GATE:
        return weighted, f"location ({location_sim:.2f} < {LOCATION_GATE})"

    # Title gate. With same_source the company and location terms are both 1.0
    # by construction, which drops the effective title bar to 0.64 — loose
    # enough to merge unrelated roles at the same employer. A false merge hides
    # a real job behind a canonical one, so this errs toward keeping both.
    if same_source:
        if title_a != title_b:
            return weighted, f"same-source title mismatch ({title_sim:.2f})"
    elif title_sim < CROSS_SOURCE_TITLE_GATE:
        return weighted, f"cross-source title ({title_sim:.2f} < {CROSS_SOURCE_TITLE_GATE})"

    return weighted, None


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

                # Same-source pairs ARE compared. UNIQUE(source, source_id)
                # stops the same posting being stored twice; it does nothing
                # about one company posting the same role under several job
                # IDs, which is where nearly all real duplicates come from.

                score, blocked = dedupe_verdict(
                    row_a["company_normalized"], row_b["company_normalized"],
                    row_a["title_normalized"], row_b["title_normalized"],
                    row_a["location_display"] or "", row_b["location_display"] or "",
                    same_source=row_a["source"] == row_b["source"],
                )

                if not blocked and score >= DEDUPE_THRESHOLD:
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
                        blocked_by=blocked,
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
    # Flatten chains. Matches are computed from one snapshot, so A<-B and B<-C
    # can both be recorded; C would then point at a duplicate rather than at a
    # real canonical listing. Resolve every pointer to its root.
    for _ in range(10):
        changed = conn.execute(
            """
            UPDATE listings SET canonical_id = (
                SELECT p.canonical_id FROM listings p WHERE p.id = listings.canonical_id
            )
            WHERE canonical_id IS NOT NULL
              AND (SELECT p.canonical_id FROM listings p WHERE p.id = listings.canonical_id)
                  IS NOT NULL
            """
        ).rowcount
        if not changed:
            break

    # A listing must never be its own canonical.
    conn.execute("UPDATE listings SET canonical_id = NULL WHERE canonical_id = id")

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
            for nm in sorted(near_misses, key=lambda x: -x.score)[:NEAR_MISS_LOG_LIMIT]:
                reason = f" [blocked: {nm.blocked_by}]" if nm.blocked_by else ""
                f.write(f"Score: {nm.score:.3f}{reason}\n")
                f.write(f"  A: [{nm.company_a}] {nm.title_a} @ {nm.location_a}\n")
                f.write(f"  B: [{nm.company_b}] {nm.title_b} @ {nm.location_b}\n\n")
        logger.info("Wrote %d near-misses to %s", len(near_misses), near_miss_file)

    if matches:
        logger.info("Linked %d duplicates", len(matches))
    logger.info("Found %d near-misses", len(near_misses))

    return stats
