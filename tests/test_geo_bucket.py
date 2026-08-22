from leadgen.filters.geo_bucket import GeoBucketer


def test_montreal_is_grand_montreal():
    r = GeoBucketer().lookup("Montreal")
    assert r.matched and r.in_radius
    assert r.region_bucket == "Grand Montreal"


def test_accent_insensitive_match():
    r = GeoBucketer().lookup("Repentigny")
    assert r.matched and r.region_bucket == "Grand Montreal"
    r2 = GeoBucketer().lookup("répentigny")
    assert r2.matched and r2.region_bucket == "Grand Montreal"


def test_other_bucket_within_100km():
    r = GeoBucketer().lookup("Saint-Hyacinthe")
    assert r.matched and r.in_radius
    assert r.region_bucket == "Other"


def test_unknown_municipality_is_dropped_not_guessed():
    r = GeoBucketer().lookup("Ville Imaginaire Qui N'existe Pas")
    assert r.matched is False
    assert r.drop_reason is not None
