# Phase 12 — Automation

## GitHub Actions pipeline

Workflow: `.github/workflows/pipeline.yml`

Schedule: every 6 hours (`0 */6 * * *`) + manual trigger.

Steps:
1. Fetch all sources (ATS boards + aggregators + remote feeds + gig feeds)
2. Translate + merge + score
3. Export static data
4. Build frontend
5. Deploy to Cloudflare Pages via wrangler
6. Commit data updates

## Secrets required

Add these 5 in GitHub repo Settings → Secrets and variables → Actions:

| Secret name | Value | Source |
|---|---|---|
| `ADZUNA_APP_ID` | Your Adzuna app ID | developer.adzuna.com |
| `ADZUNA_APP_KEY` | Your Adzuna app key | developer.adzuna.com |
| `USAJOBS_API_KEY` | Your USAJobs API key | developer.usajobs.gov |
| `USAJOBS_EMAIL` | Your registered email | developer.usajobs.gov |
| `CLOUDFLARE_API_TOKEN` | Scoped API token (see below) | dash.cloudflare.com/profile/api-tokens |

### Cloudflare token — minimum scope

Do NOT use the Global API Key. Create a scoped token:

1. dash.cloudflare.com/profile/api-tokens → Create Token
2. Use template: **Custom token**
3. Token name: `Kestrel Pipeline`
4. Permissions: **Account** — **Cloudflare Workers Scripts** — **Edit**
5. Account Resources: Include — your account
6. **Do NOT add any Zone Resources** — deploy needs no DNS/zone access
7. Continue to summary → Create Token → Copy

This token can only deploy workers. It cannot read or modify DNS,
domains, billing, or any other account resources.

Gmail credentials are NOT in CI yet — they require interactive OAuth.
The pipeline skips Gmail when credentials aren't configured.

## Failure notification

- Individual source failures: logged as `::warning::` in Actions
- More than half of sources failing: exits with `::error::` and fails the job
- `failure()` step prints summary and could trigger Slack/email
- Silent failures (source returns 0 results): logged but not treated as errors
  (a company genuinely having no openings is not a pipeline failure)

## Freelancer.com research

**Freelancer.com has a public JSON API — no auth, no key:**
`https://www.freelancer.com/api/projects/0.1/projects/active?query=web+development`
Returns 1,139 active projects with titles, budgets, bid counts.
Also has RSS at `freelancer.com/rss.xml` (20 generic items).

**Upwork is closed:** all endpoints return ConnectError. Historical RSS feeds
are dead. API requires OAuth + approved app. Not usable.

Freelancer.com is noted for future gig track work — not built yet.

## Schema fix

Removed department-field hack for gig classification. Added proper columns:
- `gig_classification TEXT` — demand, supply, ambiguous, or NULL for jobs
- `gig_confidence REAL` — 0.0-1.0 classification confidence

## HN Freelancer disabled

Set `enabled: false` in `config/gig_feeds.yaml`. 15-33 comments/month,
mostly SEEKING WORK. Zero web dev demand.
