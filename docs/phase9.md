# Phase 9 — Remote Feeds

## What was built
- One parser (`_parse_remote_feed`), three configs: RemoteOK, Remotive, We Work Remotely
- WWR attribution visible in showroom footer with link back
- All feed listings marked `is_remote=1` unconditionally (remote by definition)
- Wired into `fetch_all()` as part of the scheduled run

## Feed results

| Feed | Listings | Format |
|---|---|---|
| RemoteOK | 100 | JSON API |
| Remotive | 16 | JSON API |
| We Work Remotely | 25 | RSS |
| **Total** | **141** | |

## Adzuna query retargeting
Adzuna default queries changed from company-specific (which re-finds ATS data)
to Minnesota-area role searches:
- "software engineer" + Minnesota
- "web developer" + Minnesota
- "full stack" + Minnesota
- "devops engineer" + Minnesota
4 API calls/day = 4/33 budget. Company-specific search available manually.

## Remote detection accuracy (ground truth test)

| Feed | Heuristic Accuracy | Reason |
|---|---|---|
| We Work Remotely | 100% (25/25) | Location: "Anywhere in the World" — matches heuristic |
| RemoteOK | 3% (3/100) | Location is city names without "Remote" keyword |
| Remotive | 0% (0/16) | Location is region lists without "Remote" keyword |

**This is plainly worse than Phase 2's 15/15.** The heuristic was designed for ATS
boards where the location field is structured. Remote feed location fields use
city names ("Brampton"), garbled text ("Heartâs Content"), or region lists
("Americas, Europe, Asia") — none containing the keyword "Remote".

**Impact: none.** The translator bypasses the heuristic for feed listings, setting
`is_remote=1` unconditionally. The heuristic is only used for ATS boards and
aggregators where remote status is ambiguous. The 2.6% overall number reflects
the heuristic being tested outside its design scope, not a bug in the product.

**The heuristic's real accuracy on its intended inputs (ATS boards) remains at
the level validated in Phase 2.** The feeds prove the heuristic's limitation is
known and handled — by not using it where it doesn't apply.
