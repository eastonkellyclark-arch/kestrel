# SPEC.md — Kestrel, Phased Build

Each phase has a **Done when** test. Do not start a phase until the previous
one's test passes *when actually run*.

**Phases 0–6 produce a usable, deployed app.** Everything after adds coverage to
something that already works.

---

## Phase 0 — Skeleton and live domain

Structure, config, health check, and a real deployment. No listing logic.

- `backend/`, `frontend/`, `docs/`, `data/`
- Python dependency setup; FastAPI app with `GET /health`
- Settings module reading all config from environment
- `.env.example` listing every variable; `.env` gitignored
- **Pre-commit hook blocking anything that looks like a credential**
- SQLite initialized in the configured data directory
- `git init`, public repo, first commit
- **Deploy a placeholder page to `kestrel.adlaunch.studio` via Cloudflare Pages**

That last item is not decoration. Proving DNS, HTTPS, and the build pipeline now
— when nothing can break — is what keeps deployment from becoming a wall at the
end of the project.

**Done when:** server starts and `/health` returns 200 locally; the SQLite file
exists; `git status` is clean with `.env` untracked; the pre-commit hook rejects
a test commit containing a fake API key; and `https://kestrel.adlaunch.studio`
loads the placeholder over HTTPS from a phone on cellular data.

---

## Phase 1 — ATS core

Greenhouse and Lever only.

- Registry table: company, ATS platform, board slug, active flag, added date
- Seeded by hand with 20–30 companies — Twin Cities employers plus
  remote-friendly companies worth watching
- Greenhouse adapter (`?content=true`), Lever adapter
- Raw responses stored verbatim with source, slug, fetch timestamp
- **Per-company failure isolation** — one dead slug must not abort the run
- Distinct errors: slug not found, board disabled, network failure, empty board

**Done when:** one command fetches from every registry company and prints
per-company counts. Running twice creates no duplicate raw rows. A deliberately
bad slug produces a clear message naming that company while the run continues.

---

## Phase 2 — Translator and Merger

- Source-agnostic schema **including `listing_type` (`job` | `gig`) now**
- Company and title normalization for matching; display versions preserved
- **Remote detection heuristic** over title and description text
- Confidence-scored dedupe, configurable threshold, near-misses logged
- Duplicates linked to a canonical listing, never deleted

**Done when:** `listings` is populated from raw storage and you have read 20
random rows and 20 near-miss entries yourself. Remote detection checked against
15 listings you personally read, with false-positive and false-negative counts
and examples written to `docs/phase2-review.md`.

---

## Phase 3 — The Judge

- `profile.yaml` and `weights.yaml`
- Six job-track scorers per CLAUDE.md, including source quality
- Degree-posture parser: hard requirement, "or equivalent experience",
  explicit no-degree
- Composite score with per-dimension breakdown stored alongside
- `rescore` command — recomputes from YAML, zero network calls
- Unit tests per scorer, including missing description, salary, and date

**Done when:** every listing has a score and breakdown. Top 20 and bottom 20
printed with breakdowns and you agree the ranking is right. Changing a weight
and re-running rescore visibly reorders with no network access.

---

## Phase 4 — Front Desk

- `GET /listings` — ranked, filterable by type, remote, min score, source,
  posted-since, degree-not-required, status
- `GET /listings/{id}` — detail with breakdown and duplicate sources
- `PATCH /listings/{id}` — status update
- `POST /rescore`, `GET /stats`
- Pagination, consistent errors, OpenAPI docs at `/docs`
- **Static export mode** — a command that writes the public dataset (listings,
  scores, breakdowns; no private fields) to JSON for the showroom build

The export path is what makes hosting free. Build it now rather than
retrofitting it.

**Done when:** every endpoint exercised against the real database with combined
filters. The static export produces valid JSON containing no private fields —
verify by grepping the output for notes and status values.

---

## Phase 5 — Showroom

Public surface. React + Vite + TypeScript, built against the static export.

- Ranked list: score badge, company, title, location, remote and no-degree flags
- Filter panel
- Detail view with full description and **visualized score breakdown**
- Distinguishable loading, empty, and error states
- **Visible We Work Remotely attribution** once that source lands
- Deployed to `kestrel.adlaunch.studio`

First thing anyone sees. Make deliberate typography and color choices rather
than shipping framework defaults.

**Done when:** the live URL shows real ranked data, loads fast on a phone, and
you found a job worth applying to using only the UI. Every error state triggered
on purpose and looking intentional.

---

## Phase 6 — Desk

Private surface. Runs locally now, behind Cloudflare Access once deployed.

- Status lifecycle: interested → applied → responded → interview → closed
- Timestamped history, per-listing notes
- Pipeline view with stage counts
- Export to CSV and Markdown
- Registry editor
- **No authentication code.** Cloudflare Access handles identity at the edge.

**Deployment note:** The showroom is a static export on Cloudflare Pages — no
backend runs there, so `/desk` on the public domain doesn't exist. The desk
runs locally (`uvicorn`) until there's a hosted backend. Cloudflare Access
setup moves to whenever the backend is deployed (not Phase 6).

**Done when:** five listings moved through three statuses each, then a full
re-ingest and rescore, and all history intact. Export opens correctly in a
spreadsheet. Desk UI runs locally and is genuinely usable for daily tracking.

**The app is genuinely usable from here. Start using it daily.**

---

## Phase 7 — The Sniffer

- Takes a careers URL, identifies the ATS, extracts the slug
- Covers Greenhouse, Lever, Ashby, Workable, Recruitee
- **Manual fallback** on failure, with the reason logged
- Adapters added for Ashby, Workable, Recruitee
- Desk UI: paste a URL, see what was detected, confirm into the registry

**Done when:** ten real careers URLs tested, at least three expected to fail.
Results correct, failures fall back cleanly, registry grew.

---

## Phase 8 — Aggregators

- **Adzuna** with an explicit call budget — track usage and refuse to exceed
  the cap rather than silently burning quota
- **USAJobs**
- Pagination, backoff on 429 and 5xx
- Both through the existing Translator and Merger unchanged

**Done when:** both ingest on one command, the budget counter blocks correctly
at the cap, and dedupe collapses cross-source duplicates you verified by hand.

---

## Phase 9 — Remote feeds

RemoteOK, Remotive, We Work Remotely. One parser, three configs.

WWR attribution visible in the UI.

**Done when:** all three ingest, attribution is live, and remote detection is
re-validated against these feeds — everything on them is remote by definition,
making them ground truth. Report the accuracy numbers; if they're worse than
Phase 2 suggested, say so plainly.

---

## Phase 10 — Gmail alert channel

- Read-only Gmail OAuth, credentials from env
- Parsers for LinkedIn, Indeed, ZipRecruiter, Glassdoor
- **Unwrap tracking URLs before dedupe**
- Per-sender failure isolation
- Only configured alert senders are read or stored

**Done when:** real alert emails parsed correctly, and dedupe collapses an alert
listing against the same role already pulled from an ATS board. A malformed
email produces a clear per-sender error without stopping the others.

---

## Phase 11 — Gig track

Only now. The job track is finished and in daily use.

- **Google Alerts RSS** — the primary gig source. One parser, many feeds,
  feed URLs in config so alerts can be added without code changes.
- **Reddit `.rss`** — r/forhire, r/smallbusiness, local subreddits. Hourly
  polling, well within the ~1/min limit. Isolated so its removal breaks nothing.
- **Craigslist via Open RSS**
- **HN "Freelancer? Seeking Freelancer?"** via Algolia
- `gig_profile.yaml` and `gig_weights.yaml`
- Showroom and desk gain a Jobs/Gigs toggle
- Optional: SAM.gov

Everything flows through the existing pipeline. **If adding this track requires
changing the pipeline, the abstraction is wrong — fix it and report what changed.**

**Done when:** both tracks ingest on one command, the toggle works, the top 10
gigs are work you could genuinely deliver, and no job-track behavior regressed.

---

## Phase 12 — Automation and cutover

- GitHub Actions workflow on a cron: fetch → normalize → dedupe → score →
  static export → commit → trigger Pages build
- All credentials in Actions Secrets
- Failure notification — a silent broken pipeline is worse than no pipeline
- Showroom refreshes without manual intervention

**Done when:** you change nothing for a week and the live site still shows
current listings. Break a credential on purpose and confirm you find out.

---

## Phase 13 — HN Who is Hiring (optional)

Free-text comment parsing via Algolia. Accept partial extraction.

**This is the cut. If time or energy is short, ship without it.**

---

## Then — use it

Two weeks minimum of real job and gig hunting before building anything else.
Keep a running list of what breaks and what annoys you.

---

## Phase 14 — Outcome tracking (post-launch)

Only after there is real application data to analyze.

- Response rate by score band, by source, by posting freshness at time of apply
- Does the score predict callbacks?
- Recalibrate weights against what the data says
- Write the findings up in `docs/scoring-validation.md`

This is the highest-value addition to the project. Everyone who builds an
aggregator builds a ranking. Almost nobody measures whether theirs works.

**Done when:** you can state, with numbers, which scoring dimension best
predicted a response — and you've adjusted the weights accordingly.
