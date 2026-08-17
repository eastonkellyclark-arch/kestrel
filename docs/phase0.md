# Phase 0 — Skeleton and Live Domain

## Deliverables
- Directory structure: `backend/`, `frontend/`, `docs/`, `data/`
- FastAPI app with `GET /health`
- Centralised settings via `pydantic-settings`, all from env vars
- `.env.example` lists every variable; `.env` gitignored
- SQLite initialised at startup in the configured data directory
- Pre-commit hook blocks commits containing credential patterns
- Placeholder page deployed to `kestrel.adlaunch.studio` via Cloudflare Pages

## Done-when tests
- Server starts, `/health` returns 200
- SQLite file exists at configured path
- `git status` clean, `.env` untracked
- Pre-commit hook rejects a test commit with a fake API key
- `https://kestrel.adlaunch.studio` loads placeholder over HTTPS
