"""The Sniffer — identifies which ATS a company uses from their careers page URL.

Takes a URL, fetches it, inspects the HTML for ATS signatures.
On failure, returns what it found so the user can provide the slug manually.

Workable removed — public API returns 0 results for all tested companies
as of Aug 2026. Detection patterns kept so the Sniffer can identify the
platform and tell the user "this is Workable, but there's no public API."
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
    html = resp.text[:100_000]
    for pattern, platform, extractor in _HTML_PATTERNS:
        m = pattern.search(html)
        if m:
            slug = extractor(m) if extractor else None
            confidence = "high" if slug else "medium"
            return SniffResult(url, platform, slug, confidence,
                               f"HTML contains {platform} embed/reference")

    # Step 4: Slug-guess fallback — derive candidate slugs from the domain
    # and probe each ATS API directly. Catches JS-rendered embeds.
    slug_guesses = _derive_slug_guesses(url)
    if slug_guesses:
        probe_result = _probe_ats_apis(url, slug_guesses, timeout)
        if probe_result:
            return probe_result

    return SniffResult(url, None, None, "failed",
                       "No recognized ATS pattern found in URL, page HTML, or API probe")


def _derive_slug_guesses(url: str) -> list[str]:
    """Extract candidate board slugs from a URL's domain name."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    host = parsed.hostname or ""
    parts = host.replace("www.", "").replace("careers.", "").replace("jobs.", "").split(".")
    if not parts:
        return []
    base = parts[0]
    guesses = [base]
    if "-" in base:
        guesses.append(base.replace("-", ""))
    guesses.append(base + "inc")
    guesses.append(base + "hq")
    return guesses


# ATS API probe endpoints: (platform, url_template, response_validator)
_PROBE_ENDPOINTS = [
    ("greenhouse", "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
     lambda d: "jobs" in d),
    ("lever", "https://api.lever.co/v0/postings/{slug}?mode=json",
     lambda d: isinstance(d, list)),
    ("ashby", "https://api.ashbyhq.com/posting-api/job-board/{slug}",
     lambda d: "jobs" in d),
]


def _probe_ats_apis(original_url: str, slugs: list[str], timeout: float) -> SniffResult | None:
    """Try each slug against each ATS API. Return first hit."""
    for slug in slugs:
        for platform, url_template, validator in _PROBE_ENDPOINTS:
            probe_url = url_template.format(slug=slug)
            try:
                resp = httpx.get(probe_url, timeout=timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    if validator(data):
                        logger.info("API probe hit: %s/%s", platform, slug)
                        return SniffResult(
                            original_url, platform, slug, "high",
                            f"API probe: {platform} board '{slug}' exists and returns data",
                        )
            except Exception:
                continue
    return None
