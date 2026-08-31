"""Gmail alert channel adapter.

Read-only Gmail scope. Never send, delete, or modify.
Only processes messages from configured alert senders.

Each sender has its own parser with per-sender failure isolation:
a broken LinkedIn parser must not stop the Indeed one.

Alert URLs are tracking-wrapped — unwrapped before storage for dedupe.
"""

import base64
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path

from ..models import FetchOutcome, FetchResult
from ..repository import store_raw_listing
from ..settings import settings

logger = logging.getLogger("kestrel.gmail")

# Alert senders we process — nothing else in the mailbox is read
ALERT_SENDERS = {
    "linkedin": {
        "from_patterns": ["jobs-noreply@linkedin.com", "jobalerts-noreply@linkedin.com"],
        "parser": "_parse_linkedin_alert",
    },
    "indeed": {
        "from_patterns": ["alert@indeed.com", "noreply@indeed.com",
                          "donotreply@match.indeed.com", "no-reply@indeed.com"],
        "parser": "_parse_indeed_alert",
    },
    "ziprecruiter": {
        "from_patterns": ["noreply@ziprecruiter.com", "alert@ziprecruiter.com"],
        "parser": "_parse_ziprecruiter_alert",
    },
    "glassdoor": {
        "from_patterns": ["noreply@glassdoor.com", "alerts@glassdoor.com"],
        "parser": "_parse_glassdoor_alert",
    },
}

# Tracking URL unwrap patterns
_TRACKING_PATTERNS = [
    # LinkedIn tracking
    re.compile(r"https?://www\.linkedin\.com/comm/jobs/view/(\d+)"),
    # Indeed tracking redirect
    re.compile(r"https?://(?:www\.)?indeed\.com/rc/clk\?.*?&jk=([a-f0-9]+)"),
    # Generic redirect wrappers
    re.compile(r"[?&]url=([^&]+)"),
    re.compile(r"[?&]redirect=([^&]+)"),
]


def unwrap_tracking_url(url: str) -> str:
    """Unwrap tracking/redirect URLs to get the actual job posting URL.

    Critical for dedupe — the same job appears with different tracking
    wrappers from different alert emails.
    """
    if not url:
        return url

    # LinkedIn job view URLs — extract job ID
    m = re.search(r"linkedin\.com/(?:comm/)?jobs/view/(\d+)", url)
    if m:
        return f"https://www.linkedin.com/jobs/view/{m.group(1)}"

    # Indeed click tracking — extract job key
    m = re.search(r"indeed\.com/rc/clk\?.*?jk=([a-f0-9]+)", url)
    if m:
        return f"https://www.indeed.com/viewjob?jk={m.group(1)}"

    # URL-encoded redirect parameter
    from urllib.parse import unquote
    m = re.search(r"[?&](?:url|redirect|dest)=([^&]+)", url)
    if m:
        return unquote(m.group(1))

    return url


def _extract_jobs_from_html(html: str, sender: str) -> list[dict]:
    """Extract job listings from an alert email HTML body.

    Each sender has a different format. Returns list of dicts with:
    title, company, location, url, source_id
    """
    parser_fn = {
        "linkedin": _parse_linkedin_alert,
        "indeed": _parse_indeed_alert,
        "ziprecruiter": _parse_ziprecruiter_alert,
        "glassdoor": _parse_glassdoor_alert,
    }.get(sender)

    if not parser_fn:
        logger.warning("No parser for sender: %s", sender)
        return []

    try:
        return parser_fn(html)
    except Exception as e:
        logger.error("Parser failed for %s: %s", sender, e)
        return []


def _parse_linkedin_alert(html: str) -> list[dict]:
    """Parse LinkedIn job alert email HTML."""
    jobs = []
    # LinkedIn alerts contain job cards with title, company, location, and link
    # Pattern: <a href="...linkedin.com/comm/jobs/view/ID...">Title</a>
    # followed by company and location text
    pattern = re.compile(
        r'href="(https?://[^"]*linkedin\.com/(?:comm/)?jobs/view/(\d+)[^"]*)"[^>]*>'
        r'\s*([^<]+?)\s*</a>',
        re.IGNORECASE | re.DOTALL,
    )
    for m in pattern.finditer(html):
        raw_url = m.group(1)
        job_id = m.group(2)
        title = re.sub(r'\s+', ' ', m.group(3)).strip()
        if not title or len(title) < 3:
            continue

        # Try to find company/location after the title link
        after = html[m.end():m.end() + 500]
        company = ""
        location = ""
        # Common patterns in LinkedIn alert HTML
        comp_m = re.search(r'(?:company|employer)[^>]*>([^<]+)', after, re.I)
        if comp_m:
            company = comp_m.group(1).strip()
        loc_m = re.search(r'(?:location|place)[^>]*>([^<]+)', after, re.I)
        if loc_m:
            location = loc_m.group(1).strip()

        jobs.append({
            "source_id": f"linkedin-{job_id}",
            "title": title,
            "company": company,
            "location": location,
            "url": unwrap_tracking_url(raw_url),
        })
    return jobs


def _parse_indeed_alert(html: str) -> list[dict]:
    """Parse Indeed job alert email HTML."""
    jobs = []
    # Indeed alerts: <a href="...indeed.com/rc/clk?jk=KEY...">Title</a>
    pattern = re.compile(
        r'href="(https?://[^"]*indeed\.com/rc/clk[^"]*jk=([a-f0-9]+)[^"]*)"[^>]*>'
        r'\s*([^<]+?)\s*</a>',
        re.IGNORECASE | re.DOTALL,
    )
    for m in pattern.finditer(html):
        raw_url = m.group(1)
        job_key = m.group(2)
        title = re.sub(r'\s+', ' ', m.group(3)).strip()
        if not title or len(title) < 3:
            continue

        after = html[m.end():m.end() + 500]
        company = ""
        location = ""
        comp_m = re.search(r'(?:company|employer)[^>]*>([^<]+)', after, re.I)
        if comp_m:
            company = comp_m.group(1).strip()
        loc_m = re.search(r'(?:location|place)[^>]*>([^<]+)', after, re.I)
        if loc_m:
            location = loc_m.group(1).strip()

        jobs.append({
            "source_id": f"indeed-{job_key}",
            "title": title,
            "company": company,
            "location": location,
            "url": unwrap_tracking_url(raw_url),
        })
    return jobs


def _parse_ziprecruiter_alert(html: str) -> list[dict]:
    """Parse ZipRecruiter job alert email HTML."""
    jobs = []
    pattern = re.compile(
        r'href="(https?://[^"]*ziprecruiter\.com/[^"]*)"[^>]*>\s*([^<]+?)\s*</a>',
        re.IGNORECASE | re.DOTALL,
    )
    for m in pattern.finditer(html):
        raw_url = m.group(1)
        title = re.sub(r'\s+', ' ', m.group(2)).strip()
        if not title or len(title) < 5 or title.lower() in ("view all jobs", "unsubscribe", "see more"):
            continue

        # Generate ID from URL
        source_id = re.sub(r'[^a-z0-9]', '-', raw_url.lower().split('/')[-1])[:50]

        after = html[m.end():m.end() + 500]
        company = ""
        location = ""
        comp_m = re.search(r'>([^<]{3,40})</(?:span|td|div)', after)
        if comp_m:
            company = comp_m.group(1).strip()

        jobs.append({
            "source_id": f"zip-{source_id}",
            "title": title,
            "company": company,
            "location": location,
            "url": unwrap_tracking_url(raw_url),
        })
    return jobs


def _parse_glassdoor_alert(html: str) -> list[dict]:
    """Parse Glassdoor job alert email HTML."""
    jobs = []
    pattern = re.compile(
        r'href="(https?://[^"]*glassdoor\.com/[^"]*job[^"]*)"[^>]*>\s*([^<]+?)\s*</a>',
        re.IGNORECASE | re.DOTALL,
    )
    for m in pattern.finditer(html):
        raw_url = m.group(1)
        title = re.sub(r'\s+', ' ', m.group(2)).strip()
        if not title or len(title) < 5 or title.lower() in ("view all", "see all jobs"):
            continue

        source_id = re.sub(r'[^a-z0-9]', '-', raw_url.lower().split('?')[0].split('/')[-1])[:50]

        jobs.append({
            "source_id": f"glassdoor-{source_id}",
            "title": title,
            "company": "",
            "location": "",
            "url": unwrap_tracking_url(raw_url),
        })
    return jobs


def _identify_sender(from_header: str) -> str | None:
    """Match a From header to a known alert sender."""
    from_lower = from_header.lower()
    for sender_name, config in ALERT_SENDERS.items():
        for pattern in config["from_patterns"]:
            if pattern in from_lower:
                return sender_name
    return None


def _is_headless() -> bool:
    """True when there is no human present to complete a browser consent.

    GitHub Actions sets CI=true. KESTREL_HEADLESS forces the same behaviour
    for cron and container runs.
    """
    return bool(os.environ.get("CI") or os.environ.get("KESTREL_HEADLESS"))


def fetch_alerts(credentials_path: str, token_path: str,
                 max_results: int = 50,
                 allow_interactive: bool | None = None) -> list[FetchResult]:
    """Fetch job alerts from Gmail. Requires OAuth credentials.

    Returns one FetchResult per sender — per-sender failure isolation.

    A stored token with a refresh token renews without a browser, so this runs
    headlessly in CI. Only the FIRST authorisation needs a human. When there is
    no human — `allow_interactive=False`, or CI detected — this refuses and
    says so rather than calling run_local_server(), which would block on a
    browser that will never open until the job hits its timeout.
    """
    if allow_interactive is None:
        allow_interactive = not _is_headless()
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        return [FetchResult("Gmail", "gmail_alert", "inbox",
                            FetchOutcome.NETWORK_ERROR,
                            error_detail="google-api-python-client not installed. "
                            "Run: pip install google-api-python-client google-auth-oauthlib")]

    SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

    # Load or create credentials
    creds = None
    token_file = Path(token_path)
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                # A dead refresh token used to propagate out of here and take
                # the whole fetch step down with it. Google expires refresh
                # tokens after 7 days while the OAuth consent screen is in
                # "Testing" publishing status, so this is the expected failure
                # mode, not an exceptional one.
                detail = str(e)
                if "invalid_grant" in detail or "expired or revoked" in detail:
                    detail = (
                        "Gmail refresh token is expired or revoked. Google expires "
                        "refresh tokens after 7 days while the OAuth consent screen is "
                        "in 'Testing' publishing status. Set the consent screen to "
                        "'In production' in Google Cloud Console, re-authorise locally, "
                        "and update the GMAIL_TOKEN_JSON secret. "
                        f"(original: {e})"
                    )
                logger.error("Gmail authorisation failed: %s", detail)
                return [FetchResult("Gmail", "gmail_alert", "inbox",
                                    FetchOutcome.NETWORK_ERROR, error_detail=detail)]
        else:
            if not Path(credentials_path).exists():
                return [FetchResult("Gmail", "gmail_alert", "inbox",
                                    FetchOutcome.NETWORK_ERROR,
                                    error_detail=f"Credentials file not found: {credentials_path}")]
            if not allow_interactive:
                return [FetchResult(
                    "Gmail", "gmail_alert", "inbox",
                    FetchOutcome.NETWORK_ERROR,
                    error_detail=(
                        f"Gmail needs interactive authorisation and none is possible here "
                        f"(no valid token at {token_path}). Run the pipeline locally once to "
                        f"complete the browser consent, then put the resulting token JSON in "
                        f"the GMAIL_TOKEN_JSON Actions secret. Refusing to open a browser "
                        f"that nothing can answer."
                    ),
                )]
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)

        try:
            token_file.write_text(creds.to_json())
            logger.info("Gmail token saved to %s", token_file)
        except OSError as e:
            # A read-only or ephemeral token path is survivable — the refreshed
            # credential is still good for this run.
            logger.warning("Could not persist refreshed Gmail token to %s: %s", token_file, e)

    service = build("gmail", "v1", credentials=creds)

    # Build query: only from configured alert senders
    all_from = []
    for config in ALERT_SENDERS.values():
        all_from.extend(config["from_patterns"])
    query = " OR ".join(f"from:{addr}" for addr in all_from)

    try:
        response = service.users().messages().list(
            userId="me", q=query, maxResults=max_results
        ).execute()
    except Exception as e:
        return [FetchResult("Gmail", "gmail_alert", "inbox",
                            FetchOutcome.NETWORK_ERROR, error_detail=str(e))]

    messages = response.get("messages", [])
    if not messages:
        return [FetchResult("Gmail", "gmail_alert", "inbox",
                            FetchOutcome.EMPTY_BOARD, job_count=0)]

    # Process each message, grouped by sender
    results_by_sender: dict[str, list[dict]] = {}
    errors_by_sender: dict[str, str] = {}
    now = datetime.utcnow()

    for msg_info in messages:
        try:
            msg = service.users().messages().get(
                userId="me", id=msg_info["id"], format="full"
            ).execute()
        except Exception as e:
            logger.error("Failed to fetch message %s: %s", msg_info["id"], e)
            continue

        # Get From header
        headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
        from_header = headers.get("from", "")
        sender = _identify_sender(from_header)
        if not sender:
            continue

        # Extract HTML body
        html_body = _extract_html_body(msg.get("payload", {}))
        if not html_body:
            continue

        # Parse with per-sender isolation
        try:
            jobs = _extract_jobs_from_html(html_body, sender)
            results_by_sender.setdefault(sender, []).extend(jobs)
        except Exception as e:
            errors_by_sender[sender] = str(e)
            logger.error("Parser failed for %s: %s", sender, e)

    # Store results and build per-sender FetchResults
    fetch_results = []
    for sender_name in ALERT_SENDERS:
        jobs = results_by_sender.get(sender_name, [])
        error = errors_by_sender.get(sender_name)

        if error:
            fetch_results.append(FetchResult(
                f"Gmail/{sender_name}", "gmail_alert", sender_name,
                FetchOutcome.NETWORK_ERROR, error_detail=error))
            continue

        stored = 0
        for job in jobs:
            sid = job.get("source_id", "")
            if not sid:
                continue
            raw_data = {**job, "gmail_sender": sender_name}
            if store_raw_listing("gmail_alert", sender_name, sid, raw_data, now):
                stored += 1

        if jobs:
            logger.info("Gmail/%s: %d jobs, %d new", sender_name, len(jobs), stored)
            fetch_results.append(FetchResult(
                f"Gmail/{sender_name}", "gmail_alert", sender_name,
                FetchOutcome.SUCCESS, job_count=len(jobs)))
        # Don't report senders with no messages — that's normal

    return fetch_results


def _extract_html_body(payload: dict) -> str | None:
    """Extract HTML body from Gmail message payload."""
    # Check top-level body
    if payload.get("mimeType") == "text/html":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    # Check parts
    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/html":
            data = part.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        # Nested multipart
        if part.get("parts"):
            result = _extract_html_body(part)
            if result:
                return result

    return None
