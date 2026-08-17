"""Degree posture scorer (weight: 20).

Detects three postures:
  - hard_requirement: "Bachelor's degree required", "BS/MS required"
  - equivalent_ok: "or equivalent experience", "degree preferred"
  - no_degree: "no degree required", degree not mentioned at all

Scoring: no_degree → 100, equivalent_ok → 70, hard_requirement → 20
Missing/low-quality description → 50 (neutral, don't penalize the unknown)
"""

import re

_HARD_DEGREE = re.compile(
    r"\b("
    r"(?:bachelor'?s?|master'?s?|phd|doctorate|b\.?s\.?|m\.?s\.?|b\.?a\.?|m\.?a\.?)"
    r"\s+(?:degree\s+)?(?:required|is required|mandatory|must have|minimum)"
    r"|"
    r"(?:bachelor'?s?|master'?s?)\s+degree\s+(?:required|is required|in\b)"
    r"|"
    r"(?:required|minimum)\s*:?\s*(?:bachelor|master|b\.?s\.?|m\.?s\.?)"
    r"|"
    r"must (?:have|hold|possess)\s+(?:a\s+)?(?:bachelor'?s?|master'?s?|b\.?s\.?|m\.?s\.?)"
    r")\b",
    re.IGNORECASE,
)

_EQUIVALENT_OK = re.compile(
    r"\b("
    r"or\s+equivalent\s+(?:experience|work experience|professional experience|combination)"
    r"|"
    r"(?:bachelor|degree)\s+(?:preferred|desired|or equivalent)"
    r"|"
    r"equivalent\s+(?:work\s+)?experience\s+(?:accepted|considered|in lieu)"
    r"|"
    r"degree\s+or\s+(?:relevant|related|equivalent|comparable)\s+experience"
    r"|"
    r"in lieu of (?:a )?degree"
    r")\b",
    re.IGNORECASE,
)

_NO_DEGREE = re.compile(
    r"\b("
    r"no\s+degree\s+required"
    r"|"
    r"degree\s+not\s+required"
    r"|"
    r"without\s+a\s+degree"
    r"|"
    r"don'?t\s+need\s+a\s+degree"
    r")\b",
    re.IGNORECASE,
)

# Generic degree mention (for detecting "degree mentioned at all")
_ANY_DEGREE = re.compile(
    r"\b(?:bachelor|master|phd|doctorate|degree|b\.?s\.?|m\.?s\.?|b\.?a\.?|m\.?a\.?)\b",
    re.IGNORECASE,
)


def score(
    description: str,
    description_quality: str,
) -> tuple[float, dict]:
    """Return (score 0-100, detail dict)."""
    if description_quality != "good":
        return 50.0, {"posture": "unknown", "reason": f"description_quality={description_quality}"}

    # Check patterns in order of specificity
    if _NO_DEGREE.search(description):
        return 100.0, {"posture": "no_degree"}

    if _EQUIVALENT_OK.search(description):
        return 70.0, {"posture": "equivalent_ok"}

    if _HARD_DEGREE.search(description):
        return 20.0, {"posture": "hard_requirement"}

    # No degree mentioned at all — treat as no requirement
    if not _ANY_DEGREE.search(description):
        return 90.0, {"posture": "not_mentioned"}

    # Degree mentioned but not in a clear pattern — assume soft preference
    return 60.0, {"posture": "mentioned_unclear"}
