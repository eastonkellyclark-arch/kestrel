"""USAJobs adapter.

Endpoint: https://data.usajobs.gov/api/search
Free key, generous limits. Federal hiring with explicit qualification
standards where experience substitutes for a degree.

Auth: Authorization-Key header + User-Agent (registered email).
"""

import logging
from datetime import datetime

import httpx

from ..models import FetchOutcome, FetchResult
from ..repository import store_raw_listing
from ..settings import settings

logger = logging.getLogger("kestrel.usajobs")

BASE_URL = "https://data.usajobs.gov/api/search"


def fetch(
    keywords: list[str] | None = None,
    location: str = "Minnesota",
    pages: int = 1,
    results_per_page: int = 250,
) -> FetchResult:
    """Fetch jobs from USAJobs."""
    api_key = settings.usajobs_api_key
    email = settings.usajobs_email
    if not api_key or not email:
        return FetchResult("USAJobs", "usajobs", "search",
                           FetchOutcome.NETWORK_ERROR,
                           error_detail="KESTREL_USAJOBS_API_KEY and KESTREL_USAJOBS_EMAIL not set")

    headers = {
        "Authorization-Key": api_key,
        "User-Agent": email,
    }

    total_stored = 0
    total_found = 0
    now = datetime.utcnow()

    for page in range(1, pages + 1):
        params = {
            "Page": page,
            "ResultsPerPage": min(results_per_page, 500),
        }
        if keywords:
            params["Keyword"] = " ".join(keywords)
        if location:
            params["LocationName"] = location

        try:
            resp = httpx.get(BASE_URL, params=params, headers=headers, timeout=30.0)
        except httpx.HTTPError as e:
            return FetchResult("USAJobs", "usajobs", "search",
                               FetchOutcome.NETWORK_ERROR, error_detail=str(e))

        if resp.status_code == 429:
            return FetchResult("USAJobs", "usajobs", "search",
                               FetchOutcome.BOARD_DISABLED,
                               error_detail="Rate limited (429)")

        if resp.status_code != 200:
            return FetchResult("USAJobs", "usajobs", "search",
                               FetchOutcome.NETWORK_ERROR,
                               error_detail=f"HTTP {resp.status_code}")

        data = resp.json()
        search_result = data.get("SearchResult", {})
        items = search_result.get("SearchResultItems", [])
        total_found += len(items)

        for item in items:
            match_data = item.get("MatchedObjectDescriptor", item)
            source_id = str(match_data.get("PositionID", match_data.get("PositionURI", "")))
            if not source_id:
                continue
            if store_raw_listing("usajobs", "search", source_id, item, now):
                total_stored += 1

        logger.info("USAJobs page %d: %d results, %d new", page, len(items), total_stored)

        # Check if there are more pages
        result_count = int(search_result.get("SearchResultCount", 0))
        if page * results_per_page >= result_count:
            break

    if total_found == 0:
        return FetchResult("USAJobs", "usajobs", "search",
                           FetchOutcome.EMPTY_BOARD, job_count=0)

    return FetchResult("USAJobs", "usajobs", "search",
                       FetchOutcome.SUCCESS, job_count=total_found)
