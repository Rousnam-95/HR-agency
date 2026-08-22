"""Bucket a posting's vacancy count into headcount categories.

Never guesses: a missing/blank vacancy count is bucketed as "Unspecified" rather than
defaulted to 1, so downstream lead-scoring doesn't silently treat "we don't know" as "one".
"""
from typing import Optional

BUCKETS = ["1-4", "5-9", "10-24", "25+", "Unspecified"]


def headcount_bucket(vacancy_count: Optional[int]) -> str:
    if vacancy_count is None:
        return "Unspecified"
    try:
        n = int(vacancy_count)
    except (TypeError, ValueError):
        return "Unspecified"
    if n <= 0:
        return "Unspecified"
    if n <= 4:
        return "1-4"
    if n <= 9:
        return "5-9"
    if n <= 24:
        return "10-24"
    return "25+"
