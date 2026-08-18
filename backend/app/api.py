"""Phase 4 — The Front Desk API routes.

All endpoints for listings, scoring, stats, and static export.
"""

import json
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .database import get_connection
from .scoring.judge import score_all

logger = logging.getLogger("kestrel.api")

router = APIRouter()


# ── Profiles (public, for showroom demo) ─────────────────────────────

@router.get("/profiles")
def list_profiles():
    """List available scoring profiles. Public — used by showroom demo."""
    from .scoring.judge import _load_profile_yaml
    index = _load_profile_yaml("profiles.yaml")
    active = index.get("active", "")
    profiles = []
    for name, info in index.get("profiles", {}).items():
        profiles.append({
            "name": name,
            "label": info.get("label", name),
            "active": name == active,
        })
    return {"active": active, "profiles": profiles}


# ── Request/Response models ──────────────────────────────────────────

class StatusUpdate(BaseModel):
    status: str


class RescoreResponse(BaseModel):
    scored: int
    dealbreakers: int


# ── GET /listings ────────────────────────────────────────────────────

@router.get("/listings")
def list_listings(
    listing_type: str | None = Query(None, description="Filter: job or gig"),
    remote: bool | None = Query(None, description="Filter: remote only"),
    min_score: float | None = Query(None, description="Filter: minimum score"),
    source: str | None = Query(None, description="Filter: source platform"),
    posted_since: str | None = Query(None, description="Filter: ISO date, listings posted after this"),
    degree_not_required: bool | None = Query(None, description="Filter: degree not hard-required"),
    status: str | None = Query(None, description="Filter: listing status"),
    company: str | None = Query(None, description="Filter: company name (partial match)"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=200, description="Results per page"),
):
    """Ranked listings with composable filters and pagination."""
    conditions = ["canonical_id IS NULL", "score IS NOT NULL"]
    params: list = []

    if listing_type:
        conditions.append("listing_type = ?")
        params.append(listing_type)
    if remote is True:
        conditions.append("is_remote = 1")
    elif remote is False:
        conditions.append("is_remote = 0")
    if min_score is not None:
        conditions.append("score >= ?")
        params.append(min_score)
    if source:
        conditions.append("source = ?")
        params.append(source)
    if posted_since:
        conditions.append("posted_at >= ?")
        params.append(posted_since)
    if degree_not_required is True:
        conditions.append("degree_hard_required = 0")
    if status:
        conditions.append("status = ?")
        params.append(status)
    if company:
        conditions.append("company_display LIKE ?")
        params.append(f"%{company}%")

    where = " AND ".join(conditions)
    offset = (page - 1) * per_page

    conn = get_connection()
    total = conn.execute(f"SELECT COUNT(*) FROM listings WHERE {where}", params).fetchone()[0]
    rows = conn.execute(
        f"""
        SELECT id, listing_type, source, company_display, title_display,
               location_display, is_remote, score, posted_at, department,
               url, status, description_quality
        FROM listings
        WHERE {where}
        ORDER BY score DESC
        LIMIT ? OFFSET ?
        """,
        params + [per_page, offset],
    ).fetchall()
    conn.close()

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
        "listings": [dict(r) for r in rows],
    }


# ── GET /listings/{id} ──────────────────────────────────────────────

@router.get("/listings/{listing_id}")
def get_listing(listing_id: int):
    """Single listing detail with full score breakdown and duplicate sources."""
    conn = get_connection()
    row = conn.execute(
        """
        SELECT id, listing_type, source, source_id, board_slug,
               company_display, title_display, location_display,
               description, url, posted_at, department,
               is_remote, remote_confidence, description_quality,
               score, score_breakdown,
               canonical_id, dedupe_score,
               status, created_at
        FROM listings WHERE id = ?
        """,
        (listing_id,),
    ).fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Listing {listing_id} not found")

    result = dict(row)
    if result["score_breakdown"]:
        result["score_breakdown"] = json.loads(result["score_breakdown"])

    # Find duplicate sources
    dupes = conn.execute(
        "SELECT id, source, source_id, url FROM listings WHERE canonical_id = ?",
        (listing_id,),
    ).fetchall()
    result["duplicate_sources"] = [dict(d) for d in dupes]

    conn.close()
    return result


# ── PATCH /listings/{id} ─────────────────────────────────────────────

@router.patch("/listings/{listing_id}")
def update_listing_status(listing_id: int, body: StatusUpdate):
    """Update a listing's status."""
    valid_statuses = {"new", "interested", "applied", "responded", "interview", "closed"}
    if body.status not in valid_statuses:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status '{body.status}'. Valid: {', '.join(sorted(valid_statuses))}",
        )

    conn = get_connection()
    row = conn.execute("SELECT id FROM listings WHERE id = ?", (listing_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Listing {listing_id} not found")

    conn.execute("UPDATE listings SET status = ? WHERE id = ?", (body.status, listing_id))
    conn.commit()
    conn.close()
    return {"id": listing_id, "status": body.status}


# ── POST /rescore ────────────────────────────────────────────────────

@router.post("/rescore", response_model=RescoreResponse)
def rescore():
    """Recompute all scores from YAML profiles. Zero network calls."""
    stats = score_all()
    return RescoreResponse(scored=stats["scored"], dealbreakers=stats["dealbreakers"])


# ── GET /stats ───────────────────────────────────────────────────────

@router.get("/stats")
def get_stats():
    """Summary statistics."""
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) FROM listings WHERE canonical_id IS NULL").fetchone()[0]
    scored = conn.execute("SELECT COUNT(*) FROM listings WHERE canonical_id IS NULL AND score IS NOT NULL").fetchone()[0]
    remote = conn.execute("SELECT COUNT(*) FROM listings WHERE canonical_id IS NULL AND is_remote = 1").fetchone()[0]
    by_source = conn.execute(
        "SELECT source, COUNT(*) as cnt FROM listings WHERE canonical_id IS NULL GROUP BY source ORDER BY cnt DESC"
    ).fetchall()
    by_status = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM listings WHERE canonical_id IS NULL GROUP BY status ORDER BY cnt DESC"
    ).fetchall()
    avg_score = conn.execute(
        "SELECT AVG(score) FROM listings WHERE canonical_id IS NULL AND score IS NOT NULL"
    ).fetchone()[0]
    top_score = conn.execute(
        "SELECT MAX(score) FROM listings WHERE canonical_id IS NULL AND score IS NOT NULL"
    ).fetchone()[0]
    conn.close()

    return {
        "total_listings": total,
        "scored": scored,
        "remote": remote,
        "avg_score": round(avg_score, 1) if avg_score else 0,
        "top_score": round(top_score, 1) if top_score else 0,
        "by_source": {r["source"]: r["cnt"] for r in by_source},
        "by_status": {r["status"]: r["cnt"] for r in by_status},
    }
