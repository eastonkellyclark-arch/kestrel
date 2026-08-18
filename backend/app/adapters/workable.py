"""Workable public board adapter.

Endpoint: https://apply.workable.com/api/v3/accounts/{slug}/jobs
Returns {"results": [...]} on success.
"""

import logging
from datetime import datetime

import httpx

from ..models import FetchOutcome, FetchResult
from ..repository import store_raw_listing

logger = logging.getLogger("kestrel.workable")

BASE_URL = "https://apply.workable.com/api/v3/accounts"


def fetch(company: str, slug: str, timeout: float = 30.0) -> FetchResult:
    url = f"{BASE_URL}/{slug}/jobs"
    try:
        resp = httpx.get(url, timeout=timeout)
    except httpx.ConnectError as e:
        return FetchResult(company, "workable", slug,
                           FetchOutcome.NETWORK_ERROR, error_detail=f"Connection failed: {e}")
    except httpx.TimeoutException:
        return FetchResult(company, "workable", slug,
                           FetchOutcome.NETWORK_ERROR, error_detail="Request timed out")
    except httpx.HTTPError as e:
        return FetchResult(company, "workable", slug,
                           FetchOutcome.NETWORK_ERROR, error_detail=str(e))

    if resp.status_code == 404:
        return FetchResult(company, "workable", slug,
                           FetchOutcome.SLUG_NOT_FOUND,
                           error_detail=f"Board '{slug}' not found (404)")
    if resp.status_code == 403:
        return FetchResult(company, "workable", slug,
                           FetchOutcome.BOARD_DISABLED,
                           error_detail=f"Board '{slug}' returned 403")
    if resp.status_code != 200:
        return FetchResult(company, "workable", slug,
                           FetchOutcome.NETWORK_ERROR,
                           error_detail=f"HTTP {resp.status_code}")

    data = resp.json()
    jobs = data.get("results", [])
    if not jobs:
        return FetchResult(company, "workable", slug,
                           FetchOutcome.EMPTY_BOARD, job_count=0)

    now = datetime.utcnow()
    stored = 0
    for job in jobs:
        source_id = str(job.get("id", job.get("shortcode", "")))
        if not source_id:
            continue
        if store_raw_listing("workable", slug, source_id, job, now):
            stored += 1

    logger.info("%s (%s): %d jobs, %d new", company, slug, len(jobs), stored)
    return FetchResult(company, "workable", slug,
                       FetchOutcome.SUCCESS, job_count=len(jobs))
