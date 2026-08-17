"""Freshness scorer (weight: 15).

Newer postings score higher. Handles missing dates and stale re-posts.

Note: some Greenhouse first_published dates are months old — they may be
re-posts or long-running requisitions. We don't automatically tank them.
Instead:
  - < 7 days: 100
  - 7-14 days: 85
  - 14-30 days: 70
  - 30-60 days: 50
  - 60-90 days: 35
  - 90-180 days: 20 (likely re-post or evergreen)
  - > 180 days: 10 (definitely stale, but not zero — still a valid opening)
  - missing date: 40 (neutral, don't penalize the unknown)
"""

from datetime import datetime


def score(
    posted_at: str,
    now: datetime | None = None,
) -> tuple[float, dict]:
    """Return (score 0-100, detail dict)."""
    if now is None:
        now = datetime.utcnow()

    if not posted_at:
        return 40.0, {"days_old": None, "reason": "no_date"}

    try:
        posted = datetime.fromisoformat(posted_at[:19])
    except (ValueError, TypeError):
        return 40.0, {"days_old": None, "reason": "unparseable_date"}

    days_old = (now - posted).days

    if days_old < 0:
        # Future date — treat as very fresh (clock skew)
        return 100.0, {"days_old": days_old, "reason": "future_date"}

    if days_old <= 7:
        value = 100.0
    elif days_old <= 14:
        value = 85.0
    elif days_old <= 30:
        value = 70.0
    elif days_old <= 60:
        value = 50.0
    elif days_old <= 90:
        value = 35.0
    elif days_old <= 180:
        value = 20.0
    else:
        value = 10.0

    reason = "fresh" if days_old <= 14 else ("recent" if days_old <= 30 else (
        "aging" if days_old <= 90 else "stale"))

    return value, {"days_old": days_old, "reason": reason}
