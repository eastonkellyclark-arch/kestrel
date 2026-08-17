"""The Judge — composite scorer.

Loads profile and weights from YAML, runs all six dimension scorers,
computes a weighted composite, and stores the result with its breakdown.

Dealbreakers are hard filters applied before scoring. A listing that
matches a dealbreaker gets score 0 regardless of other dimensions.
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path

import yaml

from ..database import get_connection
from . import (
    degree_posture,
    freshness,
    location_fit,
    seniority_fit,
    skill_match,
    source_quality,
)

logger = logging.getLogger("kestrel.judge")

_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent.parent / "config"


def _load_yaml(filename: str) -> dict:
    path = _CONFIG_DIR / filename
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _check_dealbreakers(title: str, description: str, dealbreakers: list[str]) -> str | None:
    """Return the matched dealbreaker term, or None."""
    text = f"{title} {description}".lower()
    for term in dealbreakers:
        if re.search(r"\b" + re.escape(term.lower()) + r"\b", text):
            return term
    return None


def score_listing(row: dict, profile: dict, weights: dict, now: datetime) -> tuple[float, dict]:
    """Score a single listing. Returns (composite_score, breakdown_dict)."""
    dealbreakers = profile.get("dealbreakers", [])
    deal = _check_dealbreakers(
        row["title_display"], row["description"] or "", dealbreakers
    )
    if deal:
        return 0.0, {
            "dealbreaker": deal,
            "skill_match": 0, "degree_posture": 0, "freshness": 0,
            "location_fit": 0, "seniority_fit": 0, "source_quality": 0,
        }

    sm_score, sm_detail = skill_match.score(
        row["title_display"], row["description"] or "",
        row["description_quality"], profile,
    )
    dp_score, dp_detail = degree_posture.score(
        row["description"] or "", row["description_quality"],
    )
    fr_score, fr_detail = freshness.score(row["posted_at"], now)
    lf_score, lf_detail = location_fit.score(
        row["location_display"] or "", bool(row["is_remote"]),
    )
    sf_score, sf_detail = seniority_fit.score(row["title_display"], profile)
    sq_score, sq_detail = source_quality.score(row["source"])

    hygiene_dims = {
        "degree_posture": dp_score,
        "freshness": fr_score,
        "location_fit": lf_score,
        "seniority_fit": sf_score,
        "source_quality": sq_score,
    }

    # Hygiene score: weighted average of the five acceptability dimensions
    hygiene_weights = {k: weights[k] for k in hygiene_dims if k in weights}
    hygiene_total = sum(hygiene_weights.values())
    hygiene_score = sum(
        hygiene_dims[dim] * hygiene_weights[dim] / hygiene_total
        for dim in hygiene_dims
    )

    # Skill factor: multiplicative, not additive.
    # factor = floor + (1 - floor) * (skill_score / 100) ^ exponent
    # Tunable via weights.yaml: skill_floor and skill_exponent.
    skill_floor = weights.get("skill_floor", 0.15)
    skill_exponent = weights.get("skill_exponent", 0.6)
    if sm_score <= 0:
        skill_factor = skill_floor
    else:
        skill_factor = skill_floor + (1.0 - skill_floor) * (sm_score / 100.0) ** skill_exponent

    composite = hygiene_score * skill_factor

    # Express the scaling as a readable percentage
    scale_pct = round(skill_factor * 100)

    breakdown = {
        "composite": round(composite, 2),
        "hygiene_score": round(hygiene_score, 1),
        "skill_factor": round(skill_factor, 3),
        "scale_label": f"scaled to {scale_pct}% for {'strong' if scale_pct >= 80 else ('moderate' if scale_pct >= 50 else 'low')} skill fit",
        "dimensions": {
            "skill_match": {"score": round(sm_score, 1)},
            **{
                dim: {"score": round(hygiene_dims[dim], 1), "weight": weights.get(dim, 0)}
                for dim in hygiene_dims
            },
        },
        "detail": {
            "skill_match": sm_detail,
            "degree_posture": dp_detail,
            "freshness": fr_detail,
            "location_fit": lf_detail,
            "seniority_fit": sf_detail,
            "source_quality": sq_detail,
        },
    }

    return round(composite, 2), breakdown


def score_all() -> dict:
    """Score every canonical listing. Returns stats."""
    profile = _load_yaml("profile.yaml")
    weights = _load_yaml("weights.yaml")
    now = datetime.utcnow()

    conn = get_connection()
    rows = conn.execute(
        """
        SELECT id, title_display, company_display, location_display,
               description, description_quality, posted_at, source,
               is_remote
        FROM listings
        WHERE canonical_id IS NULL
        """
    ).fetchall()
    conn.close()

    stats = {"total": len(rows), "scored": 0, "dealbreakers": 0}

    conn = get_connection()
    for row in rows:
        composite, breakdown = score_listing(dict(row), profile, weights, now)
        conn.execute(
            "UPDATE listings SET score = ?, score_breakdown = ? WHERE id = ?",
            (composite, json.dumps(breakdown), row["id"]),
        )
        stats["scored"] += 1
        if breakdown.get("dealbreaker"):
            stats["dealbreakers"] += 1

    conn.commit()
    conn.close()

    logger.info(
        "Scored %d listings (%d dealbreakers)",
        stats["scored"], stats["dealbreakers"],
    )
    return stats


def print_top_bottom(n: int = 20, per_company_cap: int | None = None) -> None:
    """Print top N and bottom N scored listings."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT id, score, score_breakdown, company_display, title_display,
               location_display, is_remote, source
        FROM listings
        WHERE canonical_id IS NULL AND score IS NOT NULL
        ORDER BY score DESC
        """
    ).fetchall()
    conn.close()

    if not rows:
        print("No scored listings.")
        return

    if per_company_cap:
        # Cap per company
        company_counts: dict[str, int] = {}
        capped: list = []
        for row in rows:
            c = row["company_display"]
            company_counts[c] = company_counts.get(c, 0) + 1
            if company_counts[c] <= per_company_cap:
                capped.append(row)
        rows_to_show = capped
        label = f" (max {per_company_cap}/company)"
    else:
        rows_to_show = list(rows)
        label = ""

    def _print_section(title: str, section_rows: list) -> None:
        print(f"\n{'=' * 90}")
        print(f"  {title}{label}")
        print(f"{'=' * 90}")
        for row in section_rows:
            bd = json.loads(row["score_breakdown"])
            dims = bd.get("dimensions", {})
            remote_flag = " [REMOTE]" if row["is_remote"] else ""
            deal = bd.get("dealbreaker")

            print(f"\n  #{row['id']:>4}  Score: {row['score']:>5.1f}  {row['company_display']} — {row['title_display']}")
            print(f"         {row['location_display'] or '(no location)'}{remote_flag}  ({row['source']})")

            if deal:
                print(f"         DEALBREAKER: {deal}")
            else:
                hygiene = bd.get("hygiene_score", 0)
                factor = bd.get("skill_factor", 0)
                scale_label = bd.get("scale_label", "")
                sm_d = dims.get("skill_match", {})
                print(f"         Hygiene: {hygiene:.0f} x {factor:.0%} skill factor = {row['score']:.1f}  ({scale_label})")

                hyg_parts = []
                for dim_name in ["degree_posture", "freshness",
                                 "location_fit", "seniority_fit", "source_quality"]:
                    d = dims.get(dim_name, {})
                    hyg_parts.append(f"{dim_name}={d.get('score', 0):.0f}")
                print(f"         Hygiene dims: {', '.join(hyg_parts)}")
                print(f"         Skill match: {sm_d.get('score', 0):.0f}/100")

                detail = bd.get("detail", {})
                sm = detail.get("skill_match", {})
                hits = sm.get("primary_hits", []) + sm.get("secondary_hits", []) + sm.get("bonus_hits", [])
                if hits:
                    print(f"         Skills: {', '.join(hits)}")

    top_n = rows_to_show[:n]
    bottom_n = rows_to_show[-n:] if len(rows_to_show) > n else rows_to_show
    bottom_n = list(reversed(bottom_n))

    _print_section(f"TOP {min(n, len(top_n))}", top_n)
    _print_section(f"BOTTOM {min(n, len(bottom_n))}", bottom_n)
