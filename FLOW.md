# Kestrel — How It Works

Plain-language map of the pipeline. Every named part has one job.

---

## The map

```
  YOU PASTE A CAREERS URL
            │
            ▼
     ┌──────────────┐
     │  THE SNIFFER │  figures out which hiring system a company uses
     └──────┬───────┘
            ▼
     ┌──────────────┐
     │ THE ROLODEX  │  the saved list of companies worth checking
     └──────┬───────┘
            │
            ▼
╔═══════════════════════════════════════════════════════════════╗
║                        THE COLLECTOR                          ║
║              goes out on a schedule and fetches               ║
╚═══════════════════════════════════════════════════════════════╝
     │              │              │              │            │
     ▼              ▼              ▼              ▼            ▼
 COMPANY       AGGREGATORS    REMOTE FEEDS   YOUR INBOX    GIG SOURCES
 BOARDS                                                     
 Greenhouse    Adzuna         RemoteOK       LinkedIn      Google Alerts
 Lever         USAJobs        Remotive       Indeed        Reddit
 Ashby                        We Work        ZipRecruiter  Craigslist
 Workable                     Remotely       Glassdoor     HN Freelancer
 Recruitee                                                 SAM.gov
     │              │              │              │            │
     └──────────────┴──────┬───────┴──────────────┴────────────┘
                           ▼
                   ┌───────────────┐
                   │   THE VAULT   │  keeps every raw reply, untouched
                   └───────┬───────┘
                           ▼
                 ┌───────────────────┐
                 │  THE TRANSLATOR   │  makes many formats into one
                 └─────────┬─────────┘
                           ▼
                 ┌───────────────────┐
                 │    THE MERGER     │  collapses the same listing twice
                 └─────────┬─────────┘
                           ▼
  YOUR PROFILE ──────►┌───────────┐
  YOUR WEIGHTS ──────►│ THE JUDGE │  scores everything 0–100
                      └─────┬─────┘
                            │
            ┌───────────────┴───────────────┐
            ▼                               ▼
   ┌──────────────────┐            ┌──────────────────┐
   │   THE SHOWROOM   │            │     THE DESK     │
   │  public, anyone  │            │  private, you    │
   │  ranked listings │            │  what you applied│
   │  score reasoning │            │  to, notes, status│
   └──────────────────┘            └──────────────────┘
   kestrel.adlaunch.studio         kestrel.adlaunch.studio/desk
```

---

## What each part does

### The Sniffer
Hand it a company's careers page. It works out which hiring system that company
runs on and pulls out their ID within it. That ID fetches their jobs forever
after. When it can't tell, it asks you and remembers your answer.

*Why it matters:* there's no directory of which companies use which system.
Without this, you'd build that list by hand, one company at a time.

### The Rolodex
The saved list of companies and their IDs. Grows every time the Sniffer learns
one. The part that gets more valuable the longer you use the app.

### The Collector
Fetches on a schedule. Talks to five kinds of places and treats each with the
right etiquette — waits when told to wait, backs off when refused, and shouts
clearly when something is actually broken instead of quietly returning nothing.

### The Vault
Stores every reply exactly as it arrived, before anything is interpreted.

*Why it matters:* when the interpretation turns out to be wrong, the original is
still there. Fix the code, re-run, never re-fetch — which matters a lot when one
source only allows about 33 requests a day. It also quietly builds a history:
months of snapshots become a record of which companies are growing.

### The Translator
Many sources, many shapes, one common format: title, company, location, remote
or not, description, pay, date, link.

Also where the hardest guess happens — **is this actually remote?** No source
reliably says. It's worked out from how the posting reads, and it will sometimes
be wrong.

### The Merger
The same job appears on five boards with five slightly different spellings. The
Merger decides which are really the same and links them. Never deletes —
duplicates point at one main copy, so you can see which sources carried it.

### The Judge
Scores everything out of 100. Jobs and gigs get judged on different things.

**Jobs:** skill match (35), degree required or not (20), freshness (15),
location (15), seniority (10), whether it came straight from the employer (5).

**Gigs:** can you actually build it (35), is there a budget (25), how fresh (20),
how local (10), how many people already replied (10).

Two plain text files control each. Change one, re-run, everything reorders
instantly — no re-fetching, no code changes.

**Every score shows its reasoning.** You can always see why something ranked
where it did. A ranking nobody can explain isn't worth showing anyone.

### The Showroom
The public page. Ranked listings, filters, and the score reasoning. Anyone with
the link can see it — it's all public postings, nothing private.

This is what a hiring manager opens. It's a static page refreshed automatically,
so it loads instantly and costs nothing to host.

### The Desk
Your private side, behind a sign-in. What you applied to, when, what came back,
your notes, and the registry editor.

The sign-in isn't code Kestrel wrote — it's handled at the edge by Cloudflare,
so there's no password stored anywhere in the app.

The critical property: this survives everything. Re-fetch, re-score, the posting
vanishing entirely — your record stays.

---

## The one-sentence version

Kestrel learns which companies to watch, checks them and a dozen other sources
on a schedule, keeps every raw reply, translates it all into one format, merges
duplicates, ranks what's left against profiles you control, shows the good part
publicly, and privately remembers what you did about it.
