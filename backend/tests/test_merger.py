"""Tests for the merger (dedupe).

CLAUDE.md requires dedupe to have real tests; it had none. The cases here are
drawn from listings that were actually in the database, not invented ones.

Two bugs these lock down:

  1. Same-source pairs were never compared, on the reasoning that
     UNIQUE(source, source_id) prevents duplicates. It prevents the same
     posting being stored twice; it does nothing about one company posting the
     same role under several job IDs, which is where nearly every real
     duplicate came from.

  2. Location similarity was raw string similarity, so "Remote (USA)" and
     "Remote (Peru)" scored 0.90, and Adzuna's hierarchical
     "US, Minnesota, Hennepin County, Minneapolis" scored 0.95 against
     "...Saint Louis County, Duluth". Enabling (1) without fixing (2) merged
     519 of 1644 listings, including a Minneapolis job into a Duluth one.
"""

import pytest

from backend.app.merger import (
    CROSS_SOURCE_TITLE_GATE,
    DEDUPE_THRESHOLD,
    LOCATION_GATE,
    _location_similarity,
    compute_dedupe_score,
    dedupe_verdict,
)


def is_dupe(score: float) -> bool:
    return score >= DEDUPE_THRESHOLD


# ------------------------------------------------------------ location rules

@pytest.mark.parametrize("a,b", [
    # Same place, different granularity or spelling.
    ("Remote (USA)", "Remote (US)"),
    ("Remote, US", "Remote, United States"),
    ("Minneapolis, MN", "Minneapolis, Minnesota"),
    ("US, Minnesota, Hennepin County, Minnetonka",
     "US, Minnesota, Hennepin County, Minnetonka Mills"),
])
def test_same_place_passes_the_location_gate(a, b):
    assert _location_similarity(a, b) >= LOCATION_GATE


@pytest.mark.parametrize("a,b", [
    # Different countries — the Livefront/Sezzle international boards.
    ("Remote (USA)", "Remote (Peru)"),
    ("Chile, Remote", "Brazil, Remote"),
    ("United States, Remote", "Latin America"),
    # Different cities, sharing Adzuna's long hierarchical prefix.
    ("US, Minnesota, Hennepin County, Minneapolis",
     "US, Minnesota, Saint Louis County, Duluth"),
    ("US, Minnesota, Stearns County, Saint Cloud",
     "US, Minnesota, Saint Louis County, Duluth"),
    ("US, Minnesota, Hennepin County, Minnetonka Mills",
     "US, Minnesota, Hennepin County, Eden Prairie"),
    ("Minneapolis, Minnesota", "Saint Cloud, Minnesota"),
])
def test_different_place_fails_the_location_gate(a, b):
    assert _location_similarity(a, b) < LOCATION_GATE


def test_latin_america_is_not_the_united_states():
    """"america" as a US alias made "Latin America" match "United States"."""
    assert _location_similarity("United States, Remote", "Latin America") < LOCATION_GATE


def test_saint_is_not_a_matching_token():
    """"saint" matched Saint Cloud against Saint Louis County — 150 miles."""
    assert _location_similarity(
        "US, Minnesota, Stearns County, Saint Cloud",
        "US, Minnesota, Saint Louis County, Duluth",
    ) < LOCATION_GATE


def test_unknown_location_is_neutral_not_disqualifying():
    assert _location_similarity("", "Minneapolis, MN") == 0.5
    assert _location_similarity("Minneapolis, MN", "") == 0.5


# --------------------------------------------------------------- dupe rules

def test_identical_posting_is_a_duplicate():
    assert is_dupe(compute_dedupe_score(
        "cloudflare", "cloudflare",
        "senior data engineer", "senior data engineer",
        "In-Office", "In-Office",
        same_source=True,
    ))


def test_same_role_in_different_countries_is_not_a_duplicate():
    """Livefront posts each role per country. Eight postings, not one."""
    assert not is_dupe(compute_dedupe_score(
        "livefront", "livefront",
        "java engineer zeal", "java engineer zeal",
        "Remote (USA)", "Remote (Peru)",
        same_source=True,
    ))


def test_same_role_in_different_cities_is_not_a_duplicate():
    """Merging these would hide a metro job behind one 150 miles away."""
    assert not is_dupe(compute_dedupe_score(
        "workiva", "workiva",
        "summer 2027 intern software engineer", "summer 2027 intern software engineer",
        "US, Minnesota, Hennepin County, Minneapolis",
        "US, Minnesota, Saint Louis County, Duluth",
        same_source=True,
    ))


def test_different_roles_at_one_company_are_not_duplicates():
    """These scored 0.90 on title similarity alone and merged."""
    for title_a, title_b in [
        ("senior systems engineer workers ai", "senior systems engineer workers runtime"),
        ("senior network engineer", "forward deployed engineer fde"),
        ("senior territory account executive korea",
         "senior territory account executive seattle"),
        ("aml compliance analyst", "compliance analyst"),
    ]:
        assert not is_dupe(compute_dedupe_score(
            "cloudflare", "cloudflare", title_a, title_b, "Hybrid", "Hybrid",
            same_source=True,
        )), f"{title_a!r} vs {title_b!r} must not merge"


def test_different_companies_are_never_duplicates():
    assert compute_dedupe_score(
        "gitlab", "gusto",
        "senior backend engineer", "senior backend engineer",
        "Remote, US", "Remote, US",
    ) == 0.0


def test_cross_source_allows_fuzzy_titles():
    """Aggregators truncate and decorate titles; same-source does not."""
    score = compute_dedupe_score(
        "acme", "acme",
        "senior software engineer", "senior software engineer remote",
        "Minneapolis, MN", "Minneapolis, Minnesota",
        same_source=False,
    )
    assert is_dupe(score)


def test_cross_source_still_rejects_unrelated_titles():
    assert not is_dupe(compute_dedupe_score(
        "acme", "acme",
        "senior software engineer", "senior accountant revenue",
        "Minneapolis, MN", "Minneapolis, MN",
        same_source=False,
    ))


def test_same_source_requires_exact_title():
    """Within one source the company's own board distinguishes roles."""
    near_identical = compute_dedupe_score(
        "acme", "acme",
        "senior software engineer", "senior software engineerr",
        "Hybrid", "Hybrid",
        same_source=True,
    )
    assert near_identical == 0.0


# ------------------------------------------------------------------ verdicts

def test_verdict_reports_why_a_pair_was_blocked():
    """A gate that silently returns zero is untunable."""
    _, blocked = dedupe_verdict(
        "livefront", "livefront",
        "java engineer zeal", "java engineer zeal",
        "Remote (USA)", "Remote (Peru)",
        same_source=True,
    )
    assert blocked is not None
    assert "location" in blocked


def test_verdict_reports_title_blocks():
    _, blocked = dedupe_verdict(
        "cloudflare", "cloudflare",
        "senior network engineer", "forward deployed engineer",
        "Hybrid", "Hybrid",
        same_source=True,
    )
    assert blocked is not None
    assert "title" in blocked


def test_verdict_is_clean_for_a_real_duplicate():
    score, blocked = dedupe_verdict(
        "cloudflare", "cloudflare",
        "senior data engineer", "senior data engineer",
        "In-Office", "In-Office",
        same_source=True,
    )
    assert blocked is None
    assert score >= DEDUPE_THRESHOLD


def test_compute_score_returns_zero_when_blocked():
    """The public helper keeps its contract: blocked means 0.0."""
    assert compute_dedupe_score(
        "livefront", "livefront",
        "java engineer zeal", "java engineer zeal",
        "Remote (USA)", "Remote (Peru)",
        same_source=True,
    ) == 0.0
