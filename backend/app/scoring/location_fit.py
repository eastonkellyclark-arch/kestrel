"""Location fit scorer (weight: 15).

Qualifies if within onsite radius of home OR US-remote.
Uses simple heuristics on the location string — no geocoding API (cost rule).

Scoring:
  - US Remote: 90 (great fit)
  - Within metro (TC area detected): 100
  - US but not metro, not remote: 40 (relocation consideration)
  - Non-US remote: 15 (usually not eligible)
  - Non-US onsite: 5 (not viable)
  - Unknown/ambiguous: 30
"""

import re

# Twin Cities metro area indicators
_TC_METRO = re.compile(
    r"\b("
    r"Minneapolis|Saint Paul|St\.?\s*Paul|Farmington|Eagan|Bloomington|"
    r"Eden Prairie|Minnetonka|Plymouth|Maple Grove|Edina|"
    r"Burnsville|Lakeville|Woodbury|Roseville|Brooklyn Park|"
    r"Richfield|Golden Valley|Hopkins|Fridley|Coon Rapids|"
    r"Shakopee|Prior Lake|Savage|Apple Valley"
    r")\b",
    re.IGNORECASE,
)

_MINNESOTA = re.compile(r"\bMN\b|\bMinnesota\b", re.IGNORECASE)

_US_REMOTE = re.compile(
    r"\b("
    r"US\s+Remote|U\.?S\.?\s+Remote|United\s+States.*Remote|Remote.*United\s+States|"
    r"Remote.*US\b|Remote,?\s*US\b|Remote\s*-\s*US"
    r")\b",
    re.IGNORECASE,
)

_US_LOCATION = re.compile(
    r"\b("
    r"United States|USA|"
    r"(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)\b|"
    r"San Francisco|New York|Austin|Denver|Chicago|Seattle|Boston|Portland|"
    r"Atlanta|Los Angeles|Washington|Phoenix|Dallas|Houston|Philadelphia|"
    r"San Diego|San Jose|Salt Lake"
    r")\b",
    re.IGNORECASE,
)

_REMOTE_ANYWHERE = re.compile(
    r"\b(Remote|Distributed|Anywhere)\b",
    re.IGNORECASE,
)

_NON_US_INDICATORS = re.compile(
    r"\b("
    r"United Kingdom|UK\b|London|Berlin|Paris|Tokyo|Sydney|Singapore|"
    r"India|Brazil|Colombia|Mexico|Chile|Argentina|Canada|"
    r"Türkiye|Turkey|Poland|Australia|Germany|France|Japan|"
    r"Netherlands|Ireland|Israel|South Korea|"
    r"Latin America|EMEA|APAC|Bogota|Mumbai|Pune|Dhaka|"
    r"Remote,?\s*(?:India|UK|Germany|France|Australia|Singapore|Canada|Brazil|"
    r"Colombia|Mexico|Chile|Argentina|Israel|Japan|Netherlands|Ireland|Poland|Turkey)"
    r")\b",
    re.IGNORECASE,
)


def score(
    location: str,
    is_remote: bool,
) -> tuple[float, dict]:
    """Return (score 0-100, detail dict)."""
    if not location:
        return 30.0, {"fit": "unknown", "reason": "no_location"}

    loc = location.strip()

    # Check for TC metro
    if _TC_METRO.search(loc):
        return 100.0, {"fit": "metro", "reason": "Twin Cities area"}

    # Check for Minnesota generally
    if _MINNESOTA.search(loc):
        return 95.0, {"fit": "state", "reason": "Minnesota"}

    # Check for US Remote
    if _US_REMOTE.search(loc):
        return 90.0, {"fit": "us_remote"}

    # "Remote" without US qualifier but also has US location mentioned
    if _REMOTE_ANYWHERE.search(loc) and _US_LOCATION.search(loc):
        return 85.0, {"fit": "us_remote_inferred"}

    # Non-US check
    if _NON_US_INDICATORS.search(loc):
        if is_remote:
            return 15.0, {"fit": "non_us_remote"}
        return 5.0, {"fit": "non_us_onsite"}

    # "Remote" / "Distributed" without clear country
    if is_remote and _REMOTE_ANYWHERE.search(loc):
        return 60.0, {"fit": "remote_ambiguous", "reason": "Remote but country unclear"}

    # US location, not metro, not remote
    if _US_LOCATION.search(loc):
        return 40.0, {"fit": "us_not_metro"}

    return 30.0, {"fit": "unknown"}
