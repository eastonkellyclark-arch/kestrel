"""Skill match scorer (weight: 35).

Scans title and description for skills from the profile.
Primary skills score highest, then secondary, then bonus.
"""

import re


def _find_skills(text: str, skill_list: list[str]) -> list[str]:
    """Return which skills from skill_list appear in text."""
    text_lower = text.lower()
    found = []
    for skill in skill_list:
        # Word-boundary match, handling special chars like c++, next.js
        escaped = re.escape(skill.lower())
        if re.search(r"(?<!\w)" + escaped + r"(?!\w)", text_lower):
            found.append(skill)
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

    # For low-quality descriptions, score on title only with a penalty
    text = title
    quality_penalty = 0.0
    if description_quality == "good":
        text = f"{title} {description}"
    else:
        quality_penalty = 0.3  # can only reach 70% of max

    found_primary = _find_skills(text, primary)
    found_secondary = _find_skills(text, secondary)
    found_bonus = _find_skills(text, bonus)

    # Score: primary matches are worth the most
    primary_score = len(found_primary) / max(len(primary), 1) * 60
    secondary_score = len(found_secondary) / max(len(secondary), 1) * 30
    bonus_score = len(found_bonus) / max(len(bonus), 1) * 10

    raw = min(100.0, primary_score + secondary_score + bonus_score)
    final = raw * (1.0 - quality_penalty)

    return final, {
        "primary_hits": found_primary,
        "secondary_hits": found_secondary,
        "bonus_hits": found_bonus,
        "quality_penalty": quality_penalty > 0,
    }
