# CLAUDE.md — Kestrel

Read this file at the start of every session. It is the contract.

---

## What Kestrel is

A dual-track opportunity aggregator. It pulls listings from legal sources,
dedupes them, scores them against a profile, and tracks what has been acted on.

**Track 1 — Jobs.** Employment listings, Twin Cities metro and US-remote.
**Track 2 — Gigs.** Freelance and subcontract work: websites, advertising,
business systems, tech help.

Both tracks share one ingestion pipeline. Only the scoring profile and the
dashboard view differ.

It is a working tool and a portfolio piece at once. It must be explainable in
two minutes and demonstrable in one click.

---

## Deployment shape

**Domain:** `kestrel.adlaunch.studio`

Two surfaces, one codebase:

| Surface | Path | Access | Contents |
|---|---|---|---|
| Showroom | `/` | Public | Ranked listings, filters, score breakdowns |
| Desk | `/desk` | Cloudflare Access | Application history, notes, registry editor |

**All showroom data is public information.** Job postings are public by
definition. Nothing private is ever rendered on the public surface — not
application status, not notes, not the profile.

**Auth is never implemented in application code.** Cloudflare Access sits in
front of `/desk` and handles identity at the edge. Free tier, up to 50 users.
The app never sees a password, never stores a session, never implements a reset
flow. If a task seems to require writing authentication code, stop and ask.

**Build order:** local first, deployed continuously.
- Phase 0 deploys an empty shell to the real domain. This proves DNS, HTTPS,
  and the build pipeline before there is anything to break.
- Development happens locally against SQLite.
- The showroom is a static export refreshed by scheduled automation.
- The desk runs locally, and later behind Access.

---

## Non-negotiable constraints

### Money
**Zero recurring cost. No paid APIs, ever.** No trials, no "cheap at this
volume." If a source requires payment, it is out. Permanent constraint, not a
budget question. See COSTS.md.

### Legality and access
- **No scraping. No automating logged-in accounts. No evading access controls.**
  Documented public APIs, published feeds, and data the user legitimately
  receives (their own inbox) only.
- **Not LinkedIn, Indeed, Glassdoor, Facebook, or Wellfound directly.** Those
  are reached, where reachable at all, through job-alert emails the user
  configured and received.
- **No Minnesota Secretary of State filings data.** The free tier requires
  certifying non-commercial use, and Kestrel is hosted on a company domain.
  That belongs in a separate tool with a paid license, not here.
- Clean provenance is a feature of this project, not a limitation. If a source
  can't be explained comfortably out loud in an interview, it doesn't belong.

### Scope
- **Source count is not the constraint. Adapter patterns are.** Adding Lever
  after Greenhouse is thirty lines. Adding a whole new *kind* of source is a
  real decision.
- If a feature is not in SPEC.md, it does not get built. Propose it in the
  session review; do not add it.
- **The job track ships fully working before the gig track starts.**

### Stack — decided, do not relitigate
- Backend: **Python 3.11+, FastAPI**
- Storage: **SQLite** behind a repository layer
- Frontend: **React + Vite + TypeScript**
- Scoring: **pure Python. No ML, no LLM calls.** An LLM in the scoring path
  costs money per run, breaking the zero-cost rule, and makes the ranking
  unexplainable, destroying what makes this impressive.
- Scheduling: standalone entrypoint, runnable by GitHub Actions cron
- Hosting: Cloudflare Pages (static showroom), GitHub Actions (pipeline)
- Testing: pytest. Scoring, dedupe, and every parser get real tests.

### Portability rules
- All config from environment variables. No hardcoded paths, ports, URLs, keys.
  `.env.example` lists every variable; `.env` is gitignored.
- **The repo is public. Every credential lives in GitHub Actions Secrets.**
  Add a pre-commit hook that blocks anything resembling a key. Structural over
  policy — do not rely on remembering.
- All database access through the repository layer.
- No filesystem assumptions outside one configured data directory.
- Scheduler and web server independently runnable.
- Frontend talks to backend over HTTP only, or reads a static export.

---

## Working rules

1. **Claude Code does everything it can itself.** Hand tasks over only when they
   need the human's hands, eyes, a credential, or a reboot.
2. **A fix is not verified until it is tested the way it is actually used.**
   Actually run, end to end, output actually read.
3. **Fail loudly.** An API returning zero results and an API returning an error
   are different states and must read differently, in plain language.
4. **Structural over policy.** Make the wrong thing impossible in code.
5. **Every plan and phase gets a `.md` file in `docs/`.**
6. **Commit after every session**, with a message saying what changed and why.
7. **End every session with a review:** what is fragile, what you would do
   differently, what you had to assume.

---

## Sources

### Tier 1 — ATS boards (primary)
Public JSON, no auth, no key, no quota. Direct from employers, full
descriptions, no agency noise.

```
Greenhouse  https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true
Lever       https://api.lever.co/v0/postings/{slug}?mode=json
Ashby       https://api.ashbyhq.com/posting-api/job-board/{slug}
Recruitee   https://{slug}.recruitee.com/api/offers
Workable    PUBLIC API CLOSED as of Aug 2026 — returns 0 for all companies
```

**Query-by-company, not query-by-location.** No endpoint enumerates which
companies use an ATS. Location filtering happens after fetch. The company
registry is core infrastructure.

### Tier 2 — Aggregator APIs
- **Adzuna** — free tier ~1,000 calls/month (~33/day). Truncated descriptions,
  often model-predicted salaries. **Budget these calls explicitly.** Supporting
  source, never the backbone.
- **USAJobs** — free, structured, no real quota pressure. Federal hiring uses
  explicit qualification standards where experience substitutes for a degree.

### Tier 3 — Remote feeds
RemoteOK (JSON + RSS), Remotive (API + RSS), We Work Remotely (RSS).
**We Work Remotely requires visible attribution with a link back.**
One parser, three configs.

### Tier 4 — Gmail alert channel
The user configures job alerts on LinkedIn, Indeed, ZipRecruiter, Glassdoor.
Kestrel reads the user's own mailbox and parses what arrives.

- Read-only Gmail scope. Never send, delete, or modify.
- Only messages from configured alert senders are read or stored.
- One parser per sender, with per-sender failure isolation.
- **Alert URLs are tracking-wrapped. Unwrap before dedupe.**
- Expect title, company, location, link. Not full descriptions.

### Tier 5 — Gig sources
- **Google Alerts → RSS** — the catch-all, and the highest-yield gig source.
  Alerts set to "as-it-happens" can deliver to RSS. Any search phrase becomes a
  feed: `"need a website" Minneapolis`, `"looking for a web designer" Twin
  Cities`. Free, unlimited, no rate limit. **Expect heavy noise — the gig
  scorer earns its keep here.**
- **Reddit `.rss`** — `reddit.com/r/forhire/new.rss`. Do NOT use the OAuth API
  or `.json` endpoints: unauthenticated `.json` returns 403 as of May 2026 and
  OAuth approval is slow and unreliable. RSS is throttled to roughly 1 request
  per minute per feed, which is fine at hourly polling. **Reddit has signalled
  RSS may close next — treat this adapter as expendable and never load-bearing.**
- **Craigslist via Open RSS** — `openrss.org/` prefixed to a search URL.
  Computer gigs, creative gigs, small business ads.
- **Hacker News "Freelancer? Seeking Freelancer?"** — monthly thread via the
  Algolia API. Reuses the HN parser.
- **SAM.gov** — free API key, federal contract opportunities. Optional.

### Also in
**HN "Who is Hiring"** — monthly thread, Algolia, free-text parsing. Lowest
priority and the first thing to cut.

---

## Data model rules

- **`listing_type` (`job` | `gig`) exists from Phase 2**, before the gig track
  is built. Adding it later is a migration; adding it now is a column.
- **Raw and normalized listings stored separately.** Keep every raw response
  verbatim. When a parser is wrong — and it will be — re-run against stored data
  instead of re-fetching. Critical when one source allows 33 calls a day.
- **Historical snapshots are never pruned.** They become the hiring-velocity
  dataset later. Storage is free; re-fetching history is impossible.
- **Dedupe is a confidence-scored match.** Normalized company + title +
  location proximity, above a tunable threshold. Log near-misses for tuning.
- **Never delete a listing.** Mark it stale or closed. Application history must
  survive the posting vanishing from its source.
- **Scores are derived, never baked in.** Editing YAML and re-running rescore
  must reorder everything with zero network calls.

---

## Search parameters

- Home: Farmington, MN (~44.640, -93.144)
- Onsite radius: 80 km — covers the Twin Cities metro
- Remote: accepted anywhere in the US
- Qualifies if within radius **or** US-remote
- **Remote detection is a known-hard problem.**
  - **Solved for ATS boards:** the heuristic works when the location field
    explicitly says "Remote" or "Distributed" (validated at 15/15 on ATS data).
  - **Solved for remote feeds:** RemoteOK, Remotive, WWR are remote by
    definition — explicit source-based rule in `REMOTE_BY_SOURCE`, no heuristic.
  - **NOT solved for Gmail alerts (Phase 10):** LinkedIn/Indeed alert emails
    show city locations ("Minneapolis, MN") on fully-remote roles. The heuristic
    produces ~0% accuracy on these because there's no "Remote" keyword. This is
    an open problem, not a handled one.
  - **NOT solved for Adzuna:** location field is city-based, same gap as Gmail.

---

## Scoring

Multiple named profiles, one engine. Profiles live in `config/profiles/` as YAML.
Active profile set in `profiles.yaml`. Each profile has its own skills, experience
level, seniority target, and weights. The skill multiplier is never loosened —
separate profiles with separate skills are the answer for non-software roles.

### Job track

| Dimension | Weight |
|---|---|
| Skill match | 35 |
| Degree posture | 20 |
| Freshness | 15 |
| Location fit | 15 |
| Seniority fit | 10 |
| Source quality | 5 |

Source quality rewards direct-employer postings over agency reposts.

### Gig track

| Dimension | Weight |
|---|---|
| Deliverability | 35 |
| Budget signal | 25 |
| Freshness | 20 |
| Locality | 10 |
| Competition | 10 |

**Every score carries its per-dimension breakdown**, returned by the API and
shown in the UI. A ranking that can't be explained is not a portfolio feature.

Hard filters are few and separate from scoring: clearance required,
commission-only. Agency listings are flagged and scored down, never excluded.

---

## The Sniffer

Takes a careers page URL, identifies the ATS, extracts the board slug.

**On failure — iframe embeds, vanity domains, unknown platforms — fall back to
asking the user for the slug and record it, logging the failure reason.** The
registry keeps growing even when detection fails.

---

## What not to do

- Do not write authentication code. Cloudflare Access handles it.
- Do not render private data on the public surface.
- Do not add an LLM call anywhere in the pipeline.
- Do not build a résumé parser, cover letter generator, or auto-applier.
- Do not automate a logged-in session on any platform, for any reason.
- Do not add a paid source, even a cheap one, even on a trial.
- Do not make Reddit load-bearing.
- Do not start the gig track before the job track is working.
- Do not commit a credential. Ever, even briefly.
- Do not refactor toward microservices, Docker Compose, or Kubernetes.

If any of these seem genuinely necessary, say so in the session review and let
the human decide. Do not just build it.
