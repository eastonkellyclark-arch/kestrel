"""Seniority fit scorer (weight: 10).

Compares the listing title against the target seniority from the profile.
Target is "mid-senior" — mid and senior are both full-score. Staff/Principal/
Director are penalized. Intern/Junior are penalized.

Scoring:
  - mid (no marker, or explicit II): 100
  - senior/sr/lead: 100 (accepted range)
  - too senior (staff/principal/director/vp): 30
  - too junior (intern/junior/entry): 40
"""

import re

_SENIOR = re.compile(
    r"\b(senior|sr\.?|lead)\b",
    re.IGNORECASE,
)

_MID_EXPLICIT = re.compile(
    r"\b(mid[- ]?level|mid[- ]?senior|\bII\b|\b2\b(?!\d))\b",
    re.IGNORECASE,
)


def score(
    title: str,
    profile: dict,
) -> tuple[float, dict]:
    """Return (score 0-100, detail dict)."""
    seniority_cfg = profile.get("seniority", {})
    too_senior_terms = seniority_cfg.get("too_senior", [])
    too_junior_terms = seniority_cfg.get("too_junior", [])

    title_lower = title.lower()

    # Check explicit mid-level markers first
    if _MID_EXPLICIT.search(title):
        return 100.0, {"level": "mid_explicit"}

    # Check too-senior (staff, principal, director, etc.)
    for term in too_senior_terms:
        if re.search(r"\b" + re.escape(term.lower()) + r"\b", title_lower):
            return 30.0, {"level": "too_senior", "matched": term}

    # Check too-junior
    for term in too_junior_terms:
        if re.search(r"\b" + re.escape(term.lower()) + r"\b", title_lower):
            return 40.0, {"level": "too_junior", "matched": term}

    # Senior/Sr/Lead — accepted range, no penalty
    if _SENIOR.search(title):
        return 100.0, {"level": "senior"}

    # No seniority markers → assume mid-level
    return 100.0, {"level": "mid_implied"}
