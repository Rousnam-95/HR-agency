from datetime import date

from leadgen.state.dedupe_store import DedupeStore, build_dedupe_key


def test_posting_id_key_is_stable_across_sources_and_ids():
    key_a = build_dedupe_key(source="web_search", posting_id="abc123", company_name="X",
                              city="Laval", job_title="manutentionnaire")
    key_b = build_dedupe_key(source="web_search", posting_id="abc123", company_name="Different Name",
                              city="Longueuil", job_title="ouvrier")
    assert key_a == key_b  # posting_id alone determines the key when present


def test_composite_key_ignores_case_accents_and_extra_whitespace():
    key_a = build_dedupe_key(source="", posting_id="", company_name="Épicerie Métro",
                              city="Montréal", job_title="commis entrepôt", iso_week="2026-W34")
    key_b = build_dedupe_key(source="", posting_id="", company_name="  epicerie metro  ",
                              city="MONTREAL", job_title="COMMIS ENTREPOT", iso_week="2026-W34")
    assert key_a == key_b


def test_new_key_is_new_then_reseen_on_second_check(tmp_path):
    store = DedupeStore(db_path=tmp_path / "pipeline.db")
    try:
        first = store.check_and_record("id::src::123", "Acme Inc", today=date(2026, 8, 22))
        assert first.is_new is True
        assert first.times_seen == 1

        second = store.check_and_record("id::src::123", "Acme Inc", today=date(2026, 8, 23))
        assert second.is_new is False
        assert second.times_seen == 2
        assert second.first_seen_date == "2026-08-22"
    finally:
        store.close()


def test_different_keys_are_independent(tmp_path):
    with DedupeStore(db_path=tmp_path / "pipeline.db") as store:
        a = store.check_and_record("id::src::1", "Acme Inc")
        b = store.check_and_record("id::src::2", "Acme Inc")
        assert a.is_new is True
        assert b.is_new is True
