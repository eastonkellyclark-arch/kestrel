"""Seed the company registry with initial companies.

Run: python -m backend.app.seed
"""

from .database import init_db
from .models import ATSPlatform, RegistryEntry
from .repository import upsert_registry

# fmt: off
SEED_COMPANIES = [
    # ── Twin Cities / Minnesota (7 verified) ─────────────────────────────
    # The big TC employers (Target, UHG, Best Buy, 3M) use enterprise ATS
    # (Workday, Taleo) — they arrive via aggregators in Phase 8.
    RegistryEntry(None, "Jamf",              ATSPlatform.GREENHOUSE, "jamf"),
    RegistryEntry(None, "Sezzle",            ATSPlatform.GREENHOUSE, "sezzle"),
    RegistryEntry(None, "Branch",            ATSPlatform.GREENHOUSE, "branch"),
    RegistryEntry(None, "Livefront",         ATSPlatform.GREENHOUSE, "livefront"),
    RegistryEntry(None, "Dispatch",          ATSPlatform.GREENHOUSE, "dispatch"),
    RegistryEntry(None, "Field Nation",      ATSPlatform.LEVER,      "fieldnation"),
    RegistryEntry(None, "Total Expert",      ATSPlatform.LEVER,      "totalexpert"),

    # ── Remote-friendly mid-size — Greenhouse ────────────────────────────
    RegistryEntry(None, "Webflow",           ATSPlatform.GREENHOUSE, "webflow"),
    RegistryEntry(None, "Cockroach Labs",    ATSPlatform.GREENHOUSE, "cockroachlabs"),
    RegistryEntry(None, "Gusto",             ATSPlatform.GREENHOUSE, "gusto"),
    RegistryEntry(None, "Airtable",          ATSPlatform.GREENHOUSE, "airtable"),

    # ── Remote-friendly mid-size — Lever ─────────────────────────────────
    RegistryEntry(None, "Neon",              ATSPlatform.LEVER,      "neon"),
    RegistryEntry(None, "Perforce",          ATSPlatform.LEVER,      "perforce"),

    # ── Mega-cap benchmarks (volume anchors only) ────────────────────────
    RegistryEntry(None, "Cloudflare",        ATSPlatform.GREENHOUSE, "cloudflare"),
    RegistryEntry(None, "GitLab",            ATSPlatform.GREENHOUSE, "gitlab"),
]
# fmt: on


def seed() -> None:
    init_db()
    for entry in SEED_COMPANIES:
        upsert_registry(entry)
    print(f"Seeded {len(SEED_COMPANIES)} companies into registry.")


if __name__ == "__main__":
    seed()
