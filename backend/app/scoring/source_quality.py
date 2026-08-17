"""Source quality scorer (weight: 5).

Rewards direct-employer postings over agency reposts.
ATS boards (Greenhouse, Lever) are direct-employer by definition.
Aggregators and feeds score lower.

Scoring:
  - greenhouse, lever: 100 (direct employer)
  - usajobs: 90 (direct, structured)
  - remoteok, remotive, weworkremotely: 70 (curated feeds)
  - adzuna: 50 (aggregator, truncated descriptions)
  - gmail_alert: 60 (from employer but via alert, often truncated)
  - google_alerts_rss, reddit, craigslist: 40 (gig sources, noisy)
"""

SOURCE_SCORES = {
    "greenhouse": 100,
    "lever": 100,
    "usajobs": 90,
    "remoteok": 70,
    "remotive": 70,
    "weworkremotely": 70,
    "gmail_alert": 60,
    "adzuna": 50,
    "google_alerts_rss": 40,
    "reddit": 40,
    "craigslist": 40,
}


def score(source: str) -> tuple[float, dict]:
    """Return (score 0-100, detail dict)."""
    value = SOURCE_SCORES.get(source, 50)
    return float(value), {"source": source, "tier": "direct" if value >= 90 else (
        "curated" if value >= 70 else "aggregator")}
