"""Phase 6 — The Desk API routes.

Private surface: status lifecycle, notes, history, pipeline view,
CSV/Markdown export, registry editor.

No authentication code — Cloudflare Access handles identity at the edge.
"""

import csv
import io
import json
import logging
import re
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from .database import get_connection
from .models import ATSPlatform, RegistryEntry
from .repository import upsert_registry

logger = logging.getLogger("kestrel.desk")

router = APIRouter(prefix="/desk")

VALID_STATUSES = {"new", "interested", "applied", "responded", "interview", "closed"}


# ── Models ───────────────────────────────────────────────────────────

class StatusChange(BaseModel):
    status: str
    note: str | None = None
    resume_id: int | None = None  # which resume was used (for "applied")


class NoteCreate(BaseModel):
    content: str


class RegistryCreate(BaseModel):
    company: str
    platform: str
    board_slug: str
    active: bool = True


class SniffRequest(BaseModel):
    url: str


# ── Adzuna budget ────────────────────────────────────────────────────

@router.get("/budget/adzuna")
def adzuna_budget():
    """Current Adzuna API call budget status."""
    from .adapters.adzuna import get_budget_status
    return get_budget_status()


# ── Sniffer ──────────────────────────────────────────────────────────

@router.post("/sniff")
def sniff_url(body: SniffRequest):
    """Identify the ATS from a careers page URL."""
    from .sniffer import sniff
    result = sniff(body.url)
    return {
        "url": result.url,
        "platform": result.platform,
        "board_slug": result.board_slug,
        "confidence": result.confidence,
        "reason": result.reason,
    }


# ── Status lifecycle ─────────────────────────────────────────────────

@router.patch("/listings/{listing_id}/status")
def update_status(listing_id: int, body: StatusChange):
    """Update status with timestamped history."""
    if body.status not in VALID_STATUSES:
        raise HTTPException(422, f"Invalid status '{body.status}'. Valid: {', '.join(sorted(VALID_STATUSES))}")

    conn = get_connection()
    row = conn.execute("SELECT id, status FROM listings WHERE id = ?", (listing_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, f"Listing {listing_id} not found")

    old_status = row["status"]
    now = datetime.utcnow().isoformat()

    conn.execute("UPDATE listings SET status = ? WHERE id = ?", (body.status, listing_id))
    conn.execute(
        "INSERT INTO status_history (listing_id, old_status, new_status, note, resume_id, changed_at) VALUES (?, ?, ?, ?, ?, ?)",
        (listing_id, old_status, body.status, body.note, body.resume_id, now),
    )
    conn.commit()
    conn.close()
    return {"id": listing_id, "old_status": old_status, "new_status": body.status, "changed_at": now}


@router.get("/listings/{listing_id}/history")
def get_history(listing_id: int):
    """Get timestamped status history for a listing."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, old_status, new_status, note, changed_at FROM status_history WHERE listing_id = ? ORDER BY changed_at",
        (listing_id,),
    ).fetchall()
    conn.close()
    return {"listing_id": listing_id, "history": [dict(r) for r in rows]}


# ── Notes ────────────────────────────────────────────────────────────

@router.post("/listings/{listing_id}/notes")
def add_note(listing_id: int, body: NoteCreate):
    """Add a note to a listing."""
    conn = get_connection()
    row = conn.execute("SELECT id FROM listings WHERE id = ?", (listing_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, f"Listing {listing_id} not found")

    now = datetime.utcnow().isoformat()
    cursor = conn.execute(
        "INSERT INTO notes (listing_id, content, created_at) VALUES (?, ?, ?)",
        (listing_id, body.content, now),
    )
    conn.commit()
    note_id = cursor.lastrowid
    conn.close()
    return {"id": note_id, "listing_id": listing_id, "content": body.content, "created_at": now}


@router.get("/listings/{listing_id}/notes")
def get_notes(listing_id: int):
    """Get all notes for a listing."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, content, created_at FROM notes WHERE listing_id = ? ORDER BY created_at",
        (listing_id,),
    ).fetchall()
    conn.close()
    return {"listing_id": listing_id, "notes": [dict(r) for r in rows]}


# ── Pipeline view ────────────────────────────────────────────────────

@router.get("/pipeline")
def pipeline_view():
    """Stage counts for the pipeline view."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT status, COUNT(*) as count
        FROM listings WHERE canonical_id IS NULL
        GROUP BY status ORDER BY
            CASE status
                WHEN 'new' THEN 1 WHEN 'interested' THEN 2 WHEN 'applied' THEN 3
                WHEN 'responded' THEN 4 WHEN 'interview' THEN 5 WHEN 'closed' THEN 6
            END
        """
    ).fetchall()
    conn.close()
    return {"stages": {r["status"]: r["count"] for r in rows}}


# ── Export ────────────────────────────────────────────────────────────

@router.get("/export/csv")
def export_csv():
    """Export listings with status and notes to CSV."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT l.id, l.company_display, l.title_display, l.location_display,
               l.is_remote, l.score, l.status, l.url, l.posted_at, l.source
        FROM listings l
        WHERE l.canonical_id IS NULL AND l.status != 'new'
        ORDER BY
            CASE l.status
                WHEN 'interested' THEN 1 WHEN 'applied' THEN 2 WHEN 'responded' THEN 3
                WHEN 'interview' THEN 4 WHEN 'closed' THEN 5
            END, l.score DESC
        """
    ).fetchall()

    # Get notes for each listing
    notes_map: dict[int, list[str]] = {}
    note_rows = conn.execute(
        "SELECT listing_id, content, created_at FROM notes ORDER BY created_at"
    ).fetchall()
    conn.close()
    for nr in note_rows:
        notes_map.setdefault(nr["listing_id"], []).append(
            f"[{nr['created_at'][:10]}] {nr['content']}"
        )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Company", "Title", "Location", "Remote", "Score", "Status", "URL", "Posted", "Source", "Notes"])
    for r in rows:
        notes_str = " | ".join(notes_map.get(r["id"], []))
        writer.writerow([
            r["id"], r["company_display"], r["title_display"], r["location_display"],
            "Yes" if r["is_remote"] else "No",
            f"{r['score']:.1f}" if r["score"] else "",
            r["status"], r["url"], r["posted_at"][:10] if r["posted_at"] else "",
            r["source"], notes_str,
        ])

    return PlainTextResponse(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=kestrel-export.csv"},
    )


@router.get("/export/markdown")
def export_markdown():
    """Export listings with status to Markdown."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT l.id, l.company_display, l.title_display, l.location_display,
               l.is_remote, l.score, l.status, l.url, l.posted_at
        FROM listings l
        WHERE l.canonical_id IS NULL AND l.status != 'new'
        ORDER BY
            CASE l.status
                WHEN 'interested' THEN 1 WHEN 'applied' THEN 2 WHEN 'responded' THEN 3
                WHEN 'interview' THEN 4 WHEN 'closed' THEN 5
            END, l.score DESC
        """
    ).fetchall()

    note_rows = conn.execute(
        "SELECT listing_id, content, created_at FROM notes ORDER BY created_at"
    ).fetchall()
    conn.close()

    notes_map: dict[int, list[str]] = {}
    for nr in note_rows:
        notes_map.setdefault(nr["listing_id"], []).append(
            f"  - [{nr['created_at'][:10]}] {nr['content']}"
        )

    lines = ["# Kestrel — Application Tracker\n"]
    current_status = ""
    for r in rows:
        if r["status"] != current_status:
            current_status = r["status"]
            lines.append(f"\n## {current_status.title()}\n")
        remote = " [Remote]" if r["is_remote"] else ""
        score_str = f" (score: {r['score']:.0f})" if r["score"] else ""
        url = r["url"] or ""
        lines.append(f"- **{r['company_display']}** — [{r['title_display']}]({url}){remote}{score_str}")
        lines.append(f"  {r['location_display'] or 'Location unknown'} · Posted {(r['posted_at'] or '')[:10]}")
        if r["id"] in notes_map:
            for note in notes_map[r["id"]]:
                lines.append(note)

    return PlainTextResponse(
        content="\n".join(lines),
        media_type="text/markdown",
        headers={"Content-Disposition": "attachment; filename=kestrel-export.md"},
    )


# ── Registry editor ──────────────────────────────────────────────────

@router.get("/registry")
def list_registry(active_only: bool = Query(False)):
    """List all registry entries."""
    conn = get_connection()
    if active_only:
        rows = conn.execute("SELECT * FROM registry WHERE active = 1 ORDER BY company").fetchall()
    else:
        rows = conn.execute("SELECT * FROM registry ORDER BY company").fetchall()
    conn.close()
    return {"companies": [dict(r) for r in rows]}


@router.post("/registry")
def add_registry(body: RegistryCreate):
    """Add or update a registry entry. Writes to both SQLite and registry.json."""
    valid_platforms = {p.value for p in ATSPlatform}
    if body.platform not in valid_platforms:
        raise HTTPException(422, f"Invalid platform '{body.platform}'. Valid: {', '.join(sorted(valid_platforms))}")
    entry = RegistryEntry(
        id=None,
        company=body.company,
        platform=ATSPlatform(body.platform),
        board_slug=body.board_slug,
        active=body.active,
    )
    row_id = upsert_registry(entry)
    # Persist to registry.json so CI sees the same companies
    from .seed import load_registry, save_registry
    reg = load_registry()
    # Update if exists, add if new
    found = False
    for r in reg:
        if r["platform"] == body.platform and r["board_slug"] == body.board_slug:
            r["company"] = body.company
            r["active"] = body.active
            found = True
            break
    if not found:
        reg.append({"company": body.company, "platform": body.platform,
                     "board_slug": body.board_slug, "active": body.active})
    save_registry(reg)
    return {"id": row_id, "company": body.company, "platform": body.platform, "board_slug": body.board_slug}


@router.patch("/registry/{entry_id}")
def update_registry(entry_id: int, active: bool = Query(...)):
    """Activate or deactivate a registry entry. Syncs to registry.json."""
    conn = get_connection()
    row = conn.execute("SELECT id, platform, board_slug FROM registry WHERE id = ?", (entry_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, f"Registry entry {entry_id} not found")
    conn.execute("UPDATE registry SET active = ? WHERE id = ?", (int(active), entry_id))
    conn.commit()
    conn.close()
    # Sync to registry.json
    from .seed import load_registry, save_registry
    reg = load_registry()
    for r in reg:
        if r["platform"] == row["platform"] and r["board_slug"] == row["board_slug"]:
            r["active"] = active
            break
    save_registry(reg)
    return {"id": entry_id, "active": active}


# ── Resume & portfolio storage ───────────────────────────────────────

from fastapi import UploadFile, File, Form
from .settings import settings


@router.post("/resumes")
async def upload_resume(
    file: UploadFile = File(...),
    label: str = Form(...),
    profile_name: str = Form("fullstack"),
):
    """Upload a resume file. Stored outside the repo in data_dir/resumes/."""
    resumes_dir = settings.data_dir / "resumes"
    resumes_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename
    now = datetime.utcnow()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r"[^\w.-]", "_", file.filename or "resume")
    stored_name = f"{timestamp}_{safe_name}"
    file_path = resumes_dir / stored_name

    content = await file.read()
    file_path.write_bytes(content)

    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO resumes (label, filename, file_path, profile_name, created_at) VALUES (?, ?, ?, ?, ?)",
        (label, file.filename, str(file_path), profile_name, now.isoformat()),
    )
    conn.commit()
    resume_id = cursor.lastrowid
    conn.close()

    return {"id": resume_id, "label": label, "filename": file.filename,
            "profile_name": profile_name, "created_at": now.isoformat()}


@router.get("/resumes")
def list_resumes(profile_name: str | None = None):
    """List all resumes, optionally filtered by profile."""
    conn = get_connection()
    if profile_name:
        rows = conn.execute(
            "SELECT id, label, filename, profile_name, created_at FROM resumes WHERE profile_name = ? ORDER BY created_at DESC",
            (profile_name,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, label, filename, profile_name, created_at FROM resumes ORDER BY created_at DESC"
        ).fetchall()
    conn.close()
    return {"resumes": [dict(r) for r in rows]}


@router.post("/portfolio-links")
def add_portfolio_link(label: str = Query(...), url: str = Query(...),
                       profile_name: str = Query("fullstack")):
    """Add a portfolio link attached to a profile."""
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    cursor = conn.execute(
        "INSERT INTO portfolio_links (label, url, profile_name, created_at) VALUES (?, ?, ?, ?)",
        (label, url, profile_name, now),
    )
    conn.commit()
    link_id = cursor.lastrowid
    conn.close()
    return {"id": link_id, "label": label, "url": url, "profile_name": profile_name}


@router.get("/portfolio-links")
def list_portfolio_links(profile_name: str | None = None):
    """List portfolio links, optionally filtered by profile."""
    conn = get_connection()
    if profile_name:
        rows = conn.execute(
            "SELECT * FROM portfolio_links WHERE profile_name = ? ORDER BY created_at DESC",
            (profile_name,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM portfolio_links ORDER BY created_at DESC").fetchall()
    conn.close()
    return {"links": [dict(r) for r in rows]}
