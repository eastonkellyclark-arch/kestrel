# Phase 6 — The Desk

## What was built
- Status lifecycle: new → interested → applied → responded → interview → closed
- Timestamped status history with optional notes per transition
- Per-listing notes (independent of status changes)
- Pipeline view: stage counts
- CSV export: listings with status, notes, opened correctly in spreadsheet
- Markdown export: grouped by status, with notes
- Registry editor: list, add, activate/deactivate

## Endpoints

| Method | Path | Description |
|---|---|---|
| PATCH | /desk/listings/{id}/status | Update status with history |
| GET | /desk/listings/{id}/history | Timestamped status history |
| POST | /desk/listings/{id}/notes | Add a note |
| GET | /desk/listings/{id}/notes | List notes |
| GET | /desk/pipeline | Stage counts |
| GET | /desk/export/csv | CSV download |
| GET | /desk/export/markdown | Markdown download |
| GET | /desk/registry | List registry entries |
| POST | /desk/registry | Add/update entry |
| PATCH | /desk/registry/{id} | Activate/deactivate |

## Verification
- 5 listings moved through 3 statuses each (new→interested→applied→responded/interview)
- Full re-ingest (translate_all) and rescore after status changes
- **All 5 statuses, 15 history entries, and 5 notes survived intact**
- CSV export opens correctly, includes notes
- Markdown export groups by status with notes

## No authentication code
Cloudflare Access handles identity at the edge. See deployment instructions below.
