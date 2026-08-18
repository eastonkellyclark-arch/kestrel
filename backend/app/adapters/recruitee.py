"""Recruitee public board adapter.

Endpoint: https://{slug}.recruitee.com/api/offers
Returns {"offers": [...]} on success.
"""

import logging
from datetime import datetime

import httpx

from ..models import FetchOutcome, FetchResult
from ..repository import store_raw_listing

logger = logging.getLogger("kestrel.recruitee")


def fetch(company: str, slug: str, timeout: float = 30.0) -> FetchResult:
    url = f"https://{slug}.recruitee.com/api/offers"
    try:
        resp = httpx.get(url, timeout=timeout)
    except httpx.ConnectError as e:
        return FetchResult(company, "recruitee", slug,
                           FetchOutcome.NETWORK_ERROR, error_detail=f"Connection failed: {e}")
    except httpx.TimeoutException:
        return FetchResult(company, "recruitee", slug,
                           FetchOutcome.NETWORK_ERROR, error_detail="Request timed out")
    except httpx.HTTPError as e:
        return FetchResult(company, "recruitee", slug,
                           FetchOutcome.NETWORK_ERROR, error_detail=str(e))

    if resp.status_code == 404:
        return FetchResult(company, "recruitee", slug,
                           FetchOutcome.SLUG_NOT_FOUND,
                           error_detail=f"Board '{slug}' not found (404)")
    if resp.status_code == 403:
        return FetchResult(company, "recruitee", slug,
                           FetchOutcome.BOARD_DISABLED,
                           error_detail=f"Board '{slug}' returned 403")
    if resp.status_code != 200:
        return FetchResult(company, "recruitee", slug,
                           FetchOutcome.NETWORK_ERROR,
                           error_detail=f"HTTP {resp.status_code}")

    data = resp.json()
    offers = data.get("offers", [])
    if not offers:
        return FetchResult(company, "recruitee", slug,
                           FetchOutcome.EMPTY_BOARD, job_count=0)

    now = datetime.utcnow()
    stored = 0
    for offer in offers:
        source_id = str(offer.get("id", ""))
        if not source_id:
            continue
        if store_raw_listing("recruitee", slug, source_id, offer, now):
            stored += 1

    logger.info("%s (%s): %d offers, %d new", company, slug, len(offers), stored)
    return FetchResult(company, "recruitee", slug,
                       FetchOutcome.SUCCESS, job_count=len(offers))
