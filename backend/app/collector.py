"""The Collector — fetches from all active registry companies.

Per-company failure isolation: one dead slug never aborts the run.
"""

import logging

from .adapters import greenhouse, lever, ashby, recruitee
from .adapters import adzuna as adzuna_adapter
from .adapters import usajobs as usajobs_adapter
from .adapters import remote_feeds
from .adapters import gmail_alerts
from .adapters import gig_feeds
from .models import ATSPlatform, FetchOutcome, FetchResult
from .repository import get_active_companies

logger = logging.getLogger("kestrel.collector")

ADAPTERS = {
    ATSPlatform.GREENHOUSE: greenhouse.fetch,
    ATSPlatform.LEVER: lever.fetch,
    ATSPlatform.ASHBY: ashby.fetch,
    ATSPlatform.RECRUITEE: recruitee.fetch,
}

OUTCOME_LABELS = {
    FetchOutcome.SUCCESS: "OK",
    FetchOutcome.EMPTY_BOARD: "EMPTY (no open roles)",
    FetchOutcome.SLUG_NOT_FOUND: "SLUG NOT FOUND",
    FetchOutcome.BOARD_DISABLED: "BOARD DISABLED",
    FetchOutcome.NETWORK_ERROR: "NETWORK ERROR",
}


def fetch_all(include_aggregators: bool = True) -> list[FetchResult]:
    """Fetch from all active registry companies, optionally including aggregators."""
    companies = get_active_companies()
    if not companies:
        logger.warning("Registry is empty — nothing to fetch")

    results: list[FetchResult] = []

    # ATS boards
    for entry in companies:
        adapter = ADAPTERS.get(entry.platform)
        if not adapter:
            logger.error("%s: no adapter for platform '%s'", entry.company, entry.platform)
            continue

        logger.info("Fetching %s (%s/%s)...", entry.company, entry.platform.value, entry.board_slug)
        result = adapter(entry.company, entry.board_slug)
        results.append(result)

    # Aggregators — target MN-area roles from employers NOT in the registry.
    # ATS boards already cover registry companies with better data.
    # Adzuna's value is the Workday/iCIMS companies unreachable via ATS APIs.
    if include_aggregators:
        adzuna_searches = [
            ["software engineer"],
            ["web developer"],
            ["full stack"],
            ["devops engineer"],
        ]
        for keywords in adzuna_searches:
            logger.info("Fetching Adzuna: %s...", " ".join(keywords))
            results.append(adzuna_adapter.fetch(
                keywords=keywords,
                location="Minnesota",
                pages=1,
                results_per_page=50,
            ))

        usajobs_searches = [
            ["information technology"],
            ["software developer"],
        ]
        for keywords in usajobs_searches:
            logger.info("Fetching USAJobs: %s...", " ".join(keywords))
            results.append(usajobs_adapter.fetch(
                keywords=keywords,
                location="Minnesota",
                pages=1,
            ))

        # Remote feeds
        results.extend(remote_feeds.fetch_all_feeds())

        # Gmail alerts (requires credentials)
        creds = settings.gmail_credentials_json
        token = settings.gmail_token_json
        if creds:
            token_path = token or str(settings.data_dir / "gmail_token.json")
            logger.info("Fetching Gmail alerts...")
            results.extend(gmail_alerts.fetch_alerts(creds, token_path))

        # Gig feeds (Google Alerts, Reddit, Craigslist, HN)
        results.extend(gig_feeds.fetch_all_gig_feeds())

    return results


def print_report(results: list[FetchResult]) -> None:
    if not results:
        print("No companies in registry.")
        return

    total_jobs = 0
    ok = 0
    failed = 0

    print()
    print(f"{'Company':<30} {'Platform':<12} {'Status':<25} {'Jobs':>5}")
    print("-" * 75)

    for r in results:
        label = OUTCOME_LABELS.get(r.outcome, r.outcome.value)
        status = label
        if r.error_detail:
            status = f"{label}: {r.error_detail}"
        # Truncate long status for the table, full detail logged above
        display_status = status[:40]
        count_str = str(r.job_count) if r.outcome == FetchOutcome.SUCCESS else "-"
        print(f"{r.company:<30} {r.platform:<12} {display_status:<25} {count_str:>5}")

        if r.outcome == FetchOutcome.SUCCESS:
            total_jobs += r.job_count
            ok += 1
        else:
            failed += 1

    print("-" * 75)
    print(f"Total: {ok} succeeded, {failed} failed, {total_jobs} jobs found")
    print()
