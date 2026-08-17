# Phase 5 — The Showroom

## What was built
- React + Vite + TypeScript showroom at `kestrel.adlaunch.studio`
- Ranked list with score badges (color-coded: green 50+, amber 30-49, red <30)
- Filter panel: search, remote-only, no-degree-required, min score slider
- Detail view with full description and visualized score breakdown (bar chart)
- Deliberate dark theme with Inter typography, not framework defaults
- Split static export: index.json (439KB, no descriptions) + per-listing JSON

## Pre-Phase 5 fixes
1. **Split export**: index.json for the list view, `listings/{id}.json` for detail.
   Initial page load is the index only; descriptions load on click.
2. **degree_hard_required column**: real column populated during scoring, replaces
   the LIKE-against-JSON filter. Fails loudly if the column is missing.

## States
- **Loading**: centered spinner + "Loading listings..."
- **Error**: red heading + error message + hint text
- **Empty results**: muted "No listings match" + "Try adjusting your filters"
- **Loaded**: ranked listing cards
- **Detail loading**: spinner while fetching per-listing JSON
- **Detail error**: "Detail not available"

All visually distinct — an empty result never looks like a failure.

## Deployment
Cloudflare Pages build settings need updating from Phase 0:
- **Build command**: `cd frontend && npm install && npm run build`
- **Build output directory**: `frontend/dist`
- **Before build**: copy export data into `frontend/public/data/`

The export data must be committed to the repo (or generated in CI) for the
Pages build to include it. Phase 12 automation will handle this.
