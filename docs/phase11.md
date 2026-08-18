# Phase 11 — Gig Track

## What was built

### Gig sources
- **Google Alerts RSS**: config-driven feed URLs in `config/gig_feeds.yaml`.
  Add/remove alerts without code changes. Blocked on user providing feed URLs.
- **Reddit .rss**: r/forhire (25 items), r/smallbusiness, r/twincities,
  r/minneapolis. 2-second delay between feeds to avoid 429. Isolated — removal
  breaks nothing.
- **Craigslist via Open RSS**: 503 on all three feeds. Open RSS proxy may be
  down or URLs need adjustment. Adapter ready when service resumes.
- **HN Freelancer thread**: via Algolia `search_by_date`. 182 comments from
  the latest thread.

### Gig scoring (5 dimensions)
- **Deliverability** (skill_match as multiplier): can you build it?
- **Budget signal** (25): dollar amounts, "per hour", vs "unpaid"/"exposure"
- **Freshness** (20): same as jobs
- **Locality** (10): Twin Cities / Minnesota terms in text
- **Competition** (10): freshness-as-proxy for reply count
- Source quality (5)

Multiplicative model: `hygiene * skill_factor` with more aggressive floor
(0.10 vs 0.15 for jobs) — a gig you can't deliver is worthless.

### Pipeline changes
One change to the pipeline: `score_all()` loads the right profile/weights
per `listing_type`. The Collector, Vault, Translator, and Merger are unchanged.
Gig listings set `listing_type = "gig"` in the parser; everything else flows
through identically.

### UI
- Jobs/Gigs toggle in showroom filter panel (All / Jobs / Gigs)
- Filter applies to listing_type field

## Test results

| Source | Items | Status |
|---|---|---|
| r/forhire | 25 | Working |
| r/smallbusiness | 0 | 429 rate limit (needs spacing) |
| r/twincities | 0 | 429 rate limit (needs spacing) |
| r/minneapolis | 0 | 429 rate limit (needs spacing) |
| Craigslist (3 feeds) | 0 | 503 (Open RSS proxy down) |
| HN Freelancer | 182 | Working |
| Google Alerts | 0 | Blocked — no feed URLs yet |

Top gig: r/forhire WordPress/WooCommerce/Shopify developer (score 63.9).
Ranking is correct — web dev and React/Next.js gigs rank highest.

## What's blocked
- **Google Alerts**: need user's RSS feed URLs in `config/gig_feeds.yaml`
- **Craigslist**: Open RSS proxy returning 503 — may need alternative URLs
- **Reddit rate limiting**: 4 feeds in quick succession gets 429. The 2-second
  delay should fix it on the next run (hourly polling won't hit the limit)
