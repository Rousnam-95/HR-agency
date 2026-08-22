"""python -m leadgen run --input path/to/postings.csv
python -m leadgen init-template --output path/to/postings.csv
python -m leadgen ingest path/to/raw_leads.json
"""
import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

from leadgen.config import get_webapp_url
from leadgen.enrich.schema import Contact
from leadgen.filters.geo_bucket import GeoBucketer
from leadgen.filters.headcount import headcount_bucket
from leadgen.filters.sector_exclude import SectorExcluder
from leadgen.sheet.webapp_client import WebAppError, post_batch
from leadgen.sources.manual_import import load_postings, write_template
from leadgen.state.dedupe_store import DedupeStore, build_dedupe_key

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LEAD_COLUMNS = ["company_name", "job_title", "municipality", "region_bucket", "distance_km",
                "headcount_bucket", "vacancy_count_raw", "naics_code", "source", "posting_url", "notes"]
EXCLUDED_COLUMNS = ["company_name", "job_title", "municipality", "exclusion_method", "exclusion_reason"]
DROPPED_COLUMNS = ["company_name", "job_title", "municipality", "drop_reason"]
INGEST_LEAD_COLUMNS = ["company_name", "job_title", "municipality", "region_bucket", "distance_km",
                        "headcount_bucket", "vacancy_count_raw", "naics_code", "source", "posting_id",
                        "posting_url", "contact_name", "contact_title", "contact_email", "contact_phone",
                        "contact_source_tier", "contact_confidence", "times_seen", "dedupe_key", "notes"]


def run(input_csv: Path, output_dir: Path) -> None:
    excluder = SectorExcluder()
    geo = GeoBucketer()

    leads, excluded, dropped = [], [], []
    for posting in load_postings(input_csv):
        company = posting["company_name"].strip()
        title = posting["job_title"].strip()
        muni = posting["municipality"].strip()

        sector_result = excluder.evaluate(company_name=company, job_title=title, naics_code=posting["naics_code"])
        if sector_result.excluded:
            excluded.append({
                "company_name": company, "job_title": title, "municipality": muni,
                "exclusion_method": sector_result.method, "exclusion_reason": sector_result.reason,
            })
            continue

        geo_result = geo.lookup(muni)
        if not geo_result.matched or not geo_result.in_radius:
            dropped.append({
                "company_name": company, "job_title": title, "municipality": muni,
                "drop_reason": geo_result.drop_reason,
            })
            continue

        leads.append({
            "company_name": company,
            "job_title": title,
            "municipality": muni,
            "region_bucket": geo_result.region_bucket,
            "distance_km": geo_result.distance_km,
            "headcount_bucket": headcount_bucket(posting["vacancy_count"] or None),
            "vacancy_count_raw": posting["vacancy_count"],
            "naics_code": posting["naics_code"],
            "source": posting["source"],
            "posting_url": posting["posting_url"],
            "notes": posting["notes"],
        })

    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = date.today().isoformat()
    _write_csv(output_dir / f"leads_{stamp}.csv", LEAD_COLUMNS, leads)
    _write_csv(output_dir / f"excluded_{stamp}.csv", EXCLUDED_COLUMNS, excluded)
    _write_csv(output_dir / f"dropped_out_of_radius_{stamp}.csv", DROPPED_COLUMNS, dropped)

    print(f"Leads: {len(leads)} | Excluded (sector): {len(excluded)} | Dropped (geo): {len(dropped)}")
    print(f"Written to {output_dir}")


def ingest(input_json: Path, output_dir: Path, skip_sheet: bool = False) -> None:
    """Filter/geo-bucket/categorize/dedupe a JSON batch of leads gathered by a live search+
    enrichment run (see docs/ROUTINE_PROMPT.md), then push genuinely new ones to the Sheet.

    Reuses the exact same SectorExcluder/GeoBucketer/headcount_bucket as `run` -- the
    deterministic rules don't change just because the leads came from a live agent instead
    of a hand-filled CSV.
    """
    with open(input_json, encoding="utf-8") as f:
        raw_leads = json.load(f)
    if not isinstance(raw_leads, list):
        raise ValueError(f"{input_json} must contain a JSON list of lead records")

    excluder = SectorExcluder()
    geo = GeoBucketer()

    new_leads, reseen, excluded, dropped, contact_warnings = [], [], [], [], []

    with DedupeStore() as store:
        for raw in raw_leads:
            company = (raw.get("company_name") or "").strip()
            title = (raw.get("job_title") or "").strip()
            muni = (raw.get("municipality") or "").strip()
            naics = (raw.get("naics_code") or "").strip()

            sector_result = excluder.evaluate(company_name=company, job_title=title, naics_code=naics)
            if sector_result.excluded:
                excluded.append({
                    "company_name": company, "job_title": title, "municipality": muni,
                    "exclusion_method": sector_result.method, "exclusion_reason": sector_result.reason,
                })
                continue

            geo_result = geo.lookup(muni)
            if not geo_result.matched or not geo_result.in_radius:
                dropped.append({
                    "company_name": company, "job_title": title, "municipality": muni,
                    "drop_reason": geo_result.drop_reason,
                })
                continue

            contact = Contact.from_raw(raw)
            errors = contact.validate()
            if errors:
                contact_warnings.append(f"{company}: {'; '.join(errors)}")

            dedupe_key = build_dedupe_key(
                source=raw.get("source", ""), posting_id=raw.get("posting_id", ""),
                company_name=company, city=muni, job_title=title,
            )
            dedupe_result = store.check_and_record(dedupe_key, company)

            lead = {
                "company_name": company, "job_title": title, "municipality": muni,
                "region_bucket": geo_result.region_bucket, "distance_km": geo_result.distance_km,
                "headcount_bucket": headcount_bucket(raw.get("vacancy_count")),
                "vacancy_count_raw": raw.get("vacancy_count", ""),
                "naics_code": naics, "source": raw.get("source", ""),
                "posting_id": raw.get("posting_id", ""), "posting_url": raw.get("posting_url", ""),
                "contact_name": contact.name, "contact_title": contact.title,
                "contact_email": contact.email, "contact_phone": contact.phone,
                "contact_source_tier": contact.source_tier, "contact_confidence": contact.confidence,
                "dedupe_key": dedupe_key, "notes": raw.get("notes", ""),
            }

            if dedupe_result.is_new:
                lead["times_seen"] = 1
                new_leads.append(lead)
            else:
                lead["times_seen"] = dedupe_result.times_seen
                reseen.append(lead)

    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = date.today().isoformat()
    _write_csv(output_dir / f"ingest_new_{stamp}.csv", INGEST_LEAD_COLUMNS, new_leads)
    _write_csv(output_dir / f"ingest_excluded_{stamp}.csv", EXCLUDED_COLUMNS, excluded)
    _write_csv(output_dir / f"ingest_dropped_{stamp}.csv", DROPPED_COLUMNS, dropped)

    print(f"New leads: {len(new_leads)} | Already-seen (skipped): {len(reseen)} | "
          f"Excluded (sector): {len(excluded)} | Dropped (geo): {len(dropped)}")
    for w in contact_warnings:
        print(f"  contact warning: {w}")
    print(f"Written to {output_dir}")

    if not new_leads:
        print("Nothing new to send to the Sheet.")
        return
    if skip_sheet:
        print("Sheet POST skipped (--skip-sheet).")
        return

    webapp_url = get_webapp_url()
    if not webapp_url:
        print("SHEET_WEBAPP_URL is not set in .env -- deploy Code.gs first "
              "(see HOW-TO-Deploy-Sheet.md) to push these leads to the Sheet.")
        return

    try:
        result = post_batch(webapp_url, new_leads, excluded=excluded, dropped=dropped)
        print(f"Posted {len(new_leads)} new lead(s) to the Sheet: {result}")
    except WebAppError as e:
        print(f"Sheet POST failed (leads are safe in {output_dir}, nothing lost): {e}")


def _write_csv(path: Path, columns, rows) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(prog="leadgen")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Filter/geo-bucket/categorize a manually-collected postings CSV")
    run_p.add_argument("--input", type=Path, required=True)
    run_p.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "output")

    tmpl_p = sub.add_parser("init-template", help="Write a blank postings CSV template")
    tmpl_p.add_argument("--output", type=Path, required=True)

    ingest_p = sub.add_parser(
        "ingest",
        help="Filter/geo-bucket/categorize/dedupe a JSON batch of leads (from a live search+"
             "enrichment run) and push new ones to the Sheet",
    )
    ingest_p.add_argument("input_json", type=Path)
    ingest_p.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "output")
    ingest_p.add_argument("--skip-sheet", action="store_true",
                           help="Write CSVs only, don't POST to the Sheet web app")

    args = parser.parse_args()
    if args.command == "run":
        run(args.input, args.output_dir)
    elif args.command == "init-template":
        write_template(args.output)
        print(f"Template written to {args.output}")
    elif args.command == "ingest":
        ingest(args.input_json, args.output_dir, args.skip_sheet)


if __name__ == "__main__":
    sys.exit(main())
