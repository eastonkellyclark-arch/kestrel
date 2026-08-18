"""Adzuna adapter with explicit call budget.

Endpoint: https://api.adzuna.com/v1/api/jobs/us/search/{page}
Free tier: ~1,000 calls/month (~33/day). ENFORCE in code.

The budget counter persists in SQLite (_meta table) so it survives restarts.
Refuses to exceed the daily cap rather than silently burning quota.
"""

import json
import logging
from datetime import datetime, date

import httpx

from ..database import get_connection
from ..models import FetchOutcome, FetchResult
from ..repository import store_raw_listing
from ..settings import settings

logger = logging.getLogger("kestrel.adzuna")

BASE_URL = "https://api.adzuna.com/v1/api/jobs/us/search"


def _get_budget_key() -> str:
    return f"adzuna_calls_{date.today().isoformat()}"


def _get_calls_today() -> int:
    conn = get_connection()
    row = conn.execute(
        "SELECT value FROM _meta WHERE key = ?", (_get_budget_key(),)
    ).fetchone()
    conn.close()
    return int(row["value"]) if row else 0


def _increment_calls(count: int = 1) -> int:
    key = _get_budget_key()
    conn = get_connection()
    row = conn.execute("SELECT value FROM _meta WHERE key = ?", (key,)).fetchone()
    current = int(row["value"]) if row else 0
    new_val = current + count
    conn.execute(
        "INSERT INTO _meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?",
        (key, str(new_val), str(new_val)),
    )
    conn.commit()
    conn.close()
    return new_val


def get_budget_status() -> dict:
    """Return current budget status."""
    used = _get_calls_today()
    limit = settings.adzuna_daily_budget
    return {"date": date.today().isoformat(), "used": used, "limit": limit,
            "remaining": max(0, limit - used)}


def fetch(
    keywords: list[str] | None = None,
    location: str = "Minnesota",
    pages: int = 1,
    results_per_page: int = 50,
) -> FetchResult:
    """Fetch jobs from Adzuna. Respects the daily budget."""
    app_id = settings.adzuna_app_id
    app_key = settings.adzuna_app_key
    if not app_id or not app_key:
        return FetchResult("Adzuna", "adzuna", "search",
                           FetchOutcome.NETWORK_ERROR,
                           error_detail="KESTREL_ADZUNA_APP_ID and KESTREL_ADZUNA_APP_KEY not set")

    budget = get_budget_status()
    if budget["remaining"] < pages:
        return FetchResult("Adzuna", "adzuna", "search",
                           FetchOutcome.BOARD_DISABLED,
                           error_detail=f"Daily budget exhausted: {budget['used']}/{budget['limit']} calls used today")

    total_stored = 0
    total_found = 0
    now = datetime.utcnow()

    for page in range(1, pages + 1):
        # Check budget before each call
        if _get_calls_today() >= settings.adzuna_daily_budget:
            logger.warning("Adzuna budget hit mid-fetch at page %d", page)
            break

        url = f"{BASE_URL}/{page}"
        params = {
            "app_id": app_id,
            "app_key": app_key,
            "results_per_page": min(results_per_page, 50),
            "content-type": "application/json",
        }
        if keywords:
            params["what"] = " ".join(keywords)
        if location:
            params["where"] = location

        try:
            resp = httpx.get(url, params=params, timeout=30.0)
            _increment_calls()
        except httpx.HTTPError as e:
            _increment_calls()  # count the attempt
            return FetchResult("Adzuna", "adzuna", "search",
                               FetchOutcome.NETWORK_ERROR, error_detail=str(e))

        if resp.status_code == 429:
            return FetchResult("Adzuna", "adzuna", "search",
                               FetchOutcome.BOARD_DISABLED,
                               error_detail="Rate limited (429)")

        if resp.status_code != 200:
            return FetchResult("Adzuna", "adzuna", "search",
                               FetchOutcome.NETWORK_ERROR,
                               error_detail=f"HTTP {resp.status_code}")

        data = resp.json()
        results = data.get("results", [])
        total_found += len(results)

        for job in results:
            source_id = str(job.get("id", ""))
            if not source_id:
                continue
            if store_raw_listing("adzuna", "search", source_id, job, now):
                total_stored += 1

        logger.info("Adzuna page %d: %d results, %d new", page, len(results), total_stored)

        if len(results) < results_per_page:
            break  # no more pages

    budget_after = get_budget_status()
    logger.info("Adzuna budget: %d/%d used today", budget_after["used"], budget_after["limit"])

    if total_found == 0:
        return FetchResult("Adzuna", "adzuna", "search",
                           FetchOutcome.EMPTY_BOARD, job_count=0)

    return FetchResult("Adzuna", "adzuna", "search",
                       FetchOutcome.SUCCESS, job_count=total_found)
