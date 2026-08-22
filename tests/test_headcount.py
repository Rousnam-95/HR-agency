import pytest

from leadgen.filters.headcount import headcount_bucket


@pytest.mark.parametrize("n,expected", [
    (None, "Unspecified"),
    ("", "Unspecified"),
    ("not a number", "Unspecified"),
    (0, "Unspecified"),
    (-1, "Unspecified"),
    (1, "1-4"),
    (4, "1-4"),
    (5, "5-9"),
    (9, "5-9"),
    (10, "10-24"),
    (24, "10-24"),
    (25, "25+"),
    (500, "25+"),
])
def test_headcount_bucket(n, expected):
    assert headcount_bucket(n) == expected
