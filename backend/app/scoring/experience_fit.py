"""Experience fit scorer.

Extracts years-of-experience requirements from descriptions and scores
the gap against the user's experience level from the profile.

Extraction patterns:
  "5+ years", "minimum 3 years", "2-4 years experience",
  "at least 7 years", "3 to 5 years"

Scoring (relative to user's experience):
  - At or below user's experience: 100
  - 1-2 years above: 70 (stretch but doable)
  - 3-4 years above: 40 (significant gap)
  - 5+ years above: 15 (probably filtered out anyway by seniority)
  - "No experience required" / "entry level": 100
  - Not mentioned: 60 (neutral)
"""

import re

# Patterns that extract a number of years
_YEAR_PATTERNS = [
    # "5+ years" / "5 years" / "5-7 years"
    re.compile(r"(\d+)\s*\+?\s*(?:years?|yrs?)(?:\s+of)?\s+(?:experience|exp)", re.I),
    # "minimum 3 years"
    re.compile(r"(?:minimum|at least|min)\s+(\d+)\s+(?:years?|yrs?)", re.I),
    # "2-4 years" / "2 to 4 years"
    re.compile(r"(\d+)\s*(?:-|to)\s*\d+\s+(?:years?|yrs?)", re.I),
    # "experience: 5 years"
    re.compile(r"experience\s*:\s*(\d+)\s+(?:years?|yrs?)", re.I),
]

# Explicit no-experience signals
_NO_EXPERIENCE = re.compile(
    r"\b("
    r"no experience (?:required|needed|necessary)|"
    r"0 years|zero years|"
    r"entry[- ]level|new grad|recent graduate|"
    r"internship|apprenticeship|"
    r"no prior experience|"
    r"will train|training provided"
    r")\b",
    re.IGNORECASE,
)


def extract_years(description: str) -> int | None:
    """Extract the minimum years of experience required. Returns None if not found."""
    if not description:
        return None

    # Check for no-experience first
    if _NO_EXPERIENCE.search(description):
        return 0

    # Find all year mentions and take the first (usually the requirement)
    for pattern in _YEAR_PATTERNS:
        m = pattern.search(description)
        if m:
            return int(m.group(1))

    return None


def score(
    experience_required: int | None,
    profile: dict,
) -> tuple[float, dict]:
    """Score the experience gap."""
    user_years = profile.get("experience_years", 1)

    if experience_required is None:
        return 60.0, {"experience": "not_mentioned"}

    if experience_required == 0:
        return 100.0, {"experience": "none_required", "required": 0}

    gap = experience_required - user_years
    if gap <= 0:
        return 100.0, {"experience": "at_or_below", "required": experience_required, "gap": 0}
    if gap <= 2:
        return 70.0, {"experience": "mild_stretch", "required": experience_required, "gap": gap}
    if gap <= 4:
        return 40.0, {"experience": "significant_gap", "required": experience_required, "gap": gap}
    return 15.0, {"experience": "heavy_gap", "required": experience_required, "gap": gap}
