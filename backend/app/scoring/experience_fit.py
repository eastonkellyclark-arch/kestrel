"""Experience fit scorer.

Extracts years-of-experience requirements from descriptions and scores
the gap against the user's experience level from the profile.

Scoring (relative to user's experience):
  - Explicit "no experience required": 100
  - At or below user's experience: 100
  - 1-2 years above: 70 (stretch but doable)
  - 3-4 years above: 40 (significant gap)
  - 5+ years above: 15 (heavy gap)
  - Not mentioned: 50 (neutral — could be 0 or could be 5 phrased
    in a way the regex missed. Don't reward the unknown.)
"""

import re

# Spelled-out numbers
_WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}
_WORD_NUM_RE = re.compile(
    r"\b(" + "|".join(_WORD_NUMBERS.keys()) + r")\s+(?:years?|yrs?)(?:\s+of)?\s+(?:experience|exp)",
    re.IGNORECASE,
)

# Numeric patterns — ORDER MATTERS: ranges before single numbers
_YEAR_PATTERNS = [
    # "2-4 years" / "2 to 4 years" (takes the lower bound) — BEFORE single number
    re.compile(r"(\d+)\s*(?:-|to)\s*\d+\s+(?:years?|yrs?)", re.I),
    # "minimum 3 years" / "at least 7 years" / "min 2 years"
    re.compile(r"(?:minimum|at least|min\.?)\s+(\d+)\s+(?:years?|yrs?)", re.I),
    # "requires 3 years" / "requiring 5 years"
    re.compile(r"requir(?:es|ing|ed)\s+(\d+)\s+(?:years?|yrs?)", re.I),
    # "experience: 5 years" / "experience: 5+ years"
    re.compile(r"experience\s*:\s*(\d+)\s*\+?\s*(?:years?|yrs?)", re.I),
    # "5+ years of experience" / "5 years experience" — last, most generic
    re.compile(r"(\d+)\s*\+?\s*(?:years?|yrs?)(?:\s+of)?\s+(?:experience|exp)", re.I),
]

# Explicit no-experience signals
_NO_EXPERIENCE = re.compile(
    r"\b("
    r"no experience (?:required|needed|necessary)|"
    r"0 years|zero years|"
    r"entry[- ]level|new grad(?:uate)?|recent graduate|"
    r"internship|apprenticeship|"
    r"no prior experience|"
    r"will train|training provided|"
    r"no (?:previous |prior )?experience (?:required|needed|necessary)"
    r")\b",
    re.IGNORECASE,
)


def extract_years(description: str) -> int | None:
    """Extract the minimum years of experience required.

    Returns:
      0 — explicit "no experience required"
      N — N years required
      None — not mentioned (unknown, NOT the same as 0)
    """
    if not description:
        return None

    # Check for no-experience first
    if _NO_EXPERIENCE.search(description):
        return 0

    # Spelled-out numbers: "five years of experience"
    m = _WORD_NUM_RE.search(description)
    if m:
        return _WORD_NUMBERS[m.group(1).lower()]

    # Numeric patterns
    for pattern in _YEAR_PATTERNS:
        m = pattern.search(description)
        if m:
            return int(m.group(1))

    return None


def score(
    experience_required: int | None,
    profile: dict,
) -> tuple[float, dict]:
    """Score the experience gap.

    NULL (not mentioned) scores 50 — neutral, not favorable.
    This is honest: "not stated" could mean 0 or could mean 5 years
    phrased in a way the regex missed. Don't reward the unknown.
    """
    user_years = profile.get("experience_years", 1)

    if experience_required is None:
        return 50.0, {"experience": "not_mentioned"}

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
