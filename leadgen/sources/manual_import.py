"""Reads a human-collected CSV of postings/companies.

This is the actual Phase A "source" -- see docs/STEP0_SOURCE_FEASIBILITY.md for why Job Bank
and Emploi Québec are not automated. You (or Claude, one page at a time, when you explicitly
ask) browse those sites or Indeed yourself and fill in a CSV with this shape; the pipeline
takes it from there (filter, geo-bucket, categorize, dedupe).
"""
import csv
from pathlib import Path
from typing import Iterator, TypedDict


class RawPosting(TypedDict):
    company_name: str
    job_title: str
    municipality: str
    vacancy_count: str
    naics_code: str
    source: str
    posting_url: str
    notes: str


REQUIRED_COLUMNS = ["company_name", "job_title", "municipality"]
ALL_COLUMNS = ["company_name", "job_title", "municipality", "vacancy_count", "naics_code",
               "source", "posting_url", "notes"]


def load_postings(csv_path: Path) -> Iterator[RawPosting]:
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{csv_path} is missing required columns: {missing}")
        for row in reader:
            yield {col: row.get(col, "") for col in ALL_COLUMNS}


def write_template(csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ALL_COLUMNS)
        writer.writeheader()
        writer.writerow({
            "company_name": "Exemple Manutention ABC Inc",
            "job_title": "manutentionnaire",
            "municipality": "Longueuil",
            "vacancy_count": "6",
            "naics_code": "4931",
            "source": "jobbank.gc.ca (manual browse)",
            "posting_url": "https://www.jobbank.gc.ca/jobsearch/jobposting/...",
            "notes": "",
        })
