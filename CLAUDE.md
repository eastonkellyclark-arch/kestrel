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
| Showroom | `/` | Public | Ranked listings, filters, score breakdowns, interactive profile switcher |
| Desk | `/desk` | Local only | Apply queue, tracker, registry, sniffer, resume management |

**All showroom data is public information.** Job postings are public by
definition. Nothing private is ever rendered on the public surface — not
application status, not notes, not the profile.

**The desk runs locally** (`uvicorn`). There is no hosted backend — the
showroom is a static export on Cloudflare Pages. Cloudflare Access setup
deferred until a backend is deployed.

**Auth is never implemented in application code.** If a task seems to require
writing authentication code, stop and ask.

**Automated pipeline:** GitHub Actions runs every 6 hours — fetch, translate,
score, export, build, deploy to Cloudflare Pages. All credentials in Actions
Secrets. Failure notifications on credential errors and stale deploys.

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
  often model-predicted salaries. **Budget enforced in code** — daily call counter
  in SQLite, refuses at cap. Queries target Minnesota-area roles from employers
  not in the ATS registry (Workday/iCIMS companies). 4 calls/day.
- **USAJobs** — free, structured, no real quota pressure. Federal hiring uses
  explicit qualification standards where experience substitutes for a degree.
- **Freelancer.com** — public JSON API, no auth. Real web development gigs with
  budgets and bid counts. Primary gig source. Competition scorer uses real bid
  counts instead of freshness proxy.

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
- **Freelancer.com** — the primary gig source. Public JSON API, real budgets,
  real bid counts. All listings are demand by definition (clients posting work).
  Search queries configurable in `config/gig_feeds.yaml`.
- **Google Alerts → RSS** — feed URLs in `config/gig_feeds.yaml`. Add/remove
  without code changes. Awaiting user's feed URLs.
- **Reddit `.rss`** — r/forhire, r/smallbusiness, local subreddits. Do NOT use
  the OAuth API or `.json` endpoints. 5-second delay between feeds for rate
  limiting. **Treat as expendable and never load-bearing.**
  Demand/supply classifier filters [FOR HIRE] posts (competitors) from
  [HIRING] posts (real gigs).
- **Craigslist** — DISABLED. Native RSS returns 403, Open RSS proxy returns
  503. Craigslist has blocked programmatic RSS access as of Aug 2026.
- **HN Freelancer** — DISABLED. 15-33 comments/month, mostly SEEKING WORK.
  Zero web dev demand. Not worth the complexity.
- **SAM.gov** — free API key, federal contract opportunities. Optional.

### Upwork
**Not usable.** All endpoints return ConnectError. Historical RSS feeds dead.
API requires OAuth + approved app. Cannot be used without account automation.

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

### Composite model

Score = hygiene_score × skill_factor. Skill match is multiplicative, not
additive — zero skill match collapses the score regardless of other dimensions.
This prevents non-tech roles from outranking engineering roles.

Curve: `factor = floor + (1 - floor) * (skill_score / 100) ^ exponent`
Tunable via weights YAML: `skill_floor` and `skill_exponent`.

### Job track (fullstack profile)

| Dimension | Weight | Notes |
|---|---|---|
| Degree posture | 15 | No degree > equivalent ok > hard requirement |
| Freshness | 15 | |
| Location fit | 15 | TC metro > US Remote > US not metro > non-US |
| Experience fit | 12 | Extracted from description, scored against 1yr experience |
| Seniority fit | 8 | Mid-senior accepted, staff/principal/director penalized |
| Source quality | 5 | Direct employer > curated feed > aggregator |

Experience extraction: parses "5+ years", "minimum 3 years", spelled-out
"five years". NULL (not mentioned) scores 50 (neutral, not favorable).

### Gig track

| Dimension | Weight |
|---|---|
| Budget signal | 25 |
| Freshness | 20 |
| Locality | 10 |
| Competition | 10 |
| Source quality | 5 |

Competition uses real bid counts from Freelancer.com when available,
freshness as proxy for other sources.

Demand/supply classifier at translate time filters competitor posts
([FOR HIRE], "I am a developer") from real gigs ([HIRING], "need a website").
Supply posts score 0 on skill match — visible but buried.

**Every score carries its per-dimension breakdown**, returned by the API and
shown in the UI. The showroom's "Why this score?" section explains each
dimension in plain English. A ranking that can't be explained is not a
portfolio feature.

Hard filters are few and separate from scoring: clearance required,
commission-only. Agency listings are flagged and scored down, never excluded.

### Quality gates

Applied at translate time, not ingestion. Raw vault keeps everything.
Config in `config/quality_gate.yaml`:
- RemoteOK: min 3 words in title, spam phrase filter
- HN: min 10 words in comment content
- Filtered listings get `description_quality="filtered"`, still in DB.

---

## The Sniffer

Takes a careers page URL, identifies the ATS, extracts the board slug.
Three-pass detection: URL patterns → HTML body scan → API probe fallback
(derives slug guesses from domain name and tries each ATS API directly).

API probe catches JS-rendered embeds: Cloudflare and Figma both detected
via `cloudflare.com/careers/` → probe finds `greenhouse/cloudflare`.

**On failure — Workday, iCIMS, unknown platforms — fall back to
asking the user for the slug and record it, logging the failure reason.**

Company registry lives in `config/registry.json` — committed, read by both
local dev and CI. Desk UI writes to it so additions persist across environments.

---

## What not to do

- Do not write authentication code. Cloudflare Access handles it.
- Do not render private data on the public surface.
- Do not add an LLM call anywhere in the pipeline.
- Do not automate form filling or submission on external sites. The apply
  queue stages information — it does not inject, submit, or automate.
- Do not automate a logged-in session on any platform, for any reason.
- Do not add a paid source, even a cheap one, even on a trial.
- Do not make Reddit load-bearing.
- Do not commit a credential. Ever, even briefly.
- Do not refactor toward microservices, Docker Compose, or Kubernetes.
- Do not use silent fallbacks. If config is missing or malformed, fail
  loudly with a clear message. Structural over policy.
- Do not store data in fields meant for something else (e.g., bid count
  in the department field). Add proper columns.
- Do not loosen the skill multiplier to make non-software jobs rank.
  Separate profiles with separate skills are the answer.

If any of these seem genuinely necessary, say so in the session review and let
the human decide. Do not just build it.
