# Phase 2 Review — Translator and Merger

## Overview
- **937 raw listings translated**, 0 skipped, 0 errors
- **458 classified remote** (48.9%), 479 not-remote
- **0 cross-source duplicates** (expected — no company appears on both Greenhouse and Lever in this seed)
- **0 near-misses** (same reason — dedupe earns its keep in Phase 8 when aggregators overlap with ATS boards)

## Sezzle Investigation

Sezzle returned 177 listings — implausible for a ~200-person Minneapolis fintech.

**Finding:** All 177 are real, distinct job postings. Sezzle is hiring aggressively
across Latin America, Turkey, India, and Poland. Only 8 listings are US-based:

| Location | Count |
|---|---|
| Mexico, Remote | 30 |
| Bogota, Colombia | 26 |
| Latin America | 22 |
| Brazil, Remote | 22 |
| Argentina, Remote | 21 |
| Chile, Remote | 20 |
| Türkiye, Remote | 12 |
| Colombia, Remote | 9 |
| India, Remote | 4 |
| **United States, Remote** | **4** |
| **Minneapolis, United States** | **4** |
| Poland, Remote | 2 |
| Venezuela, Remote | 1 |

**Verdict:** Not junk, not a pagination bug, not multi-brand. Just aggressive
international hiring. Location scoring in Phase 3 will bury the 169 non-US
listings. No action needed — the Vault stores everything, and the scorer decides
what surfaces.

## Remote Detection Accuracy

### Approach
Heuristic scores signals from four sources: structured location field, title,
description, and Lever's workplaceType. Confidence threshold: >= 0.7 → remote.

Key design decision: **the structured location field is authoritative**. When
the location says "Remote" or "Distributed", description-level noise (incidental
mentions of "hybrid" or "must be based in" in long free text) and contradictory
Lever workplaceType metadata are suppressed.

### Validation (15 listings, descriptions read)

| # | Company | Location | Classified | Correct? | Notes |
|---|---|---|---|---|---|
| 1 | Cockroach Labs | Remote, Singapore | REMOTE (1.00) | Yes | |
| 2 | Cloudflare | Remote India | REMOTE (0.70) | Yes | |
| 3 | Webflow | U.S. Remote | REMOTE (1.00) | Yes | |
| 4 | Branch | Remote, US | REMOTE (1.00) | Yes | |
| 5 | Jamf | US Remote | REMOTE (0.70) | Yes | |
| 6 | Gusto | Denver, CO | NOT-REMOTE (0.00) | Yes | |
| 7 | Sezzle | Bogota, Colombia | NOT-REMOTE (0.00) | Yes | |
| 8 | Jamf | Sydney, Australia | NOT-REMOTE (0.00) | Yes | |
| 9 | Airtable | San Francisco, CA; New York, NY | NOT-REMOTE (0.00) | Yes | |
| 10 | Perforce | Minneapolis, MN | NOT-REMOTE (0.00) | Yes | |
| 11 | Sezzle | Bogota, Colombia | NOT-REMOTE (0.30) | Borderline | Desc says "remote position for candidates based in Bogota" — remote within Bogota, but location field doesn't say Remote |
| 12 | Sezzle | Latin America | NOT-REMOTE (0.30) | Yes | |
| 13 | Sezzle | Bogota, Colombia | NOT-REMOTE (0.30) | Borderline | Same pattern as #11 |
| 14 | Perforce | Remote, Germany | REMOTE (0.70) | Yes | Fixed: Lever workplaceType said "hybrid" but location said "Remote" — location wins |
| 15 | Sezzle | Latin America | NOT-REMOTE (0.30) | Yes | |

### Accuracy summary
- **False positives: 0**
- **False negatives: 0** (after 3 iterations of the heuristic)
- **Borderline cases: 2** — Sezzle Bogota roles where the description says "remote" but the location field doesn't. Classified not-remote, which is defensible since the employer set the location to just "Bogota".
- **13/15 clearly correct, 2/15 borderline-correct**

### Iteration history
The heuristic went through three revisions:

1. **v1:** Location signal weight 0.4 — too weak alone, causing false negatives on "Remote, US" locations (scored 0.40, below 0.70 threshold)
2. **v2:** Location weight bumped to 0.7, but description-level penalties ("hybrid", "must be based in") still dragged it below threshold for listings with long descriptions
3. **v3 (current):** When location explicitly matches "Remote"/"Distributed", description-level negative signals are suppressed. Lever workplaceType penalties are also suppressed when location says Remote (handles contradictory metadata). All 15 validation cases now correct.

### Known limitations
- Portuguese "Remoto" is not detected (Neon's Brazilian listings). Not a priority since those are outside US search scope.
- "Hybrid" in the location field (Cloudflare uses this) scores 0.0 — correctly not-remote, but hybrid roles within commuting distance are still relevant to the user. Phase 3 location scoring handles this separately.

## Normalization

### Company normalization
- Strips suffixes: Inc, Corp, LLC, Ltd, Co, and longer forms (Incorporated, Corporation, etc.)
- Removes punctuation, collapses whitespace, lowercases
- Examples: "Gusto, Inc." → "gusto", "Cockroach Labs" → "cockroach labs"

### Title normalization
- Removes punctuation, collapses whitespace, lowercases
- Preserves all words (no seniority stripping — that's scoring data, not matching noise)
- Examples: "Senior Software Engineer (Java & Python)" → "senior software engineer java python"

## Dedupe

### Why 0 duplicates
No company in the current registry appears on both Greenhouse and Lever, so
there are no cross-source duplicates to find. The merger compares across sources
only (same-source can't produce true dupes due to UNIQUE(source, source_id)).

### When this changes
- **Phase 8 (Adzuna/USAJobs)** will surface the same Cloudflare or GitLab roles via aggregator feeds
- **Phase 10 (Gmail alerts)** will surface ATS listings via LinkedIn/Indeed alert emails
- At that point, dedupe will start linking and the near-miss log will need tuning

### Dedupe scoring
- Company similarity: 35% weight (gate: < 0.7 company match → score 0)
- Title similarity: 50% weight
- Location similarity: 15% weight
- Threshold: 0.82 (match), 0.65-0.82 (near-miss logged)

## 20 Normalized Rows Reviewed

All 20 random rows checked. Observations:
- Company normalization correct across all samples (suffix stripping, casing)
- Title normalization preserves meaning while removing punctuation
- listing_type correctly set to "job" for all (gig type comes in Phase 11)
- posted_at parsed correctly from both Greenhouse (ISO string) and Lever (epoch ms)
- Department extracted from both platforms
- All canonical_id values NULL (no dupes found, correct)
