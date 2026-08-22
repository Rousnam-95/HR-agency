import csv
from pathlib import Path

from leadgen.filters.sector_exclude import SectorExcluder

FIXTURE = Path(__file__).parent / "fixtures" / "sector_labels.csv"


def _load_cases():
    with open(FIXTURE, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_sector_exclude_fixture():
    excluder = SectorExcluder()
    cases = _load_cases()
    assert cases, "fixture must not be empty"

    failures = []
    for row in cases:
        expected = row["expected_excluded"] == "True"
        result = excluder.evaluate(
            company_name=row["company_name"],
            job_title=row["job_title"],
            naics_code=row["naics_code"],
        )
        if result.excluded != expected:
            failures.append(
                f"{row['case_type']} ({row['company_name']!r}): expected excluded={expected}, "
                f"got excluded={result.excluded} (method={result.method}, reason={result.reason})"
            )

    assert not failures, "Sector filter mismatches:\n" + "\n".join(failures)


def test_never_exclude_wins_over_keyword_match():
    excluder = SectorExcluder()
    # "Boucherie" is a keyword-exclude term, but "Marché" is a whitelist term -- whitelist must win.
    result = excluder.evaluate(company_name="Marché Boucherie Fine du Plateau", job_title="commis")
    assert result.excluded is False


def test_naics_takes_precedence_and_reports_method():
    excluder = SectorExcluder()
    result = excluder.evaluate(company_name="Anything Inc", job_title="worker", naics_code="3116")
    assert result.excluded is True
    assert result.method == "naics"


def test_no_false_positive_on_unrelated_manufacturer():
    excluder = SectorExcluder()
    result = excluder.evaluate(company_name="Manufacturier de Meubles ABC", job_title="manutentionnaire", naics_code="3371")
    assert result.excluded is False
