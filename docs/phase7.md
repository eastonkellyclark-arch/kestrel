# Phase 7 — The Sniffer + Desk UI + Adapters

## What was built

### Sniffer
- Takes a careers page URL, identifies the ATS, extracts the board slug
- Covers: Greenhouse, Lever, Ashby, Workable, Recruitee
- Two-pass detection: URL patterns first, then HTML body scan
- Follows redirects (vanity domains → ATS URLs)
- On failure: returns what it found and why, user provides slug manually

### New adapters
- Ashby: `https://api.ashbyhq.com/posting-api/job-board/{slug}`
- Workable: `https://apply.workable.com/api/v3/accounts/{slug}/jobs`
- Recruitee: `https://{slug}.recruitee.com/api/offers`

### Desk UI
- Single-page HTML served at `/desk` by FastAPI
- Pipeline stage counts (top of page)
- Tracker tab: table of non-new listings, status dropdown, note button
- Registry tab: add/activate/deactivate companies
- Sniffer tab: paste URL → detect → confirm into registry
- Matches showroom dark theme

### Re-translate mode
- `translate_all()` now updates existing listings from raw data instead of
  skipping them. Status, history, and notes survive (separate tables).
- Verified: 0 new, 937 updated, all 5 statuses/15 history/5 notes intact.

### SPEC.md update
- Clarified: desk is local-only until backend is deployed. The showroom is
  a static site on Cloudflare Pages — no backend runs there.
- Cloudflare Access setup moves to whenever the backend is hosted.

## Sniffer test results (10 real URLs)

| URL | Result | Notes |
|---|---|---|
| boards.greenhouse.io/gitlab | greenhouse/gitlab | Direct URL match |
| jobs.lever.co/netflix | lever/netflix | Direct URL match |
| cloudflare.com/careers/jobs/ | FAILED | JS-rendered Greenhouse embed |
| jobs.ashbyhq.com/ramp | ashby/ramp | Direct URL match |
| apply.workable.com/deel/ | workable/deel | Direct URL match |
| figma.com/careers/ | FAILED | JS-rendered embed |
| target.wd5.myworkdayjobs.com | FAILED | Workday — no public API |
| 3m.com/careers/ | FAILED | 404 |
| careers.unitedhealthgroup.com | FAILED | Custom/iCIMS |
| vacatures.adcombi.com | FAILED | SSL error |

4 detected, 3 correct failures (Workday/iCIMS/custom), 3 JS embed limitations.
Manual fallback works for all failures via the desk UI.
