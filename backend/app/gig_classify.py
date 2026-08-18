"""Classifies gig posts as demand (someone hiring) vs supply (someone advertising).

Returns (classification, confidence):
  - ("demand", 1.0)   — explicit [HIRING] tag, definitive
  - ("supply", 1.0)   — explicit [FOR HIRE] tag, definitive
  - ("demand", 0.7)   — demand language without supply language
  - ("supply", 0.7)   — supply language without demand language
  - ("demand", 0.5)   — more demand phrases than supply
  - ("ambiguous", 0.3) — can't tell

Confidence shown in the desk so ambiguous cases can be eyeballed.
"""

import re

# Layer 1: explicit tags (strongest signal)
_DEMAND_TAGS = re.compile(
    r"\[(?:hiring|seeking freelancer|seeking a freelancer|looking for)\]",
    re.IGNORECASE,
)
_SUPPLY_TAGS = re.compile(
    r"\[(?:for hire|seeking work|available|freelancer available)\]",
    re.IGNORECASE,
)

# Layer 2: demand language (someone needs work done)
_DEMAND_PHRASES = re.compile(
    r"\b("
    r"i need|we need|looking for a|looking for an|seeking a|seeking an|"
    r"we'?re hiring|we'?re looking|want to hire|need someone|"
    r"help (?:me|us) (?:build|create|design|develop|set up)|"
    r"need a (?:website|developer|designer|freelancer|contractor)|"
    r"our (?:company|startup|business|team) (?:needs|is looking)|"
    r"budget is|willing to pay|pay(?:ing)? \$|rate is \$|"
    r"project for|contract work available"
    r")\b",
    re.IGNORECASE,
)

# Layer 3: supply language (someone is advertising themselves)
_SUPPLY_PHRASES = re.compile(
    r"\b("
    r"i am a|i'?m a (?:developer|designer|freelancer|engineer)|"
    r"i offer|i provide|i specialize|i can (?:build|create|design|develop|help)|"
    r"my (?:rates?|portfolio|services?|experience)|"
    r"hire me|available for (?:work|hire|projects|freelance)|"
    r"open to (?:work|opportunities|freelance)|"
    r"looking for (?:work|opportunities|clients|projects|a job|employment)|"
    r"check out my|visit my (?:portfolio|website|github)|"
    r"years? of experience|(?:senior|junior|mid) (?:developer|designer|engineer)"
    r")\b",
    re.IGNORECASE,
)


def classify(title: str, description: str) -> tuple[str, float]:
    """Return (classification, confidence).

    classification: 'demand', 'supply', or 'ambiguous'
    confidence: 0.0-1.0
    """
    text = f"{title} {description}"

    # Layer 1: explicit tags are definitive
    if _DEMAND_TAGS.search(title):
        return "demand", 1.0
    if _SUPPLY_TAGS.search(title):
        return "supply", 1.0

    # Layer 2 & 3: count phrase matches
    demand_hits = len(_DEMAND_PHRASES.findall(text))
    supply_hits = len(_SUPPLY_PHRASES.findall(text))

    if demand_hits > 0 and supply_hits == 0:
        return "demand", 0.7
    if supply_hits > 0 and demand_hits == 0:
        return "supply", 0.7
    if demand_hits > supply_hits:
        return "demand", 0.5
    if supply_hits > demand_hits:
        return "supply", 0.5

    # Both present equally, or neither
    if demand_hits > 0:
        return "ambiguous", 0.3
    return "ambiguous", 0.3
