"""The Collector — fetches from all active registry companies.

Per-company failure isolation: one dead slug never aborts the run.
"""

import logging

from .adapters import greenhouse, lever, ashby, recruitee
from .adapters import adzuna as adzuna_adapter
from .adapters import usajobs as usajobs_adapter
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

    # Aggregators
    if include_aggregators:
        logger.info("Fetching Adzuna...")
        results.append(adzuna_adapter.fetch(
            keywords=["software engineer", "developer"],
            location="Minnesota",
            pages=1,
        ))
        logger.info("Fetching USAJobs...")
        results.append(usajobs_adapter.fetch(
            keywords=["information technology", "software"],
            location="Minnesota",
            pages=1,
        ))

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
