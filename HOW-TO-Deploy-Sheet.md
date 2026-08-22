# How to deploy the Sheet (one-time, ~3 minutes)

`Code.gs` is the Sheet-delivery half of this project. It creates and owns a Google Sheet, and
exposes a `doPost` endpoint that `python -m leadgen ingest ...` (or a live-search cloud routine)
POSTs new leads to. Once deployed, every future run is a plain HTTPS POST — no browser step,
no Google OAuth on the Python/CLI side.

## Steps

1. Go to **script.google.com** → **New project**.
2. Paste the entire contents of `Code.gs` in, replacing the default `Code.gs` boilerplate.
   No other files are needed — unlike `request-tracker`, there's no `Form.html`; this project
   has no human-facing intake page, only the JSON ingestion endpoint.
3. Run the function **`setup`** from the toolbar dropdown (next to the Run/Debug icons). The
   first run will prompt you to authorize the script (it needs to create a Spreadsheet and
   install a daily trigger) — approve it.
4. Open **View → Logs** (or **Executions**) to find the printed Spreadsheet URL. Open it and
   bookmark it — this is where your leads will land.
5. **Deploy → New deployment**:
   - Type: **Web app**
   - Execute as: **Me**
   - Who has access: **Anyone within TELUS** if you're fine with it only being reachable while
     authenticated on the TELUS network/account, or **Anyone** if you want it reachable from
     anywhere (e.g. a cloud routine running outside TELUS's network, or a personal Google
     account). Pick **Anyone** if you're not sure — the URL itself is the only thing anyone
     needs to hit the endpoint, so keep it out of anywhere public either way.
6. Copy the **Web app URL** it gives you (ends in `/exec`).
7. Put it in this project's `.env` file (copy `.env.example` to `.env` first if you haven't):
   ```
   SHEET_WEBAPP_URL=https://script.google.com/macros/s/XXXXXXXXXXXX/exec
   ```

## Test it

```
python -m leadgen ingest data/sample_postings.csv --skip-sheet   # (CSV-only dry run first)
```

Then try a real POST with a tiny hand-made JSON file (see `docs/ROUTINE_PROMPT.md` for the
exact shape `ingest` expects), or just:

```
python -m leadgen ingest path/to/some_leads.json
```

You should see `Posted N new lead(s) to the Sheet: {...}` and the rows should appear in the
**Leads** tab within a few seconds. The **Grand Montreal** / **Other** tabs update automatically
(they're live `FILTER()` formulas over Leads, not separate copies), and **Dashboard** recalculates
on its own since it's all formulas too.

## Re-deploying after you edit Code.gs

**Deploy → Manage deployments → edit (pencil icon) → New version → Deploy.** This keeps the
same URL, so you don't need to update `.env` again. Re-running `setup()` is safe any time —
it won't duplicate the Spreadsheet (the ID is remembered via `PropertiesService`) or clear
existing tabs it finds already there.

## If something looks wrong

- **Rows aren't appearing**: check `SHEET_WEBAPP_URL` is the `/exec` URL (not `/dev`), and that
  the deployment's "Execute as" is **Me**, not "User accessing the web app".
- **A lead looks duplicated**: the dedupe key is in the hidden `Dedupe Key` column (right-click
  a column header → "Unhide columns" if you need to inspect it). `python -m leadgen ingest`
  also keeps its own local dedupe state in `state/pipeline.db` — if you want to force a company
  back in as "new," you'd need to remove it from both places, which usually means you actually
  want a fresh `posting_id`/week instead of fighting the dedupe key.
- **Lead Score never changes for old rows**: `refreshLeadScores` runs once daily at 6am (script
  timezone). Run it manually from the Apps Script editor if you want to see it recompute sooner.
