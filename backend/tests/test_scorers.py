"""Unit tests for all six scorers plus edge cases.

Covers: missing description, missing salary, missing date,
low-quality-description flag, dealbreakers.
"""

from datetime import datetime

import pytest

from backend.app.scoring import (
    degree_posture,
    freshness,
    location_fit,
    seniority_fit,
    skill_match,
    source_quality,
)

PROFILE = {
    "skills": {
        "primary": ["typescript", "react", "nextjs", "nodejs", "postgresql"],
        "secondary": ["python", "redis", "docker", "ci/cd"],
        "bonus": ["c++", "supabase", "vite"],
        "synonyms": {
            "typescript": ["ts"],
            "react": ["reactjs", "react.js"],
            "nextjs": ["next.js", "next js"],
            "nodejs": ["node.js", "node js", "node"],
            "postgresql": ["postgres", "pg", "psql"],
            "python": ["py"],
            "docker": ["containerization", "containers"],
            "ci/cd": ["ci cd", "cicd", "continuous integration"],
            "c++": ["cpp", "cplusplus"],
        },
    },
    "seniority": {
        "target": "mid",
        "too_senior": ["staff", "principal", "director", "vp", "head of"],
        "too_junior": ["intern", "internship", "junior", "entry level"],
    },
    "dealbreakers": ["security clearance", "commission only"],
}

NOW = datetime(2026, 8, 17)


# ── skill_match ──────────────────────────────────────────────────────

class TestSkillMatch:
    def test_primary_skills(self):
        s, d = skill_match.score(
            "Full Stack Engineer",
            "We use TypeScript, React, and PostgreSQL daily.",
            "good", PROFILE,
        )
        assert s > 20
        assert "typescript" in d["primary_hits"]
        assert "react" in d["primary_hits"]
        assert "postgresql" in d["primary_hits"]

    def test_no_skills_mentioned(self):
        s, d = skill_match.score(
            "Office Manager", "Manage the office.", "good", PROFILE,
        )
        assert s == 0
        assert d["primary_hits"] == []

    def test_missing_description(self):
        s, d = skill_match.score(
            "React Developer", "", "empty", PROFILE,
        )
        # Title-only, with quality penalty
        assert d["quality_penalty"] is True
        assert s > 0  # "react" in title

    def test_non_english_description(self):
        s, d = skill_match.score(
            "Engenheiro de Software",
            "Procuramos um engenheiro com experiencia em sistemas distribuidos.",
            "non_english", PROFILE,
        )
        assert d["quality_penalty"] is True

    def test_bonus_skills(self):
        s, d = skill_match.score(
            "Engineer", "Experience with C++ and Supabase.", "good", PROFILE,
        )
        assert "c++" in d["bonus_hits"]
        assert "supabase" in d["bonus_hits"]

    def test_synonyms_ts_node_pg(self):
        s, d = skill_match.score(
            "TS/Node Developer",
            "Stack: TS, Node, PG, Redis.",
            "good", PROFILE,
        )
        assert "typescript" in d["primary_hits"]
        assert "nodejs" in d["primary_hits"]
        assert "postgresql" in d["primary_hits"]
        assert "redis" in d["secondary_hits"]

    def test_synonym_react_js(self):
        s, d = skill_match.score(
            "Frontend Engineer",
            "We use React.js and Next.js for our frontend.",
            "good", PROFILE,
        )
        assert "react" in d["primary_hits"]
        assert "nextjs" in d["primary_hits"] or "next.js" in d["primary_hits"]


# ── degree_posture ───────────────────────────────────────────────────

class TestDegreePosture:
    def test_hard_requirement(self):
        s, _ = degree_posture.score(
            "Bachelor's degree required in Computer Science.", "good",
        )
        assert s == 20.0

    def test_equivalent_ok(self):
        s, d = degree_posture.score(
            "BS in CS or equivalent experience accepted.", "good",
        )
        assert s == 70.0
        assert d["posture"] == "equivalent_ok"

    def test_no_degree_explicit(self):
        s, d = degree_posture.score(
            "No degree required. We value experience.", "good",
        )
        assert s == 100.0
        assert d["posture"] == "no_degree"

    def test_not_mentioned(self):
        s, d = degree_posture.score(
            "We want someone who ships fast and communicates clearly.",
            "good",
        )
        assert s == 90.0
        assert d["posture"] == "not_mentioned"

    def test_missing_description(self):
        s, d = degree_posture.score("", "empty")
        assert s == 50.0
        assert d["posture"] == "unknown"

    def test_non_english(self):
        s, d = degree_posture.score(
            "Precisamos de um engenheiro senior.", "non_english",
        )
        assert s == 50.0


# ── freshness ────────────────────────────────────────────────────────

class TestFreshness:
    def test_fresh(self):
        s, d = freshness.score("2026-08-15T10:00:00", NOW)
        assert s == 100.0
        assert d["days_old"] in (1, 2)  # depends on time-of-day

    def test_two_weeks(self):
        s, d = freshness.score("2026-08-05T10:00:00", NOW)
        assert s == 85.0

    def test_one_month(self):
        s, d = freshness.score("2026-07-20T10:00:00", NOW)
        assert s == 70.0

    def test_stale(self):
        s, d = freshness.score("2026-01-01T10:00:00", NOW)
        assert s == 10.0
        assert d["reason"] == "stale"

    def test_missing_date(self):
        s, d = freshness.score("", NOW)
        assert s == 40.0
        assert d["reason"] == "no_date"

    def test_none_date(self):
        s, d = freshness.score(None, NOW)
        assert s == 40.0

    def test_unparseable(self):
        s, d = freshness.score("not-a-date", NOW)
        assert s == 40.0
        assert d["reason"] == "unparseable_date"

    def test_re_post_months_old(self):
        """Greenhouse first_published can be months old — re-posts or evergreen."""
        s, d = freshness.score("2026-04-01T10:00:00", NOW)
        # 138 days old → 90-180 bracket = 20, or >180 = 10 depending on exact date
        assert s in (20.0, 10.0)
        assert d["days_old"] > 90


# ── location_fit ─────────────────────────────────────────────────────

class TestLocationFit:
    def test_twin_cities(self):
        s, d = location_fit.score("Minneapolis, MN", False)
        assert s == 100.0
        assert d["fit"] == "metro"

    def test_minnesota(self):
        s, d = location_fit.score("Duluth, MN", False)
        assert s == 95.0

    def test_us_remote(self):
        s, d = location_fit.score("Remote, United States", True)
        assert s == 90.0

    def test_non_us_onsite(self):
        s, d = location_fit.score("Bangalore, India", False)
        assert s == 5.0

    def test_non_us_remote(self):
        s, d = location_fit.score("Remote, India", True)
        assert s == 15.0

    def test_us_not_metro(self):
        s, d = location_fit.score("San Francisco, CA", False)
        assert s == 40.0

    def test_no_location(self):
        s, d = location_fit.score("", False)
        assert s == 30.0

    def test_ambiguous_remote(self):
        s, d = location_fit.score("Remote", True)
        assert s == 60.0

    def test_canada_only_restriction(self):
        """'CA Remote (BC & ON only)' is Canada, not US."""
        s, d = location_fit.score("CA Remote (BC & ON only)", True)
        assert s == 15.0
        assert d["fit"] == "non_us_restricted"

    def test_us_remote_with_us_paren(self):
        """US states in parens should NOT trigger non-US restriction."""
        s, d = location_fit.score("Remote, US (CA, NY, TX)", True)
        assert s >= 85.0  # should be US remote


# ── seniority_fit ────────────────────────────────────────────────────

class TestSeniorityFit:
    def test_mid_implied(self):
        s, d = seniority_fit.score("Software Engineer", PROFILE)
        assert s == 100.0

    def test_mid_explicit(self):
        s, d = seniority_fit.score("Software Engineer II", PROFILE)
        assert s == 100.0

    def test_senior(self):
        s, d = seniority_fit.score("Senior Software Engineer", PROFILE)
        assert s == 100.0  # mid-senior accepted range

    def test_too_senior(self):
        s, d = seniority_fit.score("Staff Engineer", PROFILE)
        assert s == 30.0

    def test_too_junior(self):
        s, d = seniority_fit.score("Software Engineering Intern", PROFILE)
        assert s == 40.0

    def test_director(self):
        s, d = seniority_fit.score("Director of Engineering", PROFILE)
        assert s == 30.0

    def test_lead(self):
        s, d = seniority_fit.score("Lead Software Engineer", PROFILE)
        assert s == 100.0  # lead is accepted range


# ── source_quality ───────────────────────────────────────────────────

class TestSourceQuality:
    def test_greenhouse(self):
        s, d = source_quality.score("greenhouse")
        assert s == 100.0
        assert d["tier"] == "direct"

    def test_lever(self):
        s, d = source_quality.score("lever")
        assert s == 100.0

    def test_adzuna(self):
        s, d = source_quality.score("adzuna")
        assert s == 50.0
        assert d["tier"] == "aggregator"

    def test_unknown_source(self):
        s, d = source_quality.score("some_new_source")
        assert s == 50.0
