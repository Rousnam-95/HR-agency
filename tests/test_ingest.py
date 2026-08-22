import json
from unittest.mock import patch

from leadgen.cli import ingest

RAW_LEADS = [
    {  # clean keep, named contact -> should be posted
        "company_name": "Entrepot General Logistique", "job_title": "manutentionnaire",
        "municipality": "Laval", "vacancy_count": 6, "naics_code": "4931",
        "source": "web_search", "posting_id": "ws-1", "posting_url": "https://example.com/1",
        "contact_name": "Julie Tremblay", "contact_title": "Directrice RH",
        "contact_email": "j.tremblay@example.com", "contact_source_tier": "company_site",
        "contact_confidence": "High",
    },
    {  # sector-excluded
        "company_name": "Abattoir Richelieu Inc", "job_title": "manutentionnaire",
        "municipality": "Laval", "naics_code": "3116", "source": "web_search", "posting_id": "ws-2",
    },
    {  # out of radius / unmatched municipality
        "company_name": "Quelquechose Inc", "job_title": "ouvrier",
        "municipality": "Ville Introuvable Pas Reelle", "source": "web_search", "posting_id": "ws-3",
    },
]


def test_ingest_filters_excludes_and_posts_only_new_kept_leads(tmp_path):
    input_json = tmp_path / "raw.json"
    input_json.write_text(json.dumps(RAW_LEADS), encoding="utf-8")

    with patch("leadgen.cli.DedupeStore") as mock_store_cls, \
         patch("leadgen.cli.get_webapp_url", return_value="https://script.google.com/fake/exec"), \
         patch("leadgen.cli.post_batch") as mock_post:
        # Fresh in-memory-like store behavior: every key is new.
        instance = mock_store_cls.return_value.__enter__.return_value
        instance.check_and_record.side_effect = lambda key, company, **kw: type(
            "R", (), {"is_new": True, "times_seen": 1, "first_seen_date": "2026-08-22"}
        )()

        ingest(input_json, tmp_path / "out", skip_sheet=False)

    mock_post.assert_called_once()
    posted_leads = mock_post.call_args[0][1]
    assert len(posted_leads) == 1
    assert posted_leads[0]["company_name"] == "Entrepot General Logistique"
    assert posted_leads[0]["contact_source_tier"] == "company_site"

    out_files = {p.name for p in (tmp_path / "out").iterdir()}
    assert any(name.startswith("ingest_new_") for name in out_files)
    assert any(name.startswith("ingest_excluded_") for name in out_files)
    assert any(name.startswith("ingest_dropped_") for name in out_files)


def test_ingest_skip_sheet_never_calls_post(tmp_path):
    input_json = tmp_path / "raw.json"
    input_json.write_text(json.dumps(RAW_LEADS[:1]), encoding="utf-8")

    with patch("leadgen.cli.post_batch") as mock_post:
        ingest(input_json, tmp_path / "out", skip_sheet=True)

    mock_post.assert_not_called()
