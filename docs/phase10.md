# Phase 10 — Gmail Alert Channel

## What was built

### Gmail adapter
- Read-only Gmail scope (`gmail.readonly`). Never sends, deletes, or modifies.
- Only processes messages from configured alert senders:
  - LinkedIn: `jobs-noreply@linkedin.com`
  - Indeed: `alert@indeed.com`
  - ZipRecruiter: `noreply@ziprecruiter.com`
  - Glassdoor: `noreply@glassdoor.com`
- Per-sender failure isolation: a broken LinkedIn parser does not stop Indeed.
- Tracking URL unwrapping before storage (dedupe depends on this).

### URL unwrapping
- LinkedIn: `linkedin.com/comm/jobs/view/ID` → `linkedin.com/jobs/view/ID`
- Indeed: `indeed.com/rc/clk?...jk=KEY` → `indeed.com/viewjob?jk=KEY`
- Generic: `?url=`, `?redirect=`, `?dest=` parameter extraction

### Remote detection approach
Gmail alert locations ("Minneapolis, MN") are unreliable for remote status.
Two strategies:

1. **Ambiguous default**: if the heuristic says "not remote" but there's no
   strong negative signal, set `remote_confidence=0.3` instead of 0.0.
   The scorer treats this as uncertain rather than confidently wrong.

2. **Cross-reference on dedupe**: when a gmail_alert listing is linked to an
   ATS canonical (via the Merger), inherit the ATS version's remote status.
   ATS boards have structured workplace data; Gmail doesn't. Free when it
   applies.

### Quality gate fix
Moved RemoteOK spam filter from ingestion (adapter) to translation time.
Raw vault keeps everything. Filter config in `config/quality_gate.yaml`:
- `min_title_words: 3` (configurable)
- `spam_phrases: [seeking a job, looking for, ...]`
- `gated_sources: [remoteok]`
57 listings marked as `description_quality="filtered"`, still in DB.

### Translator parser
`_parse_gmail_alert`: handles truncated data (title + company + location + URL,
no full description). Sets `description_quality="truncated"`.

## What's blocked until Google Cloud setup

The adapter code is complete but needs OAuth credentials to run. Setup:

1. Google Cloud Console → create project "Kestrel"
2. Enable Gmail API
3. Create OAuth Desktop credentials
4. Download `credentials.json` to project root
5. Set `KESTREL_GMAIL_CREDENTIALS_JSON=./credentials.json` in `.env`
6. First run opens browser for OAuth consent

## What's NOT blocked
- Parsers (LinkedIn, Indeed, ZipRecruiter, Glassdoor)
- URL unwrapping logic
- Per-sender failure isolation
- Cross-reference remote inheritance in Merger
- Quality gate (already moved and tested)
