"""Lever public postings adapter.

Endpoint: https://api.lever.co/v0/postings/{slug}?mode=json
Returns a JSON array of postings on success.
"""

import logging
from datetime import datetime

import httpx

from ..models import FetchOutcome, FetchResult
from ..repository import store_raw_listing

logger = logging.getLogger("kestrel.lever")

BASE_URL = "https://api.lever.co/v0/postings"


def fetch(company: str, slug: str, timeout: float = 30.0) -> FetchResult:
    url = f"{BASE_URL}/{slug}?mode=json"
    try:
        resp = httpx.get(url, timeout=timeout)
    except httpx.ConnectError as e:
        return FetchResult(company, "lever", slug,
                           FetchOutcome.NETWORK_ERROR, error_detail=f"Connection failed: {e}")
    except httpx.TimeoutException:
        return FetchResult(company, "lever", slug,
                           FetchOutcome.NETWORK_ERROR, error_detail="Request timed out")
    except httpx.HTTPError as e:
        return FetchResult(company, "lever", slug,
                           FetchOutcome.NETWORK_ERROR, error_detail=str(e))

    if resp.status_code == 404:
        return FetchResult(company, "lever", slug,
                           FetchOutcome.SLUG_NOT_FOUND,
                           error_detail=f"Board '{slug}' not found (404)")

    if resp.status_code == 403:
        return FetchResult(company, "lever", slug,
                           FetchOutcome.BOARD_DISABLED,
                           error_detail=f"Board '{slug}' returned 403 — likely disabled")

    if resp.status_code != 200:
        return FetchResult(company, "lever", slug,
                           FetchOutcome.NETWORK_ERROR,
                           error_detail=f"HTTP {resp.status_code}")

    data = resp.json()

    # Lever returns [] for a valid board with no postings,
    # but also [] for some slugs that simply don't exist without a 404.
    # We treat an empty list from a 200 as an empty board — it's a real response.
    if not data:
        return FetchResult(company, "lever", slug,
                           FetchOutcome.EMPTY_BOARD, job_count=0)

    now = datetime.utcnow()
    stored = 0
    for posting in data:
        source_id = str(posting.get("id", ""))
        if not source_id:
            continue
        if store_raw_listing("lever", slug, source_id, posting, now):
            stored += 1

    logger.info("%s (%s): %d postings, %d new", company, slug, len(data), stored)
    return FetchResult(company, "lever", slug,
                       FetchOutcome.SUCCESS, job_count=len(data))
