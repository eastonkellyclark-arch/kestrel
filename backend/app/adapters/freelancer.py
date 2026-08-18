"""Freelancer.com adapter — public JSON API, no auth.

Endpoint: https://www.freelancer.com/api/projects/0.1/projects/active
Returns real projects with budgets, bid counts, and timestamps.

No key, no quota documented. Be polite — one request per search.
"""

import logging
from datetime import datetime

import httpx

from ..models import FetchOutcome, FetchResult
from ..repository import store_raw_listing

logger = logging.getLogger("kestrel.freelancer")

BASE_URL = "https://www.freelancer.com/api/projects/0.1/projects/active"


def fetch(
    query: str = "web development",
    limit: int = 50,
    timeout: float = 30.0,
) -> FetchResult:
    """Fetch active projects from Freelancer.com."""
    params = {
        "query": query,
        "limit": min(limit, 100),
        "compact": "true",
        "job_details": "true",
        "project_types[]": "fixed",  # fixed-price projects
    }

    try:
        resp = httpx.get(BASE_URL, params=params, timeout=timeout,
                         headers={"User-Agent": "Kestrel/1.0"})
    except httpx.HTTPError as e:
        return FetchResult("Freelancer.com", "freelancer", "search",
                           FetchOutcome.NETWORK_ERROR, error_detail=str(e))

    if resp.status_code != 200:
        return FetchResult("Freelancer.com", "freelancer", "search",
                           FetchOutcome.NETWORK_ERROR,
                           error_detail=f"HTTP {resp.status_code}")

    data = resp.json()
    if data.get("status") != "success":
        return FetchResult("Freelancer.com", "freelancer", "search",
                           FetchOutcome.NETWORK_ERROR,
                           error_detail=f"API error: {data.get('message', 'unknown')}")

    projects = data.get("result", {}).get("projects", [])
    if not projects:
        return FetchResult("Freelancer.com", "freelancer", "search",
                           FetchOutcome.EMPTY_BOARD, job_count=0)

    now = datetime.utcnow()
    stored = 0
    for project in projects:
        source_id = str(project.get("id", ""))
        if not source_id:
            continue
        if store_raw_listing("freelancer", "search", source_id, project, now):
            stored += 1

    logger.info("Freelancer.com '%s': %d projects, %d new", query, len(projects), stored)
    return FetchResult("Freelancer.com", "freelancer", "search",
                       FetchOutcome.SUCCESS, job_count=len(projects))
