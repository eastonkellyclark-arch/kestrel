# BUILD_PROMPTS.md — Kestrel

One prompt per Claude Code session. Paste verbatim. Run the **Done when** test
from SPEC.md before moving on. `/clear` between sessions. Commit after each.

**Before Prompt 0:**
- Create the folder; put CLAUDE.md, SPEC.md, FLOW.md, COSTS.md, and this file in
  the root
- `git init`, push to a **public** GitHub repo
- Cloudflare account, `adlaunch.studio` DNS available for a subdomain

**Set up now, needed later — these have lead times:**
- **Turn on LinkedIn and Indeed job alerts today.** Phase 10 parses them, and
  you can't build a parser against an empty inbox. Weeks of accumulated
  messages in varying formats is exactly what you want.
- **Create your Google Alerts today** and set delivery to RSS. Same reason,
  and feeds need time to populate.
- Adzuna app ID and key (developer.adzuna.com, free, instant) before Phase 8
- USAJobs API key before Phase 8
- Google Cloud project with Gmail API enabled before Phase 10

---

## Prompt 0 — Skeleton and live domain

```
Read CLAUDE.md and SPEC.md in this folder before doing anything.

Build Phase 0: project skeleton plus a live deployment.

Structure, Python dependency setup, FastAPI app with GET /health, a settings
module loading all config from environment variables, .env.example, .gitignore,
SQLite initialization, and a pre-commit hook that blocks commits containing
anything resembling an API key or credential.

Then deploy a placeholder page to kestrel.adlaunch.studio via Cloudflare Pages.
I have the Cloudflare account and the domain; tell me exactly what to click and
what to paste, and do everything else yourself.

Deploying now — before there's anything to break — is what keeps deployment
from becoming a wall at the end. Treat it as a real deliverable, not a stub.

Verify /health locally yourself, and test the pre-commit hook by attempting a
commit with a fake key. Then tell me: what's fragile, what you'd do
differently, what you assumed.
```

---

## Prompt 1 — ATS core

```
Read CLAUDE.md and SPEC.md. Phase 0 is complete.

Build Phase 1: the ATS layer — Greenhouse and Lever only. Endpoints are in
CLAUDE.md, both public, no auth.

Build the company registry, seed it with 20-30 companies (Twin Cities employers
plus remote-friendly companies — pick sensible ones and show me the list), and
store raw responses verbatim.

Critical: per-company failure isolation. One dead slug must not abort the run.
Slug-not-found, board-disabled, network failure, and genuinely-empty-board are
four different outcomes and must read differently.

Run the real fetch and report per-company counts. Break one slug on purpose and
show me the output. Then tell me: what's fragile, what you'd do differently,
what you assumed.
```

---

## Prompt 2 — Translator and Merger

```
Read CLAUDE.md and SPEC.md. Phases 0-1 are complete.

Build Phase 2: normalization and deduplication.

Include listing_type (job|gig) in the schema now, even though the gig track is
Phase 11.

Normalize company names and titles for matching while preserving display
versions. Build the remote-detection heuristic — read CLAUDE.md on why this is
the hard part and don't assume your first approach works. Dedupe as a
confidence-scored match with a configurable threshold; log near-misses; link
duplicates to a canonical listing rather than deleting.

Before reporting done: read 20 random normalized rows and 20 near-miss entries
yourself. Check remote detection against 15 listings whose descriptions you
actually read. Write false positive and false negative counts, with examples of
what it got wrong, into docs/phase2-review.md.

Then tell me: what's fragile, what you'd do differently, what you assumed.
```

---

## Prompt 3 — The Judge

```
Read CLAUDE.md and SPEC.md. Phases 0-2 are complete.

Build Phase 3: the scoring engine. This is the centerpiece.

Create profile.yaml and weights.yaml. Seed profile.yaml with:

  primary skills: TypeScript, React, Next.js, Node.js, PostgreSQL
  secondary skills: Python, Redis, Electron, REST API design, cloud deployment
  bonus skills: C++, Supabase, Vite, job queues, marketing automation
  target seniority: mid-level
  dealbreakers: security clearance required, commission-only compensation

Six scorers per the CLAUDE.md table, including source quality — direct-employer
ATS postings should outrank agency reposts of the same role.

Store the per-dimension breakdown alongside every composite score. Include a
rescore command that recomputes from YAML with zero network calls. Unit tests
per scorer with edge cases: missing description, salary, or date.

Before reporting done: print top 20 and bottom 20 with breakdowns so I can
judge the ranking. Then change a weight and re-run rescore to prove it reorders.

Then tell me: what's fragile, what you'd do differently, what you assumed.
```

---

## Prompt 4 — Front Desk

```
Read CLAUDE.md and SPEC.md. Phases 0-3 are complete.

Build Phase 4: the HTTP API per SPEC.md Phase 4, plus static export mode.

Filters must compose correctly when combined. Pagination and consistent errors.

The static export writes the public dataset to JSON for the showroom build —
listings, scores, breakdowns, and nothing private. No notes, no status, no
profile data. This export is what makes hosting free, so build it properly now.

Exercise every endpoint against the real database including combined filters.
Then grep the export output for notes and status values to prove nothing
private leaked.

Then tell me: what's fragile, what you'd do differently, what you assumed.
```

---

## Prompt 5 — Showroom

```
Read CLAUDE.md and SPEC.md. Phases 0-4 are complete.

Build Phase 5: the public showroom. React + Vite + TypeScript, built against
the static export, deployed to kestrel.adlaunch.studio.

Ranked list, filter panel, detail view with the score breakdown visualized.

This is the first thing a hiring manager sees, so visual design matters more
than it would for an internal tool. Make deliberate typography and color
choices rather than shipping framework defaults.

Loading, empty, and error states must be visibly distinct. An empty result must
never look like a failure, or vice versa.

Before reporting done: deploy it, load the live URL on a phone, trigger every
error state on purpose, and find a job worth applying to using only the UI.

Then tell me: what's fragile, what you'd do differently, what you assumed.
```

---

## Prompt 6 — Desk

```
Read CLAUDE.md and SPEC.md. Phases 0-5 are complete.

Build Phase 6: the private desk at /desk — status lifecycle, timestamped
history, notes, pipeline view with stage counts, CSV and Markdown export, and a
registry editor.

Do NOT write authentication code. Cloudflare Access handles identity at the
edge. Tell me exactly how to configure Access on the /desk route and I'll do
that part.

The critical property: status and history survive re-ingestion, rescoring, and
the source listing going stale. Test it explicitly — move several listings
through statuses, run a full re-ingest and rescore, confirm nothing was lost.

Then tell me: what's fragile, what you'd do differently, what you assumed.
```

---

## Prompt 7 — The Sniffer

```
Read CLAUDE.md and SPEC.md. Phases 0-6 are complete and the app is in daily use.

Build Phase 7: the ATS detector, plus Ashby, Workable, and Recruitee adapters.

The Sniffer takes a careers page URL, identifies which ATS the company uses,
and extracts the board slug. On failure — iframe embeds, vanity domains,
unknown platforms — fall back to prompting me for the slug and record it, with
the failure reason logged so patterns are visible.

Add a desk flow: paste a URL, see what was detected, confirm into the registry.

Test against ten real careers URLs including at least three you expect to fail.
Show me what happened for each.

Then tell me: what's fragile, what you'd do differently, what you assumed.
```

---

## Prompt 8 — Aggregators

```
Read CLAUDE.md and SPEC.md. Phases 0-7 are complete.

Build Phase 8: Adzuna and USAJobs.

Adzuna's free tier is roughly 1,000 calls a month — about 33 a day. Build an
explicit call budget: track usage and refuse to exceed the cap rather than
silently burning quota. Read Adzuna's actual API docs rather than guessing at
parameter names.

Both flow through the existing Translator and Merger unchanged.

Run both, show the budget counter working, and verify it blocks at the cap.
Find genuine cross-source duplicates by hand and confirm dedupe caught them.

Then tell me: what's fragile, what you'd do differently, what you assumed.
```

---

## Prompt 9 — Remote feeds

```
Read CLAUDE.md and SPEC.md. Phases 0-8 are complete.

Build Phase 9: RemoteOK, Remotive, and We Work Remotely. One parser, three
configs — if you're writing three parsers, the abstraction is wrong.

We Work Remotely requires attribution. Add a visible credit with a link back.

These feeds are ground truth for remote detection, since everything on them is
remote by definition. Re-run the heuristic against them and report accuracy. If
it's worse than Phase 2 suggested, say so plainly.

Then tell me: what's fragile, what you'd do differently, what you assumed.
```

---

## Prompt 10 — Gmail alert channel

```
Read CLAUDE.md and SPEC.md. Phases 0-9 are complete.

Build Phase 10: the Gmail alert channel. I've had LinkedIn and Indeed job
alerts running for weeks, so there's real mail to test against.

Read-only Gmail scope. Never send, delete, or modify. Only process messages
from configured alert senders — nothing else in the mailbox is read or stored.

One parser per sender with per-sender failure isolation: a broken LinkedIn
parser must not stop the Indeed one. Alert URLs are tracking-wrapped — unwrap
them before dedupe or the same job appears twice.

Expect title, company, location, link. Not full descriptions.

Process real emails, show what was extracted, and confirm dedupe collapses an
alert listing against the same role already pulled from an ATS board. Feed it a
malformed email and show me the error.

Then tell me: what's fragile, what you'd do differently, what you assumed.
```

---

## Prompt 11 — Gig track

```
Read CLAUDE.md and SPEC.md. Phases 0-10 are complete and the job track is in
daily use.

Build Phase 11: the gig track.

Sources: Google Alerts RSS (my feed URLs go in config so I can add alerts
without code changes — this is the primary gig source and the noisiest);
Reddit .rss for r/forhire, r/smallbusiness and local subreddits, polled hourly;
Craigslist via the Open RSS proxy; and the HN "Freelancer? Seeking Freelancer?"
monthly thread via Algolia.

Do NOT use the Reddit OAuth API or .json endpoints — read CLAUDE.md on why.
Keep the Reddit adapter isolated enough that its removal breaks nothing else.

Create gig_profile.yaml and gig_weights.yaml with the five gig dimensions.
Add a Jobs/Gigs toggle to both surfaces.

Google Alerts will produce heavy noise. The gig scorer has to filter it — if
the top results are junk, the scoring needs work, not the source.

Run both tracks, confirm the toggle works, show me the top 10 gigs so I can
judge whether they're work I could deliver, and verify no job-track regression.

Then tell me: what's fragile, what you'd do differently, what you assumed.
```

---

## Prompt 12 — Automation and cutover

```
Read CLAUDE.md and SPEC.md. Phases 0-11 are complete.

Build Phase 12: full automation via GitHub Actions.

A scheduled workflow that fetches every source, normalizes, dedupes, scores,
writes the static export, commits it, and triggers the Cloudflare Pages build.
All credentials in Actions Secrets — the repo is public.

Add failure notification. A silently broken pipeline is worse than no pipeline;
I need to find out when a source dies.

Tell me exactly which secrets to add and where. Then break one on purpose and
show me that the notification fires.

Then tell me: what's fragile, what you'd do differently, what you assumed.
```

---

## Prompt 13 — HN Who is Hiring (optional)

```
Read CLAUDE.md and SPEC.md. Phases 0-12 are complete.

Build Phase 13: HN "Who is Hiring" via the Algolia HN Search API. Free-text
comment parsing. Accept partial extraction — a listing with a missing field
beats a dropped listing.

Run it and show me 15 parsed results next to their original comments so I can
see what the parser lost.

Then tell me: what's fragile, what you'd do differently, what you assumed.
```

---

## Then — use it

Two weeks minimum before Phase 14. Keep a list of what breaks and what annoys
you.

---

## Prompt 14 — Outcome tracking

**Do not run this until you have applied to at least 30 listings through the app.**

```
Read CLAUDE.md and SPEC.md. Phases 0-13 are complete and I've been using
Kestrel daily with real applications logged.

Build Phase 14: outcome tracking. Analyze whether the score actually predicted
anything — response rate by score band, by source, by how fresh the posting was
when I applied, by day of week.

Then tell me what the data says, including if it says the scoring model is
wrong. Recommend weight adjustments based on evidence, not intuition, and write
the findings into docs/scoring-validation.md.

Be honest if the sample is too small to conclude anything. A real "not enough
data yet" beats a confident number built on twelve applications.

Then tell me: what's fragile, what you'd do differently, what you assumed.
```
