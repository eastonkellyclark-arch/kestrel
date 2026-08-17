"""The Translator — converts raw listings from each source into the common schema.

Each source parser extracts the same fields. Raw data is never modified.
"""

import json
import logging
import re
from datetime import datetime

from .database import get_connection
from .desc_quality import classify as classify_description
from .normalize import normalize_company, normalize_title
from .remote_detect import detect_remote

logger = logging.getLogger("kestrel.translator")

# Sanitize HTML: keep structural tags, strip everything else.
# This preserves list formatting for display while staying safe.
_SAFE_TAGS = {"p", "br", "ul", "ol", "li", "h1", "h2", "h3", "h4", "h5", "h6",
              "strong", "b", "em", "i", "div", "span"}
_TAG_RE = re.compile(r"<(/?)(\w+)([^>]*)>", re.IGNORECASE)
_MULTI_NEWLINE = re.compile(r"\n{3,}")
_MULTI_BR = re.compile(r"(<br\s*/?>){3,}", re.IGNORECASE)


def _sanitize_html(html: str) -> str:
    """Keep safe structural tags, strip attributes and dangerous tags."""
    # Decode HTML entities first — Greenhouse encodes tags as &lt;p&gt;
    import html as html_mod
    html = html_mod.unescape(html)

    def _replace_tag(m: re.Match) -> str:
        slash = m.group(1)
        tag = m.group(2).lower()
        if tag in _SAFE_TAGS:
            return f"<{slash}{tag}>"
        # Replace block-level removed tags with newline, inline with nothing
        if tag in ("div", "section", "article", "header", "footer", "table", "tr", "td", "th"):
            return "\n"
        return ""
    result = _TAG_RE.sub(_replace_tag, html)
    result = re.sub(r"&nbsp;", " ", result)
    result = _MULTI_BR.sub("<br>", result)
    return result.strip()


def _strip_html(html: str) -> str:
    """Strip ALL HTML to plaintext. Used for desc_quality classification."""
    import html as html_mod
    html = html_mod.unescape(html)
    text = re.sub(r"<[^>]+>", "\n", html)
    text = re.sub(r"&\w+;", " ", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = _MULTI_NEWLINE.sub("\n\n", text)
    return text.strip()


def _parse_greenhouse(raw: dict, board_slug: str) -> dict | None:
    """Parse a Greenhouse raw job record."""
    source_id = str(raw.get("id", ""))
    if not source_id:
        return None

    title = raw.get("title", "").strip()
    company = raw.get("company_name", board_slug).strip()
    if not title:
        return None

    # Location
    loc = raw.get("location", {})
    location = loc.get("name", "") if isinstance(loc, dict) else str(loc)

    # Description: sanitized HTML for display, plaintext for classification
    raw_html = raw.get("content", "") or ""
    description = _sanitize_html(raw_html)
    desc_plain = _strip_html(raw_html)

    # URL
    url = raw.get("absolute_url", "")

    # Posted date
    posted_at = raw.get("first_published") or raw.get("updated_at") or ""
    if posted_at:
        posted_at = posted_at[:19]  # trim timezone suffix

    # Department
    departments = raw.get("departments", [])
    department = departments[0].get("name", "") if departments else ""

    # Remote detection (uses plaintext)
    is_remote, remote_conf = detect_remote(
        location=location, title=title, description=desc_plain,
    )

    return {
        "source": "greenhouse",
        "source_id": source_id,
        "board_slug": board_slug,
        "listing_type": "job",
        "title_display": title,
        "company_display": company,
        "location_display": location,
        "title_normalized": normalize_title(title),
        "company_normalized": normalize_company(company),
        "description": description,
        "url": url,
        "posted_at": posted_at,
        "department": department,
        "is_remote": int(is_remote),
        "remote_confidence": remote_conf,
        "description_quality": classify_description(desc_plain, title),
    }


def _parse_lever(raw: dict, board_slug: str) -> dict | None:
    """Parse a Lever raw posting record."""
    source_id = str(raw.get("id", ""))
    if not source_id:
        return None

    title = raw.get("text", "").strip()
    if not title:
        return None

    # Lever doesn't include company name in the posting — use registry slug
    # The registry maps slug → company name; we pass it as board_slug
    company = board_slug  # Will be overridden below via registry lookup

    # Location
    cats = raw.get("categories", {})
    location = cats.get("location", "")
    all_locs = cats.get("allLocations", [])
    if all_locs and not location:
        location = ", ".join(all_locs)

    # Description — combine all text sections
    # Sanitized HTML for display, plaintext for classification
    html_parts = []
    plain_parts = []
    for field in ("description", "additional", "opening"):
        text = raw.get(field, "")
        if text:
            html_parts.append(_sanitize_html(text))
            plain_parts.append(_strip_html(text))
    for lst in raw.get("lists", []):
        header = lst.get("text", "")
        content_html = lst.get("content", "")
        if header:
            html_parts.append(f"<strong>{header}</strong>")
            plain_parts.append(header)
        if content_html:
            html_parts.append(_sanitize_html(content_html))
            plain_parts.append(_strip_html(content_html))
    description = "\n".join(html_parts)
    desc_plain = "\n\n".join(plain_parts)

    url = raw.get("hostedUrl", "")

    # Posted date (Lever uses epoch ms)
    created_at_ms = raw.get("createdAt", 0)
    posted_at = ""
    if created_at_ms:
        posted_at = datetime.utcfromtimestamp(created_at_ms / 1000).isoformat()[:19]

    department = cats.get("team", "")

    workplace_type = raw.get("workplaceType", "")

    is_remote, remote_conf = detect_remote(
        location=location, title=title, description=desc_plain,
        workplace_type=workplace_type,
    )

    return {
        "source": "lever",
        "source_id": source_id,
        "board_slug": board_slug,
        "listing_type": "job",
        "title_display": title,
        "company_display": company,  # placeholder — resolved below
        "location_display": location,
        "title_normalized": normalize_title(title),
        "company_normalized": normalize_company(company),
        "description": description,
        "url": url,
        "posted_at": posted_at,
        "department": department,
        "is_remote": int(is_remote),
        "remote_confidence": remote_conf,
        "description_quality": classify_description(desc_plain, title),
    }


PARSERS = {
    "greenhouse": _parse_greenhouse,
    "lever": _parse_lever,
}


def translate_all() -> dict:
    """Translate all raw listings into normalized listings. Returns stats."""
    conn = get_connection()

    # Build slug → company name map from registry
    registry_rows = conn.execute(
        "SELECT board_slug, company, platform FROM registry"
    ).fetchall()
    slug_to_company = {}
    for r in registry_rows:
        slug_to_company[(r["platform"], r["board_slug"])] = r["company"]

    raw_rows = conn.execute(
        "SELECT id, source, board_slug, source_id, raw_json FROM raw_listings"
    ).fetchall()
    conn.close()

    stats = {"total": len(raw_rows), "translated": 0, "skipped": 0, "errors": 0}
    now = datetime.utcnow().isoformat()[:19]
    parsed_listings = []

    for row in raw_rows:
        source = row["source"]
        parser = PARSERS.get(source)
        if not parser:
            stats["skipped"] += 1
            continue

        try:
            raw = json.loads(row["raw_json"])
            record = parser(raw, row["board_slug"])
        except Exception as e:
            logger.error("Parse error for %s/%s: %s", source, row["source_id"], e)
            stats["errors"] += 1
            continue

        if not record:
            stats["skipped"] += 1
            continue

        # Resolve company name from registry for Lever
        if source == "lever":
            real_name = slug_to_company.get(("lever", row["board_slug"]), row["board_slug"])
            record["company_display"] = real_name
            record["company_normalized"] = normalize_company(real_name)

        record["created_at"] = now
        parsed_listings.append(record)

    # Bulk insert
    conn = get_connection()
    inserted = 0
    for rec in parsed_listings:
        try:
            conn.execute(
                """
                INSERT INTO listings (
                    listing_type, source, source_id, board_slug,
                    title_display, company_display, location_display,
                    title_normalized, company_normalized,
                    description, url, posted_at, department,
                    is_remote, remote_confidence,
                    description_quality,
                    created_at
                ) VALUES (
                    :listing_type, :source, :source_id, :board_slug,
                    :title_display, :company_display, :location_display,
                    :title_normalized, :company_normalized,
                    :description, :url, :posted_at, :department,
                    :is_remote, :remote_confidence,
                    :description_quality,
                    :created_at
                )
                """,
                rec,
            )
            inserted += 1
        except Exception:
            # Already translated (UNIQUE constraint)
            pass
    conn.commit()
    conn.close()

    stats["translated"] = inserted
    logger.info(
        "Translated %d of %d raw listings (%d skipped, %d errors)",
        inserted, stats["total"], stats["skipped"], stats["errors"],
    )
    return stats
