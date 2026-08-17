"""Seniority fit scorer (weight: 10).

Compares the listing title against the target seniority from the profile.
Target is "mid" — penalizes titles that are clearly too senior or too junior.

Scoring:
  - mid-level match (default, no markers): 100
  - senior (one step above): 70
  - too senior (staff/principal/director): 30
  - too junior (intern/junior/entry): 40
  - explicit "mid" or "II" marker: 100
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

    # Check too-senior
    for term in too_senior_terms:
        if re.search(r"\b" + re.escape(term.lower()) + r"\b", title_lower):
            return 30.0, {"level": "too_senior", "matched": term}

    # Check too-junior
    for term in too_junior_terms:
        if re.search(r"\b" + re.escape(term.lower()) + r"\b", title_lower):
            return 40.0, {"level": "too_junior", "matched": term}

    # Check regular senior (one step above mid, still viable)
    if _SENIOR.search(title):
        return 70.0, {"level": "senior"}

    # No seniority markers → assume mid-level
    return 90.0, {"level": "mid_implied"}
