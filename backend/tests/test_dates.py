"""Tests for timestamp normalisation.

The strings here are the real shapes our sources emit, not invented ones.
"""

import pytest

from backend.app.dates import normalize_timestamp as N


@pytest.mark.parametrize("raw,expected", [
    # We Work Remotely RSS — the bug. `[:19]` produced "Wed, 12 Aug 2026 18".
    ("Wed, 12 Aug 2026 18:00:00 +0000", "2026-08-12T18:00:00"),
    ("Mon, 22 Jul 2026 07:15:33 +0000", "2026-07-22T07:15:33"),
    # RFC 822 with a named zone, and with an offset that must actually shift.
    ("Wed, 12 Aug 2026 18:00:00 GMT", "2026-08-12T18:00:00"),
    ("Wed, 12 Aug 2026 14:00:00 -0400", "2026-08-12T18:00:00"),
])
def test_rfc822_rss_dates(raw, expected):
    assert N(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    # Greenhouse / Lever / Remotive — ISO 8601 with an offset.
    ("2026-08-15T15:25:24-04:00", "2026-08-15T19:25:24"),
    ("2026-08-16T14:14:11Z", "2026-08-16T14:14:11"),
    ("2026-08-16T14:14:11+00:00", "2026-08-16T14:14:11"),
    # Naive ISO — taken as already-UTC.
    ("2026-08-18T15:46:51", "2026-08-18T15:46:51"),
    # USAJobs sends 7 digits of sub-second precision.
    ("2026-08-15T15:03:05.0000000", "2026-08-15T15:03:05"),
    ("2026-08-15T15:03:05.123456", "2026-08-15T15:03:05"),
    # Date only.
    ("2026-08-15", "2026-08-15T00:00:00"),
])
def test_iso_dates(raw, expected):
    assert N(raw) == expected


def test_epoch_seconds_and_millis():
    # RemoteOK/HN send seconds; Freelancer sends milliseconds.
    assert N(1786000000) == N("1786000000")
    assert N(1786000000).startswith("2026-")
    assert N(1786000000000) == N(1786000000)


@pytest.mark.parametrize("raw", ["", None, "   ", "not a date", "n/a", [], {}, True])
def test_unparseable_returns_empty_string(raw):
    """An explicit "no date" the scorer already handles — never a fake one."""
    assert N(raw) == ""


@pytest.mark.parametrize("raw", ["0", "1", "99999999999999999999"])
def test_implausible_epochs_rejected(raw):
    assert N(raw) == ""


def test_output_is_always_fromisoformat_readable():
    """The contract the freshness scorer depends on."""
    from datetime import datetime

    samples = [
        "Wed, 12 Aug 2026 18:00:00 +0000",
        "2026-08-15T15:25:24-04:00",
        "2026-08-15T15:03:05.0000000",
        "2026-08-16T14:14:11Z",
        1786000000,
    ]
    for s in samples:
        out = N(s)
        assert out
        datetime.fromisoformat(out)  # must not raise


def test_wwr_listing_now_scores_as_fresh_not_undated():
    """End-to-end: the regression that cost every WWR listing ~9 points."""
    from datetime import datetime

    from backend.app.scoring.freshness import score

    now = datetime(2026, 8, 31)
    raw = "Wed, 26 Aug 2026 18:00:00 +0000"

    # What the old code produced.
    old_value, old_detail = score(raw[:19], now=now)
    assert old_detail["reason"] == "unparseable_date"
    assert old_value == 40.0

    new_value, new_detail = score(N(raw), now=now)
    assert new_detail["reason"] == "fresh"
    assert new_value == 100.0
