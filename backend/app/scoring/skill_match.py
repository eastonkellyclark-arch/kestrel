"""Skill match scorer.

Scans title and description for skills from the profile.
Primary skills score highest, then secondary, then bonus.
Synonyms loaded from profile.yaml. Title mentions get 2x weight.
"""

import re


def _find_skills(text: str, skill_list: list[str], synonyms: dict) -> list[str]:
    """Return which skills from skill_list appear in text."""
    text_lower = text.lower()
    found = []
    for skill in skill_list:
        escaped = re.escape(skill.lower())
        if re.search(r"(?<!\w)" + escaped + r"(?!\w)", text_lower):
            found.append(skill)
            continue
        for syn in synonyms.get(skill.lower(), []):
            escaped_syn = re.escape(syn)
            if re.search(r"(?<!\w)" + escaped_syn + r"(?!\w)", text_lower):
                found.append(skill)
                break
    return found


def score(
    title: str,
    description: str,
    description_quality: str,
    profile: dict,
) -> tuple[float, dict]:
    """Return (score 0-100, detail dict)."""
    primary = profile.get("skills", {}).get("primary", [])
    secondary = profile.get("skills", {}).get("secondary", [])
    bonus = profile.get("skills", {}).get("bonus", [])
    synonyms = profile.get("skills", {}).get("synonyms", {})

    # Supply posts (competitors advertising) get zero skill score —
    # they match skills precisely because they're competitors, not clients.
    if description_quality == "supply_post":
        return 0.0, {
            "primary_hits": [], "secondary_hits": [], "bonus_hits": [],
            "title_hits": [], "quality_penalty": True,
            "supply_post": True,
        }

    quality_penalty = 0.0
    if description_quality in ("good", "truncated"):
        full_text = f"{title} {description}"
        if description_quality == "truncated":
            quality_penalty = 0.15  # lighter penalty — real content, just less of it
    else:
        full_text = title
        quality_penalty = 0.3  # empty/non_english/filtered — title only

    found_primary = _find_skills(full_text, primary, synonyms)
    found_secondary = _find_skills(full_text, secondary, synonyms)
    found_bonus = _find_skills(full_text, bonus, synonyms)

    # Title-weight boosting: skills in the title count double.
    # A role titled "React Developer" is a stronger match than one that
    # mentions React once in a requirements list.
    title_primary = _find_skills(title, primary, synonyms)
    title_secondary = _find_skills(title, secondary, synonyms)
    title_bonus = _find_skills(title, bonus, synonyms)

    # Effective hit count: base + 1 extra for each title hit
    primary_effective = len(found_primary) + len(title_primary)
    secondary_effective = len(found_secondary) + len(title_secondary)
    bonus_effective = len(found_bonus) + len(title_bonus)

    primary_score = primary_effective / max(len(primary), 1) * 60
    secondary_score = secondary_effective / max(len(secondary), 1) * 30
    bonus_score = bonus_effective / max(len(bonus), 1) * 10

    raw = min(100.0, primary_score + secondary_score + bonus_score)
    final = raw * (1.0 - quality_penalty)

    return final, {
        "primary_hits": found_primary,
        "secondary_hits": found_secondary,
        "bonus_hits": found_bonus,
        "title_hits": title_primary + title_secondary + title_bonus,
        "quality_penalty": quality_penalty > 0,
    }
