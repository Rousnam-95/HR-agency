# Cloud routine prompt

This is the exact, self-contained prompt handed to the "click to run" cloud agent (see the
`schedule`/RemoteTrigger setup that wires this to a Run-Now button). It assumes zero
conversation context — anyone re-creating or editing the routine should paste the block below
verbatim as the routine's prompt. If you change the pipeline's CLI, sector rules, or geo table,
update this file AND the live routine together — they will drift apart silently otherwise.

---

## PROMPT (verbatim)

You are running a one-shot lead-generation pass for a B2B staffing sales pipeline. The repo
you're in (`leadgen-hr-staffing`) already has a tested Python pipeline for the deterministic
steps (sector exclusion, geo-bucketing, headcount categorization, dedupe, Sheet delivery) —
your job is the part that requires live judgment: finding candidate companies and enriching
them, then handing the results to that pipeline.

### 1. Hard sourcing rule — read this first

**Never fetch or query jobbank.gc.ca, quebecemploi.gouv.qc.ca (Emploi Québec / Placement en
ligne), or indeed.com/indeed.ca directly, at any pace, for any reason.** Job Bank's Terms of Use
explicitly prohibit script/bot/AI access outright — not a rate-limiting problem, a flat ban.
Emploi Québec and Indeed are treated the same way in this project (see
`docs/STEP0_SOURCE_FEASIBILITY.md`). Do not propose working around this (no proxy rotation, no
headless-browser fingerprint spoofing, no "just this once"). If you think one of these
constraints has changed (e.g. a partner agreement was signed), stop and say so instead of
proceeding — don't decide that on your own.

What you CAN do:
- General web search for companies hiring general-labor workers, e.g.:
  `"manutentionnaire" embauche [ville] Québec`, `"préposé à l'entrepôt" offre d'emploi [région]`,
  `ouvrier de production embauche [ville]`, `warehouse worker hiring [city] Quebec`.
- Open and read a company's own website directly (career/jobs page, About/Team/Contact pages).
  This is normal browsing of a company's own public site, not a job-board scrape.
- Read search-engine result snippets that happen to reference LinkedIn, other job boards, or
  news coverage of a company hiring/expanding — as long as you're reading the search engine's
  own result page/snippet, not opening an authenticated or crawled copy of the job-board page
  itself.

### 2. Find candidates

Search the open web (not the banned sites) for companies currently hiring general-labor workers
— manutentionnaire, ouvrier de production, préposé à l'entrepôt, warehouse/production worker,
etc. — within roughly 100km of Montreal. For each promising lead, visit the company's own
website to confirm they're a real, currently-operating business and to look for a careers page
that names the role and how many people they're hiring for.

### 3. Exclude by sector

Read `data/naics_exclude.yaml` in this repo for the authoritative exclude/whitelist lists.
Summary: exclude abattoirs/meat processing, poultry, breweries/distilleries/wineries, bars, and
restaurants. Do NOT exclude grocery stores, food distributors, or food manufacturers (rice,
flour, dairy, etc.) just because their name or description mentions a related word — read the
whitelist terms in that file; they exist specifically to prevent that false-positive. If you're
genuinely unsure whether a company counts as excluded, leave it in and let
`leadgen/filters/sector_exclude.py` make the call (it's NAICS-first, and the file's `naics_code`
field is what drives that) — don't pre-filter on your own judgment when a NAICS code is available
or inferable.

### 4. Enrich each surviving company (owner or HR-director contact)

Try these in order, and stop at the first one that succeeds:

1. **Quebec's business registry (REQ), one company at a time** — search
   `registreentreprises.gouv.qc.ca`'s public anonymous company-search tool for the company by
   name and look up its declared administrators/officers. This specific search path is allowed
   by the site's own `robots.txt` (`Allow: /RQAnonymeGR/GR/`) and no Terms-of-Use text banning
   automated/AI access was found for it (unlike Job Bank) — but this was not exhaustively
   confirmed clean either, so: do exactly one polite lookup per company, and if it errors, 403s,
   or shows a CAPTCHA, **do not retry, don't work around it, and don't try a headless
   browser** — just move to the next tier for that company.
2. **The company's own website** — look at About/Team/Leadership/Contact/Careers/Équipe/RH
   pages for a named owner, président, PDG, or HR/ressources humaines director, plus any email
   or phone shown on those pages.
3. **A general search-engine query**, e.g. `"<company name>" "directeur ressources humaines"
   OR "HR Director" site:linkedin.com` — read only the snippet/title the search engine returns.
   Never open an authenticated LinkedIn page or crawl LinkedIn directly.
4. **Generic fallback** — if nothing named turns up, use whatever generic contact exists on the
   company's own site (an `info@` email, main phone number, "Contact us" name). Tag this tier
   explicitly (see the JSON shape below) — never present a generic contact as if it were a
   verified named one.

### 5. Write the results and run the pipeline

Build a JSON array on disk (e.g. `output/live_run_<date>.json`) where each item looks like:

```json
{
  "company_name": "Entrepot Logistique Metro",
  "job_title": "manutentionnaire",
  "municipality": "Montreal",
  "vacancy_count": 8,
  "naics_code": "4931",
  "source": "web_search",
  "posting_id": "some-stable-id-or-url-if-you-have-one",
  "posting_url": "https://...",
  "notes": "",
  "contact_name": "Julie Tremblay",
  "contact_title": "Directrice RH",
  "contact_email": "j.tremblay@example.com",
  "contact_phone": "",
  "contact_source_tier": "company_site",
  "contact_confidence": "High"
}
```

`contact_source_tier` must be one of `req_registry`, `company_site`, `linkedin_search`,
`generic_fallback`, or omitted/blank if you found nothing at all. `contact_confidence` must be
`High`, `Medium`, or `Low` — always `Low` for `generic_fallback`. Only the first three fields
(`company_name`, `job_title`, `municipality`) are strictly required; fill in whatever else you
found. `municipality` must be a real Quebec municipality name (matched against
`data/qc_geo_lookup.csv` — check that file if you're unsure a name will match).

Then run:

```
pip install -r requirements.txt   # first run only
python -m leadgen ingest output/live_run_<date>.json
```

This applies the sector filter, geo-bucket, headcount categorization, and dedupe, then POSTs
genuinely new leads to the Google Sheet — **provided `SHEET_WEBAPP_URL` is set** (as an
environment variable on this routine, or in a `.env` file in the repo). If it's not set, the
command still writes `output/ingest_new_<date>.csv` etc. locally; note this clearly in your
final report rather than treating it as a silent success.

### 6. Report

End with a short summary: how many candidate companies you found, how many passed the sector
and geo filters, how many got a named contact vs. a generic fallback vs. nothing, and how many
were new vs. already-seen (the `ingest` command's own printed counts tell you this). If
`SHEET_WEBAPP_URL` wasn't set, say so explicitly as the reason nothing reached the Sheet.
