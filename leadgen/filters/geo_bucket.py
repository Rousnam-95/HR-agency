"""Join a posting's municipality name against data/qc_geo_lookup.csv to get its region bucket.

Anything not found in the lookup table, or found but beyond 100km, is dropped -- never
silently defaulted into a bucket. See scripts/build_geo_lookup.py for how the table is built
and its known coverage gaps.
"""
import csv
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_DEFAULT_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "qc_geo_lookup.csv"


def _normalize(text: str) -> str:
    text = text.lower().strip()
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


@dataclass
class GeoResult:
    matched: bool
    in_radius: bool = False
    region_bucket: Optional[str] = None
    distance_km: Optional[float] = None
    drop_reason: Optional[str] = None


class GeoBucketer:
    def __init__(self, lookup_path: Path = _DEFAULT_PATH):
        self._by_name = {}
        with open(lookup_path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                self._by_name[_normalize(row["municipality"])] = row

    def lookup(self, municipality: str) -> GeoResult:
        row = self._by_name.get(_normalize(municipality))
        if row is None:
            return GeoResult(matched=False, drop_reason=f"municipality '{municipality}' not in lookup table")
        in_radius = row["in_100km_radius"] == "True"
        if not in_radius:
            return GeoResult(matched=True, in_radius=False,
                              distance_km=float(row["distance_km_from_mtl"]),
                              drop_reason=f"{municipality} is {row['distance_km_from_mtl']}km from Montreal, beyond 100km")
        return GeoResult(matched=True, in_radius=True,
                          region_bucket=row["region_bucket"],
                          distance_km=float(row["distance_km_from_mtl"]))
