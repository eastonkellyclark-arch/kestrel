"""Remote feeds adapter — one parser, three configs.

Covers RemoteOK (JSON), Remotive (JSON), We Work Remotely (RSS).
Everything on these feeds is remote by definition.
"""

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime

import httpx

from ..models import FetchOutcome, FetchResult
from ..repository import store_raw_listing

logger = logging.getLogger("kestrel.remote_feeds")


# Feed configurations
FEEDS = {
    "remoteok": {
        "url": "https://remoteok.com/api",
        "format": "json",
        "headers": {"User-Agent": "Kestrel/1.0"},
    },
    "remotive": {
        "url": "https://remotive.com/api/remote-jobs",
        "format": "json",
    },
    "weworkremotely": {
        "url": "https://weworkremotely.com/categories/remote-programming-jobs.rss",
        "format": "rss",
    },
}


def _parse_remoteok_jobs(data: list) -> list[dict]:
    """Extract jobs from RemoteOK JSON response."""
    jobs = []
    for item in data:
        if not isinstance(item, dict) or not item.get("position"):
            continue
        jobs.append({
            "source_id": str(item.get("id", "")),
            "title": item.get("position", ""),
            "company": item.get("company", ""),
            "location": item.get("location", "Worldwide"),
            "description": item.get("description", ""),
            "url": item.get("url", ""),
            "posted_at": item.get("date", ""),
            "tags": item.get("tags", []),
            "salary_min": item.get("salary_min"),
            "salary_max": item.get("salary_max"),
            "raw": item,
        })
    return jobs


def _parse_remotive_jobs(data: dict) -> list[dict]:
    """Extract jobs from Remotive JSON response."""
    jobs = []
    for item in data.get("jobs", []):
        jobs.append({
            "source_id": str(item.get("id", "")),
            "title": item.get("title", ""),
            "company": item.get("company_name", ""),
            "location": item.get("candidate_required_location", "Worldwide"),
            "description": item.get("description", ""),
            "url": item.get("url", ""),
            "posted_at": item.get("publication_date", ""),
            "tags": item.get("tags", []),
            "raw": item,
        })
    return jobs


def _parse_wwr_rss(xml_text: str) -> list[dict]:
    """Extract jobs from We Work Remotely RSS feed."""
    jobs = []
    # Parse RSS XML
    root = ET.fromstring(xml_text)
    for item in root.findall(".//item"):
        title_text = item.findtext("title", "")
        link = item.findtext("link", "")
        description = item.findtext("description", "")
        pub_date = item.findtext("pubDate", "")
        region = item.findtext("region", "Worldwide")
        category = item.findtext("category", "")

        # WWR titles are "Company: Title"
        company = ""
        title = title_text
        if ": " in title_text:
            company, title = title_text.split(": ", 1)

        # Generate a stable ID from the link
        source_id = re.sub(r"[^a-z0-9]", "-", link.lower().split("/")[-1]) if link else ""

        jobs.append({
            "source_id": source_id,
            "title": title.strip(),
            "company": company.strip(),
            "location": region,
            "description": description,
            "url": link,
            "posted_at": pub_date,
            "tags": [category] if category else [],
            "raw": {"title": title_text, "link": link, "description": description,
                    "pubDate": pub_date, "region": region, "category": category},
        })
    return jobs


_PARSERS = {
    "json_remoteok": _parse_remoteok_jobs,
    "json_remotive": _parse_remotive_jobs,
    "rss": _parse_wwr_rss,
}


def fetch(feed_name: str, timeout: float = 30.0) -> FetchResult:
    """Fetch from a remote feed by name."""
    config = FEEDS.get(feed_name)
    if not config:
        return FetchResult(feed_name, feed_name, feed_name,
                           FetchOutcome.NETWORK_ERROR,
                           error_detail=f"Unknown feed: {feed_name}")

    url = config["url"]
    headers = config.get("headers", {})

    try:
        resp = httpx.get(url, timeout=timeout, headers=headers)
    except httpx.ConnectError as e:
        return FetchResult(feed_name, feed_name, feed_name,
                           FetchOutcome.NETWORK_ERROR, error_detail=f"Connection failed: {e}")
    except httpx.TimeoutException:
        return FetchResult(feed_name, feed_name, feed_name,
                           FetchOutcome.NETWORK_ERROR, error_detail="Request timed out")
    except httpx.HTTPError as e:
        return FetchResult(feed_name, feed_name, feed_name,
                           FetchOutcome.NETWORK_ERROR, error_detail=str(e))

    if resp.status_code != 200:
        return FetchResult(feed_name, feed_name, feed_name,
                           FetchOutcome.NETWORK_ERROR,
                           error_detail=f"HTTP {resp.status_code}")

    # Parse based on format
    fmt = config["format"]
    if fmt == "json":
        data = resp.json()
        parser_key = f"json_{feed_name}"
        parser = _PARSERS.get(parser_key)
        if not parser:
            return FetchResult(feed_name, feed_name, feed_name,
                               FetchOutcome.NETWORK_ERROR,
                               error_detail=f"No parser for {parser_key}")
        jobs = parser(data)
    elif fmt == "rss":
        jobs = _parse_wwr_rss(resp.text)
    else:
        return FetchResult(feed_name, feed_name, feed_name,
                           FetchOutcome.NETWORK_ERROR,
                           error_detail=f"Unknown format: {fmt}")

    if not jobs:
        return FetchResult(feed_name, feed_name, feed_name,
                           FetchOutcome.EMPTY_BOARD, job_count=0)

    now = datetime.utcnow()
    stored = 0
    for job in jobs:
        sid = job.get("source_id", "")
        if not sid:
            continue
        if store_raw_listing(feed_name, feed_name, sid, job.get("raw", job), now):
            stored += 1

    logger.info("%s: %d jobs, %d new", feed_name, len(jobs), stored)
    return FetchResult(feed_name, feed_name, feed_name,
                       FetchOutcome.SUCCESS, job_count=len(jobs))


def fetch_all_feeds() -> list[FetchResult]:
    """Fetch from all configured remote feeds."""
    results = []
    for name in FEEDS:
        logger.info("Fetching %s...", name)
        results.append(fetch(name))
    return results
