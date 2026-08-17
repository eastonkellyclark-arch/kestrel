"""Description quality classifier.

Flags listings whose descriptions are empty, near-empty, just the title
repeated, or not in English. The scorer needs to handle these explicitly
rather than producing confident-looking numbers from nothing.
"""

import re

# Common English function words — if enough are present, it's English
_ENGLISH_MARKERS = {
    "the", "and", "you", "with", "for", "are", "will", "our", "this",
    "that", "your", "have", "from", "about", "team", "work", "experience",
    "role", "looking", "join", "ability", "responsibilities", "requirements",
    "must", "should", "including", "skills", "position", "company",
}
_MIN_ENGLISH_HITS = 5
_MIN_DESCRIPTION_LENGTH = 80  # characters
_WORD_RE = re.compile(r"[a-z]+")


def classify(description: str, title: str) -> str:
    """Return quality label: 'good', 'empty', 'title_only', 'non_english'."""
    if not description or not description.strip():
        return "empty"

    desc = description.strip()

    if len(desc) < _MIN_DESCRIPTION_LENGTH:
        return "empty"

    # Check if description is just the title repeated (possibly with minor wrapper text)
    title_lower = title.strip().lower()
    desc_lower = desc.lower()
    if title_lower and (
        desc_lower == title_lower
        or desc_lower.startswith(title_lower) and len(desc_lower) < len(title_lower) + 40
    ):
        return "title_only"

    # Language detection: count English function words
    words = set(_WORD_RE.findall(desc_lower))
    english_hits = len(words & _ENGLISH_MARKERS)
    if english_hits < _MIN_ENGLISH_HITS:
        return "non_english"

    return "good"
