# Phase 1 — ATS Core

## What was built
- Registry table: company, platform, board_slug, active flag, added_date
- Raw listings table (the Vault): source, board_slug, source_id, raw_json, fetched_at
- Greenhouse adapter (public JSON, `?content=true`)
- Lever adapter (public JSON, `?mode=json`)
- Standalone fetch command (`python -m backend.fetch`)
- Per-company failure isolation — one dead slug never aborts the run

## Seed list (15 active companies)
- **Twin Cities (7):** Jamf, Sezzle, Branch, Livefront, Dispatch, Field Nation, Total Expert
- **Mid-size remote (6):** Webflow, Cockroach Labs, Gusto, Airtable, Neon, Perforce
- **Mega-cap benchmarks (2):** Cloudflare, GitLab

## Fetch results (2026-08-17)
- 937 raw listings stored
- 15/15 active companies succeeded
- Dedup verified: second fetch added 0 new rows

## Distribution flags
- Cloudflare: 298 jobs (31.8%) — over 20% threshold
- GitLab: 197 jobs (21.0%) — over 20% threshold
- Sezzle: 177 jobs (18.9%) — just under threshold
- Consider per-company intake cap before Phase 3 scoring

## TC slug discovery
- Original 13 guesses: 3 worked (Jamf, Branch, Sezzle)
- Slug hunting found 4 more: Field Nation (Lever), Total Expert (Lever), Livefront, Dispatch
- 6 TC companies not on Greenhouse/Lever: SPS Commerce, Datasite, Gravie, Calabrio, Sleep Number, When I Work
- Final TC hit rate: 7 working local sources

## Failure states
All four read distinctly:
- `SLUG NOT FOUND`: "Board 'xyz' not found (404)"
- `BOARD DISABLED`: "Board 'xyz' returned 403 — likely disabled"
- `NETWORK ERROR`: "Request timed out" / "Connection failed: ..."
- `EMPTY (no open roles)`: reported as empty with 0 count, no error
