# Phase 3 — The Judge

## What was built
- `config/profile.yaml` — skills (primary/secondary/bonus), target seniority, dealbreakers
- `config/weights.yaml` — six dimension weights summing to 100
- Six scorers: skill_match, degree_posture, freshness, location_fit, seniority_fit, source_quality
- Degree-posture parser detecting: hard requirement, equivalent-ok, no-degree, not-mentioned
- Description quality classifier: good, empty, title_only, non_english
- Per-dimension breakdown stored as JSON alongside composite score
- `rescore` command recomputes from YAML with zero network calls
- 37 unit tests covering all scorers with edge cases
- Top/bottom 20 printout in global and diversity (2-per-company cap) views

## Pre-Phase 3 findings

### Description quality
- 924 good, 0 empty, 0 title_only, 13 non_english
- All 13 non-English are from Neon (Brazilian Portuguese)
- Scorers handle low-quality descriptions explicitly: degree_posture returns 50 (neutral), skill_match applies a 30% penalty

### US vs non-US breakdown
- **286 US-relevant out of 937 (30.5%)**
- Cloudflare: 6 US / 292 non-US (2% US)
- Sezzle: 8 US / 169 non-US (5% US)
- GitLab: 87 US / 110 non-US (44% US)
- Gusto, Airtable, Total Expert: 100% US
- Location scoring effectively buries non-US listings (score 5-15)

## Scoring results

### Score distribution (937 listings)
- Dealbreakers: 2 (Cloudflare federal roles requiring clearance)
- Top score: 64.9
- Median: ~42
- Bottom (non-dealbreaker): ~25

### Key observation
The top 20 is dominated by listings with:
- No degree requirement (90-100 on degree_posture)
- Fresh posting (85-100 on freshness)
- US Remote location (90 on location_fit)
- Low skill match (0-15 on skill_match)

Non-tech roles (demand generation, customer support, recruiters) rank higher
than engineering roles with more skill matches because they typically don't
mention degree requirements and have favorable location + seniority scores.

The diversity view (2-per-company cap) fixes the Cloudflare/GitLab volume
dominance and surfaces TC companies: Livefront, Perforce, Total Expert,
Sezzle, Jamf.

### Rescore verification
Changed skill_match weight 35→55: #466 (GitLab Senior Backend Engineer with
4 skill hits) jumped from #3 to #1. Restored. Zero network calls.
