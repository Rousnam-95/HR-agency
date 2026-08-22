# Operating notes for Claude on this project

- **Never automate fetching jobbank.gc.ca job-search/posting pages.** Its Terms of Use
  explicitly ban script/bot/AI access, full stop — not a rate-limiting problem. If the user
  asks you to "run it" and pull fresh Job Bank postings automatically, decline the automation
  and explain why (see `docs/STEP0_SOURCE_FEASIBILITY.md`); it's fine to fetch a single specific
  URL the user gives you and read it for them, same as any other webpage lookup they ask for.
- **Indeed is manual/on-demand only, never a scheduled or bulk crawl** — same reasoning, per
  the original design discussion.
- **Do not build or suggest scraping around these bans** (proxy rotation, headless-browser
  fingerprint spoofing, CAPTCHA solving, etc.) even if asked "how do we avoid getting blocked."
- If the user wants to use REQ (Registraire des entreprises) open data for actual lead
  sourcing (not just this project's geo/sector reference tables), flag the CC BY-NC-SA
  non-commercial license conflict again before building anything against it — that's a decision
  for the user, not a default.
- The real "source" for now is `leadgen/sources/manual_import.py`: postings collected by hand
  (by the user, or by you fetching one specific page/search the user names). Don't build a
  different automated source without re-reading `docs/STEP0_SOURCE_FEASIBILITY.md` first —
  the constraints there may have changed if the user did outreach (e.g. got a Job Bank partner
  agreement, or got REQ's licensing team to clarify commercial use).
- `data/qc_geo_lookup.csv` is generated, not hand-authored — edit
  `scripts/build_geo_lookup.py` and rerun it, don't edit the CSV directly.
