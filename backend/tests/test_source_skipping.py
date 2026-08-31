"""Tests for sources that do not run.

A source that never ran must never look like a source that ran and found
nothing. The Gmail alert channel contributed zero listings for thirteen days
without a single log line, because the collector skipped it with a bare
`if creds:` and no else branch.
"""

import os

from backend.app.adapters import gmail_alerts
from backend.app.collector import healthy_pairs
from backend.app.models import FetchOutcome, FetchResult


def test_skipped_is_distinct_from_success_and_failure():
    assert FetchOutcome.SKIPPED.value == "skipped"
    assert FetchOutcome.SKIPPED not in (FetchOutcome.SUCCESS, FetchOutcome.EMPTY_BOARD)


def test_skipped_source_is_not_counted_healthy():
    """Staleness must not conclude anything from a source that never ran."""
    results = [FetchResult("Gmail", "gmail_alert", "inbox", FetchOutcome.SKIPPED,
                           error_detail="KESTREL_GMAIL_CREDENTIALS_JSON not set")]
    assert healthy_pairs(results) == set()


def test_empty_board_is_counted_healthy():
    """A board that answered with zero open roles HAS told us something."""
    results = [FetchResult("Jamf", "greenhouse", "jamf", FetchOutcome.EMPTY_BOARD)]
    assert healthy_pairs(results) == {("greenhouse", "jamf")}


def test_collector_reports_gmail_skip_instead_of_staying_silent(monkeypatch):
    from backend.app import collector

    monkeypatch.setattr(collector.settings, "gmail_credentials_json", "", raising=False)
    monkeypatch.setattr(collector, "get_active_companies", lambda: [])
    monkeypatch.setattr(collector.adzuna_adapter, "fetch",
                        lambda **kw: FetchResult("Adzuna", "adzuna", "search",
                                                 FetchOutcome.SKIPPED))
    monkeypatch.setattr(collector.usajobs_adapter, "fetch",
                        lambda **kw: FetchResult("USAJobs", "usajobs", "search",
                                                 FetchOutcome.SKIPPED))
    monkeypatch.setattr(collector.remote_feeds, "fetch_all_feeds", lambda: [])
    # Gig sources hit the network too; this test is about the Gmail branch.
    monkeypatch.setattr(collector.gig_feeds, "fetch_all_gig_feeds", lambda: [])
    monkeypatch.setattr(collector.freelancer_adapter, "fetch",
                        lambda **kw: FetchResult("Freelancer.com", "freelancer", "search",
                                                 FetchOutcome.SKIPPED))

    results = collector.fetch_all(include_aggregators=True)
    gmail = [r for r in results if r.company == "Gmail"]

    assert gmail, "Gmail must appear in the results even when it is not configured"
    assert gmail[0].outcome == FetchOutcome.SKIPPED
    assert "GMAIL_CREDENTIALS_JSON" in gmail[0].error_detail


def test_headless_detection(monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("KESTREL_HEADLESS", raising=False)
    assert gmail_alerts._is_headless() is False

    monkeypatch.setenv("CI", "true")
    assert gmail_alerts._is_headless() is True

    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("KESTREL_HEADLESS", "1")
    assert gmail_alerts._is_headless() is True


def test_headless_run_refuses_interactive_auth_instead_of_blocking(tmp_path):
    """run_local_server() in CI blocks on a browser until the job times out."""
    creds = tmp_path / "credentials.json"
    creds.write_text('{"installed": {"client_id": "x", "client_secret": "y"}}')

    results = gmail_alerts.fetch_alerts(
        str(creds), str(tmp_path / "no_token.json"), allow_interactive=False
    )

    assert len(results) == 1
    assert results[0].outcome == FetchOutcome.NETWORK_ERROR
    detail = results[0].error_detail
    assert "interactive authorisation" in detail
    assert "GMAIL_TOKEN_JSON" in detail


def test_missing_credentials_file_is_reported(tmp_path):
    results = gmail_alerts.fetch_alerts(
        str(tmp_path / "nope.json"), str(tmp_path / "no_token.json"),
        allow_interactive=False,
    )
    assert results[0].outcome == FetchOutcome.NETWORK_ERROR
    assert "Credentials file not found" in results[0].error_detail
