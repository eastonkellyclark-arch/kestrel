"""Budget signal scorer for gigs (weight: 25).

Detects whether a gig post mentions a real budget.
Positive: dollar amounts, "per hour", "fixed price", "retainer"
Negative: "unpaid", "exposure", "equity only"

Scoring:
  - Explicit dollar amount: 100
  - Budget-positive phrases: 80
  - No budget mentioned: 40
  - Budget-negative (unpaid/exposure): 10
"""

import re


def score(
    title: str,
    description: str,
    profile: dict,
) -> tuple[float, dict]:
    budget_cfg = profile.get("budget_signals", {})
    positive = budget_cfg.get("positive", [])
    negative = budget_cfg.get("negative", [])

    text = f"{title} {description}".lower()

    # Check for dollar amounts first (strongest signal)
    if re.search(r"\$\s*\d+", text):
        return 100.0, {"signal": "dollar_amount"}

    # Check negative signals
    for term in negative:
        if term.lower() in text:
            return 10.0, {"signal": "negative", "matched": term}

    # Check positive signals
    for term in positive:
        if term.lower() in text:
            return 80.0, {"signal": "positive", "matched": term}

    return 40.0, {"signal": "none"}
