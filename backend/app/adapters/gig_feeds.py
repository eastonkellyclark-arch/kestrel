"""Gig feed adapters — Google Alerts RSS, Reddit .rss, Craigslist via Open RSS,
HN Freelancer thread via Algolia.

All feed URLs live in config/gig_feeds.yaml — add or remove without code changes.

Reddit adapter is deliberately isolated: its removal should break nothing.
"""

import hashlib
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import httpx
import yaml

from ..models import FetchOutcome, FetchResult
from ..repository import store_raw_listing

logger = logging.getLogger("kestrel.gig_feeds")

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent.parent / "config" / "gig_feeds.yaml"


def _load_config() -> dict:
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def _stable_id(text: str) -> str:
    """Generate a stable short ID from text."""
    return hashlib.md5(text.encode()).hexdigest()[:12]


def _parse_rss(xml_text: str, source_name: str) -> list[dict]:
    """Parse RSS/Atom feed into raw job dicts."""
    items = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.error("RSS parse error for %s: %s", source_name, e)
        return []

    # Handle both RSS and Atom namespaces
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    # Try RSS format first
    for item in root.findall(".//item"):
        title = item.findtext("title", "").strip()
        link = item.findtext("link", "").strip()
        description = item.findtext("description", "")
        pub_date = item.findtext("pubDate", "")
        source_id = _stable_id(link or title)

        if not title:
            continue
        items.append({
            "source_id": source_id,
            "title": title,
            "link": link,
            "description": description,
            "pub_date": pub_date,
        })

    # Try Atom format if no RSS items found
    if not items:
        for entry in root.findall(".//atom:entry", ns) or root.findall(".//{http://www.w3.org/2005/Atom}entry"):
            title = ""
            link = ""
            for child in entry:
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if tag == "title":
                    title = (child.text or "").strip()
                elif tag == "link":
                    link = child.get("href", "").strip()
                elif tag == "content" or tag == "summary":
                    description = (child.text or "").strip()
                elif tag == "published" or tag == "updated":
                    pub_date = (child.text or "").strip()

            if not title:
                continue
            items.append({
                "source_id": _stable_id(link or title),
                "title": title,
                "link": link,
                "description": description if "description" in dir() else "",
                "pub_date": pub_date if "pub_date" in dir() else "",
            })

    return items


def _fetch_rss(url: str, source_name: str, label: str,
               timeout: float = 30.0) -> FetchResult:
    """Fetch and store listings from an RSS feed."""
    headers = {"User-Agent": "Kestrel/1.0"}
    try:
        resp = httpx.get(url, timeout=timeout, headers=headers, follow_redirects=True)
    except httpx.HTTPError as e:
        return FetchResult(label, source_name, label,
                           FetchOutcome.NETWORK_ERROR, error_detail=str(e))

    if resp.status_code != 200:
        return FetchResult(label, source_name, label,
                           FetchOutcome.NETWORK_ERROR,
                           error_detail=f"HTTP {resp.status_code}")

    items = _parse_rss(resp.text, source_name)
    if not items:
        return FetchResult(label, source_name, label,
                           FetchOutcome.EMPTY_BOARD, job_count=0)

    now = datetime.utcnow()
    stored = 0
    for item in items:
        sid = item.get("source_id", "")
        if not sid:
            continue
        if store_raw_listing(source_name, label, sid, item, now):
            stored += 1

    logger.info("%s/%s: %d items, %d new", source_name, label, len(items), stored)
    return FetchResult(label, source_name, label,
                       FetchOutcome.SUCCESS, job_count=len(items))


def _fetch_hn_freelancer() -> FetchResult:
    """Fetch the latest HN 'Freelancer? Seeking Freelancer?' thread via Algolia."""
    search_url = "https://hn.algolia.com/api/v1/search_by_date"
    params = {
        "query": "Freelancer? Seeking Freelancer?",
        "tags": "story,ask_hn",
        "hitsPerPage": 1,
    }
    try:
        resp = httpx.get(search_url, params=params, timeout=30.0)
    except httpx.HTTPError as e:
        return FetchResult("HN Freelancer", "hn_freelancer", "hn",
                           FetchOutcome.NETWORK_ERROR, error_detail=str(e))

    if resp.status_code != 200:
        return FetchResult("HN Freelancer", "hn_freelancer", "hn",
                           FetchOutcome.NETWORK_ERROR,
                           error_detail=f"HTTP {resp.status_code}")

    data = resp.json()
    hits = data.get("hits", [])
    if not hits:
        return FetchResult("HN Freelancer", "hn_freelancer", "hn",
                           FetchOutcome.EMPTY_BOARD, job_count=0)

    story_id = hits[0].get("objectID")
    story_title = hits[0].get("title", "")
    logger.info("HN Freelancer thread: %s (ID %s)", story_title, story_id)

    # Fetch comments
    comments_url = f"https://hn.algolia.com/api/v1/items/{story_id}"
    try:
        resp2 = httpx.get(comments_url, timeout=30.0)
    except httpx.HTTPError as e:
        return FetchResult("HN Freelancer", "hn_freelancer", "hn",
                           FetchOutcome.NETWORK_ERROR, error_detail=str(e))

    if resp2.status_code != 200:
        return FetchResult("HN Freelancer", "hn_freelancer", "hn",
                           FetchOutcome.NETWORK_ERROR,
                           error_detail=f"Comments HTTP {resp2.status_code}")

    item_data = resp2.json()
    children = item_data.get("children", [])

    now = datetime.utcnow()
    stored = 0
    for comment in children:
        text = comment.get("text", "")
        author = comment.get("author", "")
        comment_id = str(comment.get("id", ""))
        if not text or not comment_id:
            continue

        raw = {
            "source_id": comment_id,
            "title": f"HN Freelancer: {author}",
            "description": text,
            "link": f"https://news.ycombinator.com/item?id={comment_id}",
            "pub_date": comment.get("created_at", ""),
            "author": author,
            "story_id": story_id,
            "story_title": story_title,
        }
        if store_raw_listing("hn_freelancer", "hn", comment_id, raw, now):
            stored += 1

    logger.info("HN Freelancer: %d comments, %d new", len(children), stored)
    return FetchResult("HN Freelancer", "hn_freelancer", "hn",
                       FetchOutcome.SUCCESS, job_count=len(children))


def fetch_all_gig_feeds() -> list[FetchResult]:
    """Fetch from all configured gig feeds. Returns per-feed results."""
    config = _load_config()
    results = []

    # Google Alerts RSS
    for url in config.get("google_alerts", []):
        logger.info("Fetching Google Alert: %s...", url[:60])
        results.append(_fetch_rss(url, "google_alerts_rss", f"galert-{_stable_id(url)}"))

    # Reddit .rss — isolated, expendable. ~1 req/min per feed.
    import time
    reddit_feeds = config.get("reddit", [])
    for i, feed in enumerate(reddit_feeds):
        url = feed.get("url", "")
        label = feed.get("label", url)
        if not url:
            continue
        if i > 0:
            time.sleep(5)  # Reddit rate limit: ~1 req/min per feed
        logger.info("Fetching Reddit: %s...", label)
        results.append(_fetch_rss(url, "reddit", label))

    # Craigslist via Open RSS
    for feed in config.get("craigslist", []):
        url = feed.get("url", "")
        label = feed.get("label", url)
        if not url:
            continue
        logger.info("Fetching Craigslist: %s...", label)
        results.append(_fetch_rss(url, "craigslist", label))

    # HN Freelancer thread
    if config.get("hn_freelancer", {}).get("enabled", False):
        logger.info("Fetching HN Freelancer thread...")
        results.append(_fetch_hn_freelancer())

    return results
