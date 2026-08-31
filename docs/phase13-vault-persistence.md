# Phase 13 — Vault persistence, date parsing, dedupe, silent failures

Date: 2026-08-31

Fixes four defects found while auditing 13 days of unattended pipeline runs
(41 runs, 2026-08-19 → 2026-08-31). The pipeline was healthy; the storage
layer and several silent failures were not.

---

## 1 & 2 — The vault was deleted every 6 hours, and the repo grew 140 MB/day

### What was wrong

`.github/workflows/pipeline.yml` ran `rm -f data/kestrel.db` before every
fetch, with the comment *"schema may have changed since last committed DB"*.
It then force-added the whole 35.7 MB database back to `master`.

Both halves were wrong at once:

- **Data loss.** The vault never reached back further than one run. Comparing
  the Aug 20 export to Aug 31: 706 listings disappeared, 715 appeared, 925
  survived. The 706 were not marked stale — they were gone. The design
  property that "when a parser is wrong, re-run against stored data instead of
  re-fetching" did not exist; there was only ever 6 hours of stored data.
- **Repo growth.** 188 database blobs plus 59,489 `data/export` objects. `.git`
  reached 210 MB and was growing ~140 MB/day.
- **Latent privacy bug.** `git add data/ -f` force-added the *whole* database,
  including `status_history`, `notes` and `resumes`, to a **public** repo.
  Those tables were empty so nothing leaked, but any desk use followed by a
  commit would have published application history and private notes.

### What replaced it

**`backend/app/migrations.py`** — versioned migrations. The baseline schema
(v4) in `database.py` is frozen and must not be edited again; every change is
a new entry in `MIGRATIONS`. `init_db()` runs them. A database newer than the
code is a hard error rather than a silent mis-read. `_add_column` makes a
part-applied migration re-runnable.

Migration 5 adds staleness tracking. Because the database now survives,
listings that vanish from their source would otherwise linger forever.

**`backend/app/vault.py`** — vault snapshots. A snapshot contains **only**
`_meta`, `registry`, `raw_listings`. Everything else is derived and rebuilt by
translate → merge → score each run, so no listing IDs cross machines and
`canonical_id` cannot be corrupted. Private tables are structurally excluded:
the snapshot is built by copying an explicit allowlist into a fresh database,
and `export_snapshot` refuses to write if a private table is present.

Snapshots are gzipped (35.7 MB → **3.05 MB**, 11.7×) and force-pushed as a
single-commit orphan branch `data-vault`, so the repository carries exactly
one copy instead of one per run.

**Staleness.** `raw_listings.last_seen_at` advances every time a source still
returns a listing; `raw_json` and `fetched_at` stay write-once so a fixed
parser can still be re-run against the original response. The translator
copies `last_seen_at` and `vault_source` onto the listing, so staleness is a
column comparison, not a join.

`mark_stale` only judges sources that fetched successfully this run. A source
that errored has told us nothing about whether its listings still exist, and
treating its silence as death would empty the board on a bad run. Stale
listings keep their row and their application history — `is_stale` is a
separate column from `status` — and are excluded from the export only.

`vault_source` exists because the vault's source label is not always the
listing's: Reddit vaults under `reddit` and surfaces as `r/forhire`. Keying on
`listings.source` alone would have silently excluded every Reddit listing from
staleness.

### Still outstanding

`.git` is still 210 MB. Growth has stopped, but purging the existing blobs
needs a history rewrite and a force-push to a public repo — the user's call.

---

## 6 — We Work Remotely dates were unparseable

`translator.py` normalised every date with `posted_at[:19]`. That works for
ISO 8601 and silently corrupts anything else:

```
"2026-08-12T18:00:00Z"            -> "2026-08-12T18:00:00"    ok
"Wed, 12 Aug 2026 18:00:00 +0000" -> "Wed, 12 Aug 2026 18"    garbage
```

The garbage failed `datetime.fromisoformat` in the freshness scorer, which
fell back to 40/100 ("no date"). Every WWR listing lost ~9 points and was
ranked as undated rather than fresh.

**`backend/app/dates.py`** — `normalize_timestamp` handles ISO 8601 (offsets,
trailing `Z`, USAJobs' 7-digit sub-seconds), RFC 822/2822 as used by RSS,
epoch seconds and milliseconds. It converts to UTC and returns a string
`fromisoformat` can always read, or `""` — an explicit "no date" the scorer
already handles — rather than a truncated string that looks like a date.

All nine parse sites in `translator.py` now route through it. Result: **zero
undated listings across all ten sources**, where WWR previously had 25.

---

## 5 — Dedupe was not "too tight"; it was disabled and mis-scoring

The 103 duplicate company+title pairs were **all same-source**, and
`merge_all` skipped same-source comparisons entirely:

```python
if row_a["source"] == row_b["source"]:
    continue  # "same source can't produce dupes because of UNIQUE(source, source_id)"
```

That reasoning is wrong. The constraint stops the same *posting* being stored
twice; it does nothing about a company posting the same *role* under several
job IDs, which is where nearly every real duplicate came from. The threshold
was never the problem.

But enabling same-source comparison alone merged **519 of 1644** listings,
because `_location_similarity` returned 0.90 for any two strings containing
"remote". Two failures had to be fixed together:

1. **Remote regions.** "Remote (USA)" vs "Remote (Peru)" scored 0.90. Sezzle
   and Livefront post each role in 7–8 countries; those are different jobs,
   and merging them can hide the US role behind a canonical nobody here can
   take.
2. **Hierarchical locations.** Adzuna emits
   `"US, Minnesota, Hennepin County, Minneapolis"`. Raw string similarity is
   dominated by the shared prefix, so Minneapolis vs Duluth scored 0.95 —
   150 miles apart, and directly corrupting the location score.

`_location_similarity` now compares **token sets** (Jaccard), insensitive to
ordering and hierarchy depth, with place aliases (`MN`↔`Minnesota`,
`USA`↔`US`) and generic words dropped. Two aliasing bugs found by testing
against real rows: `"america" -> "us"` made *Latin America* American, and the
token `"saint"` matched *Saint Cloud* against *Saint Louis County*.

Gates, all evidence-driven:

| Gate | Value | Reason |
|---|---|---|
| Company | 0.70 | unchanged |
| `LOCATION_GATE` | 0.50 | below this the postings are different places |
| Same-source title | exact | the company's own board distinguishes its roles |
| `CROSS_SOURCE_TITLE_GATE` | 0.85 | aggregators truncate and decorate titles |

The same-source exact-title rule came from the data: exact-title merges held
steady at 102 across every fuzzy threshold from 0.80 to 1.00, while the fuzzy
tail was all false positives ("Workers AI" vs "Workers Runtime", "Account
Executive, Korea" vs "…Seattle").

**Result: 519 → 47 merged away.** Zero same company+title+location groups
remain, no canonical chains, no self-references, and Livefront's 27
international postings are all preserved.

Also added: chain flattening (a duplicate never points at another duplicate),
and `dedupe_verdict()`, which reports *which gate* blocked a pair so the
near-miss log stays tunable — a gate that silently returns zero is not.

---

## 3 & 8 — Two silent failures

### Gmail never ran in CI

The workflow wrote only Adzuna and USAJobs keys into `.env`, so
`settings.gmail_credentials_json` was empty and `collector.py`'s bare
`if creds:` skipped the whole channel with **no log line at all**. LinkedIn,
Indeed, ZipRecruiter and Glassdoor contributed nothing for 13 days, silently.

**Can it run in CI? Yes.** A stored token with a refresh token renews without
a browser; only the first authorisation needs a human, and that already
happened. It needs the token in Actions Secrets.

**But the current token is dead.** `invalid_grant: Token has been expired or
revoked` — Google expires refresh tokens after 7 days while the OAuth consent
screen is in *Testing* publishing status. The token was issued Aug 17.

Three fixes:

- `FetchOutcome.SKIPPED` — a source that never ran no longer looks like a
  source that ran and found nothing. It is reported, logged as a warning, and
  excluded from `healthy_pairs` so staleness draws no conclusions from it.
- `fetch_alerts` refuses interactive auth when headless (`CI`,
  `KESTREL_HEADLESS`). `run_local_server()` would otherwise block on a browser
  that will never open until the 15-minute job timeout.
- A dead refresh token used to raise out of `fetch_alerts` and take the whole
  fetch step down. It now returns a `FetchResult` naming the cause and the fix.

### Every commit message was truncated

All 41 pipeline commits ended at the em dash. The cause:

```
python -c 'import sys,json; d=json.load(sys.stdin); print(f"{d[\"total_fetched\"]} ...")'
```

Inside single quotes the `\"` stays literal, and Python rejects backslashes in
f-string expressions: `SyntaxError: f-string expression part cannot include a
backslash`. stdout was empty every run; stderr went to the log unnoticed.

Reporting moved to a **job summary** (`$GITHUB_STEP_SUMMARY`) with per-source
outcomes, skipped sources, and vault statistics — where a broken formatter is
visible rather than silent. `master` no longer receives data commits at all.

---

## Testing

134 → 141 tests, from 69. New: `test_vault_persistence.py` (15),
`test_dates.py` (25), `test_merger.py` (dedupe had **no** tests despite
CLAUDE.md requiring them), `test_source_skipping.py` (7).

The persistence tests assert the property that was broken: data survives.
Migration preserves rows, snapshots round-trip, import is additive and
idempotent, private tables cannot leak, a failed source cannot mark listings
stale, and Reddit's label mismatch is handled.

---

## Session review

**Fragile.**
- `data-vault` is a force-pushed orphan branch. It is durable (it is in the
  remote), but a bad snapshot overwrites the good one. There is no generation
  history. A weekly dated tag would give a rollback point cheaply.
- The vault is now unbounded. Translate re-parses the whole vault every run;
  fine at 1,644 rows, worth watching at 50,000.
- `raw_listings` is UNIQUE(source, source_id), so the vault stores one row per
  listing, not a snapshot per fetch. "Historical snapshots are never pruned"
  is now true of listings, but there is still no history of a single posting
  changing over time.
- `LOCATION_GATE = 0.50` and `CROSS_SOURCE_TITLE_GATE = 0.85` are tuned
  against one day of data. The near-miss log names the blocking gate now, so
  they are reviewable.

**Would do differently.**
- The `rm -f` was added as a quick fix for a schema change. Writing the
  migration then would have cost an hour and saved 13 days of vault.
- I nearly shipped the same-source dedupe fix without the location fix. It
  would have merged 519 listings and quietly hidden real jobs. Measuring
  against real rows before committing caught it.

**Assumed.**
- Job postings are public, so the vault is safe on a public branch. Private
  tables are excluded structurally rather than by policy.
- 24 hours (two missed runs) is the right staleness tolerance.
- Merging same-role-different-city postings is wrong for a Farmington-based
  search with an 80 km radius, even where they are arguably one requisition.

**Not touched.** Scoring (#4) is untouched by request. The fixes above changed
neither the median (12.4) nor the maximum (63.0), which is itself evidence
that the low scores are structural rather than a symptom of these bugs.
