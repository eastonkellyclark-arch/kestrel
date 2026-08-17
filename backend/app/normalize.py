"""Company and title normalization for matching.

Display versions are preserved exactly as received.
Normalized versions are for dedupe and matching only.
"""

import re
import unicodedata


# Suffixes stripped for matching — order matters (longer first)
_COMPANY_SUFFIXES = re.compile(
    r"\s*,?\s*\b("
    r"incorporated|corporation|holdings|international|technologies|technology|"
    r"solutions|software|services|consulting|group|company|"
    r"inc\.?|corp\.?|llc\.?|ltd\.?|l\.?l\.?c\.?|co\.?"
    r")\s*\.?\s*$",
    re.IGNORECASE,
)

_WHITESPACE = re.compile(r"\s+")
_NON_ALNUM = re.compile(r"[^\w\s]", re.UNICODE)


def normalize_company(name: str) -> str:
    """Lowercase, strip suffixes and punctuation, collapse whitespace."""
    s = name.strip()
    s = unicodedata.normalize("NFKD", s)
    # Strip suffixes (may need multiple passes for "Inc. Corp.")
    for _ in range(3):
        s2 = _COMPANY_SUFFIXES.sub("", s)
        if s2 == s:
            break
        s = s2
    s = _NON_ALNUM.sub(" ", s)
    s = _WHITESPACE.sub(" ", s).strip().lower()
    return s


def normalize_title(title: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation for matching."""
    s = title.strip()
    s = unicodedata.normalize("NFKD", s)
    s = _NON_ALNUM.sub(" ", s)
    s = _WHITESPACE.sub(" ", s).strip().lower()
    return s
