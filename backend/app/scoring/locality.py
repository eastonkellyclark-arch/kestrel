"""Locality scorer for gigs (weight: 10).

Detects whether a gig is local (Twin Cities / Minnesota).
Local gigs are more deliverable and less competitive.

Scoring:
  - Twin Cities mention: 100
  - Minnesota mention: 80
  - US / Remote: 50
  - No location or international: 30
"""

import re


def score(
    title: str,
    description: str,
    location: str,
    profile: dict,
) -> tuple[float, dict]:
    locality_terms = profile.get("locality_terms", [])
    text = f"{title} {description} {location}".lower()

    for term in locality_terms:
        if term.lower() in text:
            return 100.0, {"locality": "local", "matched": term}

    if re.search(r"\b(remote|anywhere|usa|united states)\b", text, re.I):
        return 50.0, {"locality": "us_remote"}

    return 30.0, {"locality": "unknown"}
