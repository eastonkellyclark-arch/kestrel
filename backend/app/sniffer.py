"""The Sniffer — identifies which ATS a company uses from their careers page URL.

Takes a URL, fetches it, inspects the HTML for ATS signatures.
On failure, returns what it found so the user can provide the slug manually.
"""

import logging
import re
from dataclasses import dataclass

import httpx

logger = logging.getLogger("kestrel.sniffer")


@dataclass
class SniffResult:
    url: str
    platform: str | None
    board_slug: str | None
    confidence: str  # "high", "medium", "low", "failed"
    reason: str


# ATS detection patterns: (regex on URL or HTML, platform, slug extractor)
_URL_PATTERNS = [
    # Greenhouse
    (re.compile(r"boards\.greenhouse\.io/(\w+)", re.I), "greenhouse",
     lambda m: m.group(1)),
    (re.compile(r"job-boards\.greenhouse\.io/(\w+)", re.I), "greenhouse",
     lambda m: m.group(1)),
    # Lever
    (re.compile(r"jobs\.lever\.co/([^/?\s]+)", re.I), "lever",
     lambda m: m.group(1)),
    # Ashby
    (re.compile(r"jobs\.ashbyhq\.com/([^/?\s]+)", re.I), "ashby",
     lambda m: m.group(1)),
    # Workable
    (re.compile(r"apply\.workable\.com/([^/?\s]+)", re.I), "workable",
     lambda m: m.group(1)),
    # Recruitee
    (re.compile(r"([^/.\s]+)\.recruitee\.com", re.I), "recruitee",
     lambda m: m.group(1)),
]

_HTML_PATTERNS = [
    # Greenhouse embed
    (re.compile(r'id=["\']grnhse_app["\']', re.I), "greenhouse", None),
    (re.compile(r"boards\.greenhouse\.io/(\w+)", re.I), "greenhouse",
     lambda m: m.group(1)),
    (re.compile(r"job-boards\.greenhouse\.io/(\w+)", re.I), "greenhouse",
     lambda m: m.group(1)),
    # Lever embed
    (re.compile(r"jobs\.lever\.co/([^/\"'\s]+)", re.I), "lever",
     lambda m: m.group(1)),
    # Ashby embed
    (re.compile(r"jobs\.ashbyhq\.com/([^/\"'\s]+)", re.I), "ashby",
     lambda m: m.group(1)),
    # Workable embed
    (re.compile(r"apply\.workable\.com/([^/\"'\s]+)", re.I), "workable",
     lambda m: m.group(1)),
    (re.compile(r'whr-embed["\']', re.I), "workable", None),
    # Recruitee embed
    (re.compile(r"([^/\"'\s]+)\.recruitee\.com", re.I), "recruitee",
     lambda m: m.group(1)),
]


def sniff(url: str, timeout: float = 15.0) -> SniffResult:
    """Identify the ATS from a careers page URL."""
    # Step 1: Check the URL itself
    for pattern, platform, extractor in _URL_PATTERNS:
        m = pattern.search(url)
        if m:
            slug = extractor(m) if extractor else None
            return SniffResult(url, platform, slug, "high",
                               f"URL matches {platform} pattern")

    # Step 2: Fetch the page and inspect HTML
    try:
        resp = httpx.get(url, timeout=timeout, follow_redirects=True,
                         headers={"User-Agent": "Kestrel/1.0 (careers page detector)"})
    except httpx.ConnectError as e:
        return SniffResult(url, None, None, "failed", f"Connection failed: {e}")
    except httpx.TimeoutException:
        return SniffResult(url, None, None, "failed", "Request timed out")
    except httpx.HTTPError as e:
        return SniffResult(url, None, None, "failed", str(e))

    if resp.status_code != 200:
        return SniffResult(url, None, None, "failed",
                           f"HTTP {resp.status_code}")

    # Check final URL after redirects
    final_url = str(resp.url)
    for pattern, platform, extractor in _URL_PATTERNS:
        m = pattern.search(final_url)
        if m:
            slug = extractor(m) if extractor else None
            return SniffResult(url, platform, slug, "high",
                               f"Redirected to {platform} URL: {final_url}")

    # Check HTML body
    html = resp.text[:100_000]  # limit scan to first 100KB
    for pattern, platform, extractor in _HTML_PATTERNS:
        m = pattern.search(html)
        if m:
            slug = extractor(m) if extractor else None
            confidence = "high" if slug else "medium"
            return SniffResult(url, platform, slug, confidence,
                               f"HTML contains {platform} embed/reference")

    return SniffResult(url, None, None, "failed",
                       "No recognized ATS pattern found in URL or page HTML")
