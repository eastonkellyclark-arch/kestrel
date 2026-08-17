"""Remote work detection heuristic.

This is a known-hard problem (CLAUDE.md). No source reliably flags remote.
The heuristic scores signals from location, title, and description text.

Returns (is_remote: bool, confidence: float) where confidence is 0.0–1.0.

Confidence thresholds:
  >= 0.7  → classified remote
  <  0.7  → classified not remote

Signals are additive (positive evidence) and subtractive (counter-evidence).
"""

import re

# --- Positive signals (evidence of remote) ---

_REMOTE_LOCATION = re.compile(
    r"\b("
    r"remote|anywhere|distributed|work\s+from\s+home|wfh|"
    r"fully\s+remote|100%\s+remote|all\s+remote"
    r")\b",
    re.IGNORECASE,
)

_REMOTE_TITLE = re.compile(
    r"\b("
    r"remote|distributed"
    r")\b"
    r"|"
    r"\(\s*remote\s*\)|\[\s*remote\s*\]",
    re.IGNORECASE,
)

_REMOTE_DESCRIPTION = re.compile(
    r"\b("
    r"fully\s+remote|100%\s+remote|remote\s+first|remote-first|"
    r"work\s+from\s+anywhere|work\s+remotely|"
    r"this\s+(is\s+a\s+|position\s+is\s+)?remote\s+(position|role|job|opportunity)|"
    r"location:\s*remote|"
    r"remote\s+within\s+the\s+(us|u\.?s\.?|united\s+states)|"
    r"open\s+to\s+remote|remote\s+eligible"
    r")\b",
    re.IGNORECASE,
)

# --- Negative signals (evidence against remote) ---

_NOT_REMOTE = re.compile(
    r"\b("
    r"not\s+remote|no\s+remote|on-?\s*site\s+only|in-?\s*office\s+only|"
    r"must\s+be\s+(located|based)\s+(in|at|near)|"
    r"relocation\s+required|this\s+is\s+not\s+a\s+remote|"
    r"no\s+remote\s+work|office-?\s*based\s+only"
    r")\b",
    re.IGNORECASE,
)

_HYBRID = re.compile(
    r"\b("
    r"hybrid|in-?\s*office\s+\d|days?\s+(in|at)\s+(the\s+)?office|"
    r"on-?\s*site\s+\d\s+days?"
    r")\b",
    re.IGNORECASE,
)

# Lever provides workplaceType directly
_LEVER_WORKPLACE_REMOTE = {"remote"}
_LEVER_WORKPLACE_NOT_REMOTE = {"onsite", "on-site", "unspecified"}


def detect_remote(
    location: str = "",
    title: str = "",
    description: str = "",
    workplace_type: str = "",
) -> tuple[bool, float]:
    """Return (is_remote, confidence) based on available signals."""
    score = 0.0
    location_says_remote = False

    # Location field first — this is a short, structured ATS field. If it says
    # "Remote", that's intentional and authoritative. Other signals (including
    # Lever's workplaceType, which sometimes contradicts the location) must not
    # override an explicit location match.
    if location:
        if _REMOTE_LOCATION.search(location):
            score += 0.7
            location_says_remote = True
        if _NOT_REMOTE.search(location):
            score -= 0.5
            location_says_remote = False
        loc_lower = location.strip().lower()
        if loc_lower in ("hybrid", "in-office", "in office", "on-site", "onsite"):
            score -= 0.3

    # Lever's workplaceType — useful when location is ambiguous, but don't let
    # it contradict an explicit "Remote, <place>" location.
    wt = workplace_type.strip().lower()
    if wt in _LEVER_WORKPLACE_REMOTE:
        score += 0.8
        location_says_remote = True
    elif not location_says_remote:
        if wt == "hybrid":
            score -= 0.2
        elif wt in _LEVER_WORKPLACE_NOT_REMOTE:
            score -= 0.3

    # Title
    if title:
        if _REMOTE_TITLE.search(title):
            score += 0.3
        if _NOT_REMOTE.search(title):
            score -= 0.4

    # Description (weakest individual signal, but often the only one)
    if description:
        if _REMOTE_DESCRIPTION.search(description):
            score += 0.3
        # Only apply description-level penalties when the location field
        # didn't already say "Remote". Incidental mentions of "hybrid" or
        # "must be based in" in long descriptions were causing false negatives
        # for listings whose structured location explicitly says Remote.
        if not location_says_remote:
            if _NOT_REMOTE.search(description):
                score -= 0.5
            if _HYBRID.search(description):
                score -= 0.15

    # Clamp to [0, 1]
    confidence = max(0.0, min(1.0, score))

    return (confidence >= 0.7, confidence)
