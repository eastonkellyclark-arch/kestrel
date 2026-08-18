"""Competition scorer for gigs (weight: 10).

Estimates competition based on signals in the post.
Lower competition = higher score.

On Reddit/HN, reply counts indicate competition.
On Google Alerts/Craigslist, freshness is the best proxy.

Scoring:
  - Very fresh (< 1 day): 100 (few competitors yet)
  - Fresh (1-3 days): 80
  - Recent (3-7 days): 60
  - Older (1-2 weeks): 30
  - Stale (> 2 weeks): 10
  - Unknown: 50
"""

from datetime import datetime


def score(
    posted_at: str,
    now: datetime | None = None,
) -> tuple[float, dict]:
    if now is None:
        now = datetime.utcnow()

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
