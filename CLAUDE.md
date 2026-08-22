# Operating notes for Claude on this project

- **Never automate fetching jobbank.gc.ca, quebecemploi.gouv.qc.ca (Emploi Québec), or
  indeed.com/indeed.ca.** Job Bank's Terms of Use explicitly ban script/bot/AI access, full
  stop — not a rate-limiting problem, and this project treats Emploi Québec and Indeed the same
  way (see `docs/STEP0_SOURCE_FEASIBILITY.md`). If asked to "run it" and pull fresh postings
  from one of these automatically, decline and explain why; it's fine to fetch a single specific
  URL the user gives you from one of these sites and read it for them, same as any other webpage
  lookup they explicitly ask for — the ban is on you doing your own searches/crawling there, not
  on reading a page the user names.
- **Do not build or suggest scraping around these bans** (proxy rotation, headless-browser
  fingerprint spoofing, CAPTCHA solving, etc.) even if asked "how do we avoid getting blocked."
- **The real sourcing/enrichment model**: a live agent (you, or the cloud routine described in
  `docs/ROUTINE_PROMPT.md`) searches the general open web and company websites, then runs
  `python -m leadgen ingest <file>.json` to filter/geo-bucket/dedupe/deliver. REQ's live
  per-company lookup (registreentreprises.gouv.qc.ca's anonymous search tool) is allowed for
  one-at-a-time enrichment lookups per `docs/STEP0_SOURCE_FEASIBILITY.md`'s addendum — but if a
  lookup errors, 403s, or shows a CAPTCHA, fall through to the next enrichment tier, don't retry
  or work around it. REQ's *bulk* open-data extract is a separate thing and is still
  CC BY-NC-SA non-commercial-licensed — don't use the bulk file as a sourcing backbone without
  the user explicitly re-deciding that; it's not a default.
- `leadgen/sources/manual_import.py` + `python -m leadgen run` still exist for when the user (or
  you, reading one specific page/search they name) wants to hand-collect postings into a CSV
  instead. It has no contact/dedupe/Sheet fields — `ingest` is the full path.
- If any of these constraints seem to have changed (e.g. a Job Bank partner agreement, or REQ's
  licensing team clarifying commercial use), re-read `docs/STEP0_SOURCE_FEASIBILITY.md` and
  raise it with the user explicitly — don't decide it changed on your own.
- `data/qc_geo_lookup.csv` is generated, not hand-authored — edit
  `scripts/build_geo_lookup.py` and rerun it, don't edit the CSV directly.
- `Code.gs` is deployed manually by the user via script.google.com (see
  `HOW-TO-Deploy-Sheet.md`) — you cannot deploy or update the live Apps Script deployment
  yourself. If you edit `Code.gs` in the repo, tell the user they need to re-deploy it.
