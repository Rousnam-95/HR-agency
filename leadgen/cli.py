"""python -m leadgen run --input path/to/postings.csv
python -m leadgen init-template --output path/to/postings.csv
"""
import argparse
import csv
import sys
from datetime import date
from pathlib import Path

from leadgen.filters.geo_bucket import GeoBucketer
from leadgen.filters.headcount import headcount_bucket
from leadgen.filters.sector_exclude import SectorExcluder
from leadgen.sources.manual_import import load_postings, write_template

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LEAD_COLUMNS = ["company_name", "job_title", "municipality", "region_bucket", "distance_km",
                "headcount_bucket", "vacancy_count_raw", "naics_code", "source", "posting_url", "notes"]
EXCLUDED_COLUMNS = ["company_name", "job_title", "municipality", "exclusion_method", "exclusion_reason"]
DROPPED_COLUMNS = ["company_name", "job_title", "municipality", "drop_reason"]


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

    args = parser.parse_args()
    if args.command == "run":
        run(args.input, args.output_dir)
    elif args.command == "init-template":
        write_template(args.output)
        print(f"Template written to {args.output}")


if __name__ == "__main__":
    sys.exit(main())
