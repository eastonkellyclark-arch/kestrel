# COSTS.md — Kestrel

**Target: $0/month to build, $0/month to run.**

This file exists so the constraint stays checkable. If a session proposes
something that costs money, it violates CLAUDE.md and needs a decision from
Easton, not a workaround.

---

## Data sources — all $0

| Source | Cost | Limit to respect |
|---|---|---|
| Greenhouse, Lever, Ashby, Workable, Recruitee | $0 | None — no auth, no quota |
| Adzuna | $0 | ~1,000 calls/month (~33/day). **Enforce in code.** |
| USAJobs | $0 | Free key, generous |
| RemoteOK, Remotive | $0 | Be polite; cache |
| We Work Remotely | $0 | **Attribution required** |
| HN via Algolia | $0 | Be polite |
| Gmail API | $0 | Far above our use |
| Google Alerts RSS | $0 | None |
| Reddit `.rss` | $0 | ~1 req/min per feed |
| Craigslist via Open RSS | $0 | Third-party goodwill; don't hammer it |
| SAM.gov | $0 | Free key |

**Excluded on cost:** SerpApi, LoopCV, TheirStack, Techmap, BrightData,
JobsPipe, and every other paid aggregator. Also excluded: Minnesota SOS filings
data — free only under a non-commercial certification that a company-domain
project can't credibly make.

---

## Infrastructure — all $0

| Item | Service | Cost |
|---|---|---|
| Showroom hosting | Cloudflare Pages | $0 — unlimited bandwidth |
| Sign-in for /desk | Cloudflare Access | $0 — free up to 50 users, permanent |
| Pipeline scheduling | GitHub Actions | $0 — unlimited minutes on public repos |
| Repo | GitHub | $0 |
| Database | SQLite | $0 |
| Domain | `kestrel.adlaunch.studio` | $0 — already owned |

**Deliberately avoided:** Vercel Hobby (prohibits commercial use, and this sits
on a company domain), Fly.io (no free tier since 2024), Railway (trial credit
then a monthly minimum), Render (free tier sleeps, giving a cold start on the
one page meant to impress).

**Why the architecture is free:** the showroom is a static export, so there is
no always-on backend to pay for. The pipeline runs in Actions. The desk runs
locally. Nothing needs a server sitting idle.

---

## The one real cost

**Claude Code.** Pro is $20/month; Max is $100 or $200. This is the largest
line item in the project and the one nobody budgets for.

Mitigations, all already in the workflow:
- One phase per session, `/clear` between them
- CLAUDE.md keeps context small instead of re-explaining every session
- "Done when" tests prevent redoing work
- Committing every session means a crash costs minutes

If you're hitting Pro limits more than twice a week, Max 5x buys back real time.
That's a productivity decision, not a project cost.

---

## Tripwires

Stop and ask before any of these:

- Any source requiring a credit card, even for a free trial
- Any hosting that bills after a credit expires
- Exceeding the Adzuna daily budget
- Anything requiring an always-on server
- An LLM API call anywhere in the pipeline
- Commercial-tier data licensing of any kind

---

## If it ever needs to cost something

In rough order of value per dollar:

1. **Domain of its own** (~$12/yr) — only if you want it off the company domain,
   which would also reopen the MN filings option.
2. **Claude Max** ($100/mo) — a productivity purchase, not a project one.
3. **Adzuna paid tier** (sales-negotiated) — only if the free quota proves to be
   the actual bottleneck, which it probably won't be with the ATS layer primary.

Nothing on this list is needed to ship.
