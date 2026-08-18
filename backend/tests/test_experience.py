"""Unit tests for experience extraction and scoring."""

import pytest
from backend.app.scoring.experience_fit import extract_years, score

PROFILE = {"experience_years": 1}


class TestExtraction:
    def test_numeric_plus(self):
        assert extract_years("5+ years of experience") == 5

    def test_numeric_plain(self):
        assert extract_years("3 years experience required") == 3

    def test_minimum(self):
        assert extract_years("Minimum 4 years of experience") == 4

    def test_at_least(self):
        assert extract_years("At least 7 years of experience") == 7

    def test_range_takes_lower(self):
        assert extract_years("2-4 years of experience") == 2

    def test_range_with_to(self):
        assert extract_years("3 to 5 years experience") == 3

    def test_spelled_out_five(self):
        assert extract_years("five years of experience in web development") == 5

    def test_spelled_out_three(self):
        assert extract_years("Must have three years of experience") == 3

    def test_spelled_out_ten(self):
        assert extract_years("ten years experience required") == 10

    def test_requiring(self):
        assert extract_years("This role requires 6 years of relevant experience") == 6

    def test_no_experience_explicit(self):
        assert extract_years("No experience required") == 0

    def test_entry_level(self):
        assert extract_years("This is an entry-level position") == 0

    def test_new_grad(self):
        assert extract_years("New graduate welcome to apply") == 0

    def test_internship(self):
        assert extract_years("Summer internship for CS students") == 0

    def test_will_train(self):
        assert extract_years("Will train the right candidate") == 0

    def test_none_when_missing(self):
        assert extract_years("We are looking for a great engineer") is None

    def test_none_when_empty(self):
        assert extract_years("") is None

    def test_none_when_null(self):
        assert extract_years(None) is None

    def test_experience_colon(self):
        assert extract_years("Experience: 8 years") == 8

    def test_yrs_abbreviation(self):
        assert extract_years("5+ yrs exp in software development") == 5


class TestScoring:
    def test_none_is_neutral(self):
        s, d = score(None, PROFILE)
        assert s == 50.0
        assert d["experience"] == "not_mentioned"

    def test_zero_is_best(self):
        s, d = score(0, PROFILE)
        assert s == 100.0
        assert d["experience"] == "none_required"

    def test_at_user_level(self):
        s, d = score(1, PROFILE)
        assert s == 100.0

    def test_mild_stretch(self):
        s, d = score(3, PROFILE)
        assert s == 70.0
        assert d["gap"] == 2

    def test_significant_gap(self):
        s, d = score(5, PROFILE)
        assert s == 40.0
        assert d["gap"] == 4

    def test_heavy_gap(self):
        s, d = score(8, PROFILE)
        assert s == 15.0
        assert d["gap"] == 7

    def test_below_user(self):
        """Role requires 0, user has 1 — great fit."""
        profile = {"experience_years": 3}
        s, d = score(1, profile)
        assert s == 100.0
