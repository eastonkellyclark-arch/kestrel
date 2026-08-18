# Phase 8 — Aggregators (Adzuna + USAJobs)

## What was built

### Adzuna adapter
- Endpoint: `GET https://api.adzuna.com/v1/api/jobs/us/search/{page}`
- Auth: app_id + app_key from env vars
- **Explicit daily call budget** tracked in SQLite `_meta` table:
  - Persists across restarts
  - Refuses to exceed cap with clear message: "Daily budget exhausted: 33/33"
  - Budget status endpoint: `GET /desk/budget/adzuna`
  - Default cap: 33 calls/day (configurable via `KESTREL_ADZUNA_DAILY_BUDGET`)
- Pagination with per-page budget check
- Backoff on 429

### USAJobs adapter
- Endpoint: `GET https://data.usajobs.gov/api/search`
- Auth: Authorization-Key header + User-Agent (registered email)
- Pagination with total-count-based page exhaustion
- Structured federal job data with qualification summaries

### Translator parsers
- Adzuna parser: handles truncated descriptions, company object, area-based locations
- USAJobs parser: handles nested MatchedObjectDescriptor, MajorDuties lists,
  QualificationSummary, PositionLocation arrays

### Source quality scoring
- Adzuna: 50 (aggregator, truncated descriptions)
- USAJobs: 90 (direct, structured)

## Budget enforcement verification

```
Budget before: used=0, limit=33, remaining=33
After 33 simulated calls: used=33, limit=33, remaining=0
Fetch at cap: "Daily budget exhausted: 33/33 calls used today"
```

Budget blocks correctly. The daily counter resets automatically (key includes date).

## To activate

1. **Adzuna**: Register at https://developer.adzuna.com/
   ```
   KESTREL_ADZUNA_APP_ID=your_app_id
   KESTREL_ADZUNA_APP_KEY=your_app_key
   ```

2. **USAJobs**: Register at https://developer.usajobs.gov/apirequest
   ```
   KESTREL_USAJOBS_API_KEY=your_key
   KESTREL_USAJOBS_EMAIL=your@email.com
   ```

Add these to `.env` (gitignored). Once set, run `python -m backend.fetch`
and the aggregator adapters will be included automatically.

## Cross-source dedupe
Adzuna and USAJobs are the first real test of cross-source dedupe — they will
surface listings already present from ATS boards. Verify dedupe after first
real fetch with keys configured.
