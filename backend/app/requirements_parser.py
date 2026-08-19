"""Extract discrete requirements from job descriptions.

Pulls bulleted requirement lines and specific asks like
"3+ years React", "experience with CI/CD", "startup environment"
as a checklist. Partial extraction is fine — 6 of 8 is useful.
"""

import re

# Patterns for lines that look like requirements
_BULLET_LINE = re.compile(
    r"(?:^|\n)\s*(?:[-•*▪►◦]|\d+[.)]\s|[a-z][.)]\s)\s*(.+)",
    re.IGNORECASE,
)

# Patterns that indicate a requirements section
_REQ_HEADERS = re.compile(
    r"(?:requirements|qualifications|what you.ll bring|what we.re looking for|"
    r"must have|minimum qualifications|required skills|you have|ideal candidate|"
    r"what you need|basic qualifications)",
    re.IGNORECASE,
)

# Specific requirement patterns to extract even outside bullet lists
_SPECIFIC_REQS = [
    re.compile(r"(\d+\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:experience\s+(?:with|in)\s+)?[\w\s,/+.#]+)", re.I),
    re.compile(r"((?:experience|proficiency|expertise)\s+(?:with|in)\s+[\w\s,/+.#]+)", re.I),
    re.compile(r"((?:bachelor|master|phd|degree)\s+[\w\s]+)", re.I),
    re.compile(r"(familiarity with\s+[\w\s,/+.#]+)", re.I),
    re.compile(r"(strong\s+[\w\s]+\s+skills?)", re.I),
    re.compile(r"((?:knowledge|understanding)\s+of\s+[\w\s,/+.#]+)", re.I),
]


def extract_requirements(description: str) -> list[str]:
    """Extract a checklist of requirements from a job description.

    Returns a list of requirement strings, cleaned and deduplicated.
    """
    if not description:
        return []

    # Strip HTML tags for text analysis
    text = re.sub(r"<[^>]+>", "\n", description)
    text = re.sub(r"&\w+;", " ", text)

    requirements: list[str] = []
    seen_lower: set[str] = set()

    # Lines that aren't requirements
    _NOISE = re.compile(
        r"^(what you.ll|you.ll receive|about us|about the|we are|our team|"
        r"we offer|benefits|perks|why join|how to apply|equal opportunity|"
        r"we believe|this is a|the team|join us|apply now)",
        re.IGNORECASE,
    )

    def _add(req: str) -> None:
        cleaned = req.strip().rstrip(".,;:")
        if len(cleaned) < 10 or len(cleaned) > 200:
            return
        if _NOISE.search(cleaned):
            return
        lower = cleaned.lower()
        if lower in seen_lower:
            return
        seen_lower.add(lower)
        requirements.append(cleaned)

    # Strategy 1: find requirements section and extract bullet lines
    lines = text.split("\n")
    in_req_section = False
    for line in lines:
        stripped = line.strip()
        if _REQ_HEADERS.search(stripped):
            in_req_section = True
            continue
        # End section on next header-like line
        if in_req_section and stripped and not stripped[0] in "-•*▪►◦" and len(stripped) < 60:
            if stripped.endswith(":") or stripped.isupper():
                in_req_section = False
                continue
        if in_req_section and stripped:
            # Clean bullet prefix
            cleaned = re.sub(r"^[-•*▪►◦]\s*", "", stripped)
            cleaned = re.sub(r"^\d+[.)]\s*", "", cleaned)
            if cleaned:
                _add(cleaned)

    # Strategy 2: extract bullet lines from the whole description
    for m in _BULLET_LINE.finditer(text):
        _add(m.group(1))

    # Strategy 3: extract specific requirement patterns
    for pattern in _SPECIFIC_REQS:
        for m in pattern.finditer(text):
            _add(m.group(1))

    return requirements[:20]  # cap at 20 to avoid noise
