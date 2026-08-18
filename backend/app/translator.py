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


def _parse_adzuna(raw: dict, board_slug: str) -> dict | None:
    """Parse an Adzuna raw job record."""
    source_id = str(raw.get("id", ""))
    if not source_id:
        return None

    title = raw.get("title", "").strip()
    if not title:
        return None

    company_data = raw.get("company", {})
    company = company_data.get("display_name", "") if isinstance(company_data, dict) else str(company_data)
    if not company:
        company = "Unknown"

    location_data = raw.get("location", {})
    if isinstance(location_data, dict):
        area = location_data.get("area", [])
        location = ", ".join(area) if area else location_data.get("display_name", "")
    else:
        location = str(location_data)

    # Adzuna descriptions are truncated snippets
    raw_desc = raw.get("description", "") or ""
    description = _sanitize_html(raw_desc)
    desc_plain = _strip_html(raw_desc)

    url = raw.get("redirect_url", "")
    posted_at = raw.get("created", "")
    if posted_at:
        posted_at = posted_at[:19]

    is_remote, remote_conf = detect_remote(
        location=location, title=title, description=desc_plain,
    )

    return {
        "source": "adzuna",
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
        "department": "",
        "is_remote": int(is_remote),
        "remote_confidence": remote_conf,
        "description_quality": classify_description(desc_plain, title, source="adzuna"),
    }


def _parse_usajobs(raw: dict, board_slug: str) -> dict | None:
    """Parse a USAJobs raw result item."""
    match = raw.get("MatchedObjectDescriptor", raw)
    source_id = str(match.get("PositionID", ""))
    if not source_id:
        return None

    title = match.get("PositionTitle", "").strip()
    if not title:
        return None

    company = match.get("OrganizationName", match.get("DepartmentName", ""))

    location_names = match.get("PositionLocation", [])
    if isinstance(location_names, list) and location_names:
        location = "; ".join(
            loc.get("LocationName", "") for loc in location_names if isinstance(loc, dict)
        )
    else:
        location = str(location_names)

    raw_desc = match.get("UserArea", {}).get("Details", {}).get("MajorDuties", [])
    if isinstance(raw_desc, list):
        description = "<ul>" + "".join(f"<li>{d}</li>" for d in raw_desc) + "</ul>"
        desc_plain = "\n".join(raw_desc)
    else:
        description = str(raw_desc)
        desc_plain = _strip_html(description)

    # Also include qualifications
    quals = match.get("QualificationSummary", "")
    if quals:
        description += f"\n<h3>Qualifications</h3>\n<p>{quals}</p>"
        desc_plain += f"\n{quals}"

    url = match.get("PositionURI", match.get("ApplyURI", [""])[0] if isinstance(match.get("ApplyURI"), list) else "")
    posted_at = match.get("PublicationStartDate", "")
    if posted_at:
        posted_at = posted_at[:19]

    is_remote, remote_conf = detect_remote(
        location=location, title=title, description=desc_plain,
    )

    return {
        "source": "usajobs",
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
        "department": "",
        "is_remote": int(is_remote),
        "remote_confidence": remote_conf,
        "description_quality": classify_description(desc_plain, title),
    }


def _parse_ashby(raw: dict, board_slug: str) -> dict | None:
    """Parse an Ashby raw job record."""
    source_id = str(raw.get("id", ""))
    if not source_id:
        return None

    title = raw.get("title", "").strip()
    if not title:
        return None

    # Ashby doesn't include company name — resolved from registry below
    company = board_slug

    location = raw.get("location", "")
    # Include secondary locations
    secondary = raw.get("secondaryLocations", [])
    if secondary:
        sec_names = [s.get("location", "") for s in secondary if isinstance(s, dict)]
        if sec_names:
            location = "; ".join([location] + [s for s in sec_names if s])

    # Description — Ashby provides both HTML and plain
    desc_html = raw.get("descriptionHtml", "")
    desc_plain = raw.get("descriptionPlain", "")
    description = _sanitize_html(desc_html) if desc_html else desc_plain
    if not desc_plain and desc_html:
        desc_plain = _strip_html(desc_html)

    url = raw.get("jobUrl", "")
    posted_at = raw.get("publishedAt", "")
    if posted_at:
        posted_at = posted_at[:19]

    department = raw.get("department", "")

    # Ashby has explicit isRemote and workplaceType fields
    workplace_type = raw.get("workplaceType", "")
    is_remote_flag = raw.get("isRemote", False)

    is_remote, remote_conf = detect_remote(
        location=location, title=title, description=desc_plain,
        workplace_type="remote" if is_remote_flag else workplace_type.lower(),
    )

    return {
        "source": "ashby",
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


def _parse_recruitee(raw: dict, board_slug: str) -> dict | None:
    """Parse a Recruitee raw offer record."""
    source_id = str(raw.get("id", ""))
    if not source_id:
        return None

    title = raw.get("title", "").strip()
    if not title:
        return None

    company = raw.get("company_name", board_slug).strip()

    location = raw.get("location", "")
    city = raw.get("city", "")
    country = raw.get("country", "")
    if not location and city:
        location = f"{city}, {country}" if country else city

    # Description — Recruitee provides HTML in description + requirements
    desc_html = raw.get("description", "")
    req_html = raw.get("requirements", "")
    full_html = desc_html
    if req_html:
        full_html += "\n<h3>Requirements</h3>\n" + req_html
    description = _sanitize_html(full_html)
    desc_plain = _strip_html(full_html)

    url = raw.get("careers_url", raw.get("careers_apply_url", ""))
    posted_at = raw.get("published_at", raw.get("created_at", ""))
    if posted_at:
        posted_at = posted_at[:19]

    department = raw.get("department", "")

    is_remote_flag = raw.get("remote", False)
    is_remote, remote_conf = detect_remote(
        location=location, title=title, description=desc_plain,
        workplace_type="remote" if is_remote_flag else "",
    )

    return {
        "source": "recruitee",
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


def _parse_remote_feed(raw: dict, board_slug: str) -> dict | None:
    """Parse a remote feed job (RemoteOK, Remotive, We Work Remotely).

    Everything on these feeds is remote by definition — set is_remote=True
    unconditionally rather than relying on the heuristic.
    """
    source_id = str(raw.get("source_id", raw.get("id", "")))

    # WWR stores raw RSS items — generate source_id from link
    if not source_id and raw.get("link"):
        source_id = re.sub(r"[^a-z0-9]", "-", raw["link"].lower().rsplit("/", 1)[-1])
    if not source_id:
        return None

    title = raw.get("title", raw.get("position", "")).strip()
    if not title:
        return None

    company = raw.get("company", raw.get("company_name", "")).strip()

    # WWR titles are "Company: Title" format
    if not company and ": " in title:
        company, title = title.split(": ", 1)
        company = company.strip()
        title = title.strip()

    if not company:
        company = "Unknown"

    location = raw.get("location", raw.get("candidate_required_location",
                raw.get("region", "Worldwide")))
    if not location:
        location = "Worldwide"

    raw_desc = raw.get("description", "")
    import html as html_mod
    raw_desc = html_mod.unescape(raw_desc)
    description = _sanitize_html(raw_desc)
    desc_plain = _strip_html(raw_desc)

    url = raw.get("url", raw.get("link", ""))

    posted_at = raw.get("posted_at", raw.get("date", raw.get("publication_date", raw.get("pubDate", ""))))
    if posted_at:
        # Handle various date formats
        posted_at = posted_at[:19]

    tags = raw.get("tags", [])
    department = tags[0] if tags and isinstance(tags[0], str) else ""

    return {
        "source": board_slug,  # remoteok, remotive, or weworkremotely
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
        "is_remote": 1,  # remote by definition on these feeds
        "remote_confidence": 1.0,
        "description_quality": classify_description(desc_plain, title),
    }


PARSERS = {
    "greenhouse": _parse_greenhouse,
    "lever": _parse_lever,
    "adzuna": _parse_adzuna,
    "usajobs": _parse_usajobs,
    "ashby": _parse_ashby,
    "recruitee": _parse_recruitee,
    "remoteok": _parse_remote_feed,
    "remotive": _parse_remote_feed,
    "weworkremotely": _parse_remote_feed,
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

        # Resolve company name from registry for platforms that don't
        # include it in the posting data (Lever, Ashby)
        if source in ("lever", "ashby"):
            real_name = slug_to_company.get((source, row["board_slug"]), row["board_slug"])
            record["company_display"] = real_name
            record["company_normalized"] = normalize_company(real_name)

        record["created_at"] = now
        parsed_listings.append(record)

    # Bulk upsert: insert new, update existing (re-translate mode).
    # Status, notes, and history live in separate tables so they survive.
    conn = get_connection()
    inserted = 0
    updated = 0
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
            # Already exists — update content fields. Preserves status, notes, history.
            conn.execute(
                """
                UPDATE listings SET
                    title_display = :title_display,
                    company_display = :company_display,
                    location_display = :location_display,
                    title_normalized = :title_normalized,
                    company_normalized = :company_normalized,
                    description = :description,
                    url = :url,
                    posted_at = :posted_at,
                    department = :department,
                    is_remote = :is_remote,
                    remote_confidence = :remote_confidence,
                    description_quality = :description_quality
                WHERE source = :source AND source_id = :source_id
                """,
                rec,
            )
            updated += 1
    conn.commit()
    conn.close()

    stats["translated"] = inserted
    stats["updated"] = updated
    logger.info(
        "Translated %d new, updated %d existing of %d raw listings (%d skipped, %d errors)",
        inserted, updated, stats["total"], stats["skipped"], stats["errors"],
    )
    return stats
