"""Classifies gig posts as demand (someone hiring) vs supply (someone advertising).

Competitors posting "[FOR HIRE] I'm a React developer" match the same keywords
as real gigs — skill scoring can't tell them apart. This filter separates them
before scoring so only demand posts become scored listings.

Supply posts are stored in the vault and translated, but marked
description_quality="supply_post" so the scorer treats them as zero-value.

Three detection layers:
1. Explicit tags: [HIRING] vs [FOR HIRE], [SEEKING FREELANCER] vs [SEEKING WORK]
2. Demand language: "I need", "looking for", "we're hiring", budget mentions
3. Supply language: "I am a", "I offer", "my rates", "portfolio"
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


def classify(title: str, description: str) -> str:
    """Return 'demand', 'supply', or 'ambiguous'.

    demand = someone wants to hire (this is a real gig)
    supply = someone advertising themselves (competitor)
    ambiguous = can't tell (score normally, lower confidence)
    """
    text = f"{title} {description}"

    # Layer 1: explicit tags are definitive
    if _DEMAND_TAGS.search(title):
        return "demand"
    if _SUPPLY_TAGS.search(title):
        return "supply"

    # Layer 2 & 3: count phrase matches
    demand_hits = len(_DEMAND_PHRASES.findall(text))
    supply_hits = len(_SUPPLY_PHRASES.findall(text))

    if demand_hits > 0 and supply_hits == 0:
        return "demand"
    if supply_hits > 0 and demand_hits == 0:
        return "supply"
    if demand_hits > supply_hits:
        return "demand"
    if supply_hits > demand_hits:
        return "supply"

    return "ambiguous"
