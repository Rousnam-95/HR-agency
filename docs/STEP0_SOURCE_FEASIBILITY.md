# Step 0 — Source Feasibility Findings (2026-08-22)

This is a research spike, not a design doc. It changes the sourcing strategy for the whole
project, so read it before touching `leadgen/sources/`.

## TL;DR

**None of Job Bank, Emploi Québec, or the REQ open-data extract can feed an automated,
company-name-bearing lead list today.** Each fails for a different reason. The pipeline is
built around a **manual-import model** instead: a human (you, or Claude fetching one page at
a time when you explicitly ask) collects raw postings/company info, and the software does the
filtering, geo-bucketing, headcount categorization, and dedupe that's tedious to do by hand.
Automated bulk pulling is not implemented for any job-board source. This is a deliberate,
not-yet-solved gap — see "What this means for the project" below.

## Job Bank Canada (jobbank.gc.ca)

- **There is a real, official open dataset**: "Job Postings Advertised on Canada's National
  Job Bank Website" on open.canada.ca
  (https://open.canada.ca/data/en/dataset/ea639e28-c0fc-48bf-b5dd-b8899bd43072), updated
  monthly, CSV, bilingual. I downloaded the July 2026 English file (52,000 rows, ~10,000
  mentioning Quebec) and inspected the real header row.
- **It has no employer/company name field at all.** Columns are: job location snapshot ID,
  job title, NOC 2016/NOC21 code + name, external indicator, first posting date, vacancy
  count, official language, education/experience level, government type, placement agency
  flag, **NAICS**, province/territory, city, work location postal code, economic region,
  various-location flag, employment type/term details, salary fields, hours fields. Useful for
  aggregate sector/region/headcount *signal* (e.g. "how many general-labour NAICS postings are
  open in the Grand Montréal region this month"), **useless on its own for identifying which
  company to call.**
- **The live site's Terms of Use explicitly prohibit all automated access**: "Job Bank
  prohibits the use of any script, robot, spider, Web crawler, screen scraper, automated query
  program, artificial intelligence or other automated device, software, or process to access
  its services." (jobbank.gc.ca/termsofuse-employer.xhtml / cb.guichetemplois.gc.ca). This is
  broader than a typical scraping ban — it names AI explicitly. robots.txt itself only sets
  `Crawl-delay: 5` with no `Disallow`, but the Terms of Use override that: **no automated or
  AI-driven fetch of jobbank.gc.ca job-search pages, ever, regardless of rate.** This is a hard
  line, not a throttling problem.
- Job Bank does run a legitimate XML-feed program, but it's for job-board *partners* under a
  formal agreement to redistribute postings outward (or send postings in) — not a fit for an
  individual sales rep's personal tool, and not something I can set up unilaterally.
- Quebec coverage is real (thousands of QC postings in the open dataset), so the "does Quebec
  even show up in Job Bank" concern is resolved — coverage isn't the problem, employer-identity
  and the ToS ban are.

## Emploi Québec / Québec Emploi (quebecemploi.gouv.qc.ca)

- No open data feed or public API found for job postings (the only Données Québec dataset in
  this space is Ville de Montréal's own internal hiring postings as an employer — irrelevant
  here).
- The site is an Oracle APEX single-page application (URLs like
  `quebecemploi.gouv.qc.ca/apex/f?p=...`) — content is rendered client-side by JavaScript.
  A plain HTTP fetch returns an empty shell; getting postings out would require a full headless
  browser, which is a materially heavier automation footprint than a simple HTML fetch.
- I could not load the Terms of Use page's actual text (fetch tooling only got the page shell),
  so its stance on automated access is **unconfirmed**, not "permitted." Combined with the
  SPA/headless-browser requirement, this is not something to build against without a clearer
  green light.

## Registraire des entreprises du Québec (REQ) — real data, but a licensing catch

- The REQ **does** publish a genuine bulk open-data extract via Données Québec — dataset
  "Registre des entreprises," a 225MB ZIP, updated twice a month, with a real user guide
  (fetched and read directly).
- Confirmed fields per company (`Entreprise` file): NEQ (business number), incorporation date,
  legal form, immatriculation status, **`COD_INTVAL_EMPLO_QUE` — an order-of-magnitude
  employee-count bucket for Quebec**, and **`COD_ACT_ECON_CAE` / `DESC_ACT_ECON_ASSUJ`** — the
  Registraire's own economic-activity classification (CAE) and its text description, for up to
  two declared activities. A companion `Établissement` file gives **per-location addresses**
  and per-location activity codes — good raw material for geo-bucketing and sector labeling of
  *any* Quebec company, hiring or not.
- **Personal/director/shareholder names are explicitly excluded from the bulk file**: "Les
  renseignements plus personnels permettant de reconnaître des personnes, tels que les noms,
  prénoms et adresses des personnes physiques, sont absents." Quebec law does require companies
  to publicly disclose administrators and the top-3 shareholders, but that only surfaces on the
  **live, one-company-at-a-time lookup** on registreentreprises.gouv.qc.ca — not in bulk. That's
  an enrichment-phase concern (Phase B), not a blocker for Phase A.
- **The license is the real problem for this project: CC BY‑NC‑SA 4.0 — non‑commercial use
  only**, share-alike, attribution required. Building a cold-call sales lead list is a
  commercial use. Using this dataset as the backbone of the lead-gen pipeline as originally
  scoped would run against the license terms as written. This needs your explicit decision,
  not a default technical workaround — see below.
- The CAE code system is **Quebec's own classification, not standard NAICS** — the
  `naics_exclude.yaml` built in this phase uses standard 4-digit NAICS codes (matches Job Bank's
  NAICS field) with a documented note that a CAE→NAICS-style crosswalk is a separate task if REQ
  data ends up in scope.

## What this means for the project

The original plan assumed at least one of {Job Bank, Emploi Québec} would be a politely
automatable source of company-identified leads. None of the three sources checked clears that
bar today:

| Source | Has company name? | Automatable? | Blocker |
|---|---|---|---|
| Job Bank open dataset | No | Yes (it's open data) | No employer field — not usable for leads, only sector/region signal |
| Job Bank live site | Yes | **No** | Terms of Use explicitly ban all automated/AI access |
| Emploi Québec | Unconfirmed | Unclear | JS-rendered SPA + unconfirmed ToS |
| REQ open dataset | Yes | Yes (it's open data) | **Non-commercial license** conflicts with a sales-lead use case |

Two real paths forward, neither implemented yet — this needs your call:

1. **Manual-import model (what Phase A actually builds, see below).** You browse Job Bank /
   Emploi Québec / Indeed yourself (or ask me to look at one specific search or page at a
   time — that's normal human/assisted browsing, not the automated crawling the Terms of Use
   forbid), and hand the pipeline a short list of company name + city + job title + vacancy
   count. The pipeline does the filtering/geo-bucketing/categorization/dedupe from there. Slower
   to fill the pipeline, but nothing here is a ToS or licensing violation.
2. **Get the REQ non-commercial question resolved** — e.g. contact
   `groupe.pilotage@req.gouv.qc.ca` (the REQ open-data support address) and ask directly whether
   this specific use is compatible with the license, or under what terms a commercial use is
   possible. If they say it's fine, REQ's per-establishment address + CAE + employee-count-bucket
   data would actually make a *very* strong direct-prospecting source on its own (find Quebec
   companies of the right size/sector/region, hiring or not — arguably a better fit for staffing
   sales than "waiting for a job posting" anyway) — but I'm not making that license call for you.

Nothing in Phase A below depends on resolving this — the filters/geo-table/categorization are
useful regardless of which sourcing path you pick later.

## Addendum (Phase B) — REQ's live per-company search tool, and the final sourcing model

The project's actual sourcing model ended up being: a live AI agent searches the general open
web + company websites (never the banned job-board sites directly) to find candidates, then
`python -m leadgen ingest` runs the deterministic filter/geo/dedupe/Sheet-delivery stages. See
`docs/ROUTINE_PROMPT.md` for the exact routine prompt. This addendum covers the one piece of
that model not checked in the original Step 0 pass: whether REQ's live, one-company-at-a-time
search tool (as opposed to its bulk open-data extract, covered above) can be queried by an
agent at all.

- **`registreentreprises.gouv.qc.ca/robots.txt` explicitly allows the anonymous search path**:
  `Disallow: /` for everything, with a specific carve-out `Allow: /RQAnonymeGR/GR/` — which is
  exactly the anonymous company-search tool. This is a meaningfully different, more permissive
  signal than Job Bank's blanket AI ban.
- No Terms-of-Use text banning automated/AI access to that tool was found — but this is
  **not a confirmed green light either**: attempting to fetch the site's own homepage directly
  returned an HTTP 403 (likely edge/bot-detection on the general site, separate from the
  specifically-allowed search path — not necessarily evidence of a Job-Bank-style policy ban,
  but not proof of the opposite either).
- **Practical guidance baked into `docs/ROUTINE_PROMPT.md`**: treat this as allowed for one
  polite, single-company lookup at a time (matching the robots.txt-permitted path and low,
  human-like volume), and if it ever errors, 403s, or shows a CAPTCHA, don't retry or work
  around it — just fall through to the next enrichment tier (company site) for that company.
  This is a live per-lead lookup, not the bulk extract — so the bulk file's CC BY-NC-SA
  non-commercial license restriction (above) doesn't apply here.
