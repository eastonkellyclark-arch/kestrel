"""Competition scorer for gigs (weight: 10).

Uses real bid counts when available (Freelancer.com stores bids in
the department field as "bids:N"). Falls back to freshness as proxy
when bid data isn't available.

Scoring:
  - 0-5 bids: 100 (low competition)
  - 6-15 bids: 70
  - 16-30 bids: 40
  - 30+ bids: 15 (heavily competed)

Freshness fallback:
  - < 1 day: 100 (few competitors yet)
  - 1-3 days: 80
  - 3-7 days: 60
  - 1-2 weeks: 30
  - > 2 weeks: 10
  - Unknown: 50
"""

from datetime import datetime


def score(
    posted_at: str,
    now: datetime | None = None,
    bid_count: int | None = None,
) -> tuple[float, dict]:
    if now is None:
        now = datetime.utcnow()

    # Use real bid count when available (Freelancer.com)
    if bid_count is not None:
        if bid_count <= 5:
            return 100.0, {"competition": "low", "bids": bid_count}
        if bid_count <= 15:
            return 70.0, {"competition": "moderate", "bids": bid_count}
        if bid_count <= 30:
            return 40.0, {"competition": "high", "bids": bid_count}
        return 15.0, {"competition": "saturated", "bids": bid_count}

    # Freshness fallback for sources without bid data
    if not posted_at:
        return 50.0, {"competition": "unknown"}

    try:
        posted = datetime.fromisoformat(posted_at[:19])
    except (ValueError, TypeError):
        return 50.0, {"competition": "unknown"}

    hours_old = (now - posted).total_seconds() / 3600

    if hours_old < 24:
        return 100.0, {"competition": "very_low", "hours_old": round(hours_old)}
    if hours_old < 72:
        return 80.0, {"competition": "low", "hours_old": round(hours_old)}
    if hours_old < 168:
        return 60.0, {"competition": "moderate", "hours_old": round(hours_old)}
    if hours_old < 336:
        return 30.0, {"competition": "high", "hours_old": round(hours_old)}
    return 10.0, {"competition": "saturated", "hours_old": round(hours_old)}
