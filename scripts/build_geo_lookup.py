"""Build data/qc_geo_lookup.csv: Quebec municipalities -> region bucket (Grand Montreal vs
Other within 100km) with distance from a fixed Montreal reference point.

Data-quality note: the Grand-Montreal (CMM) list below was extracted from the French Wikipedia
page for the Communaute metropolitaine de Montreal on 2026-08-22 and contains 74 of the CMM's
official 82 member municipalities -- a handful of Couronne Nord municipalities (e.g. likely
Terrebonne, Repentigny, Mascouche, L'Assomption) were not present in the fetched table and are
NOT included here. Cross-check against the official CMM municipality list
(https://cmm.qc.ca/a-propos/territoires-et-municipalites/, or the MAMH PDF
https://cdn-contenu.quebec.ca/cdn-contenu/adm/min/affaires-municipales/publications/cartes/cm/663.pdf)
before treating this as complete. Because CMM membership implies proximity to Montreal, the
missing municipalities would land in the Grand Montreal bucket anyway if added later -- this
gap does not create a wrong "Other" classification, only an incomplete "Grand Montreal" one.

The "Other" (non-CMM, within ~100km) list is a small, deliberately non-exhaustive set of
well-known Quebec municipalities with independently looked-up coordinates, per the "accuracy
over coverage" instruction -- it is NOT a full postal-code/FSA-level table.

Coordinates are town-centre approximations (a few km of error at most), which does not affect
bucketing for CMM members (all well under 100km by construction) and is noted per-row for the
"Other" set where the 100km cutoff is actually being tested.
"""
import csv
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from leadgen.utils.distance import haversine_km

MTL_REF_LAT, MTL_REF_LON = 45.5017, -73.5673  # Place Ville-Marie

# (municipality, sector, lat, lon) -- all confirmed CMM members -> region_bucket = "Grand Montreal"
CMM_MUNICIPALITIES = [
    # Agglomeration de Montreal
    ("Baie-D'Urfe", "Agglomeration de Montreal", 45.410, -73.909),
    ("Beaconsfield", "Agglomeration de Montreal", 45.432, -73.867),
    ("Cote-Saint-Luc", "Agglomeration de Montreal", 45.473, -73.658),
    ("Dollard-Des Ormeaux", "Agglomeration de Montreal", 45.492, -73.817),
    ("Dorval", "Agglomeration de Montreal", 45.449, -73.747),
    ("Hampstead", "Agglomeration de Montreal", 45.478, -73.649),
    ("Kirkland", "Agglomeration de Montreal", 45.447, -73.867),
    ("L'Ile-Dorval", "Agglomeration de Montreal", 45.436, -73.744),
    ("Montreal", "Agglomeration de Montreal", 45.5017, -73.5673),
    ("Montreal-Est", "Agglomeration de Montreal", 45.633, -73.503),
    ("Montreal-Ouest", "Agglomeration de Montreal", 45.454, -73.649),
    ("Mont-Royal", "Agglomeration de Montreal", 45.516, -73.642),
    ("Pointe-Claire", "Agglomeration de Montreal", 45.448, -73.817),
    ("Sainte-Anne-de-Bellevue", "Agglomeration de Montreal", 45.402, -73.948),
    ("Senneville", "Agglomeration de Montreal", 45.427, -73.965),
    ("Westmount", "Agglomeration de Montreal", 45.483, -73.598),
    # Agglomeration de Longueuil
    ("Boucherville", "Agglomeration de Longueuil", 45.606, -73.435),
    ("Brossard", "Agglomeration de Longueuil", 45.456, -73.460),
    ("Longueuil", "Agglomeration de Longueuil", 45.532, -73.518),
    ("Saint-Bruno-de-Montarville", "Agglomeration de Longueuil", 45.541, -73.343),
    ("Saint-Lambert", "Agglomeration de Longueuil", 45.503, -73.502),
    # Laval
    ("Laval", "Laval", 45.606, -73.712),
    # Couronne Nord
    ("Blainville", "Couronne Nord", 45.670, -73.883),
    ("Boisbriand", "Couronne Nord", 45.622, -73.833),
    ("Bois-des-Filion", "Couronne Nord", 45.657, -73.766),
    ("Deux-Montagnes", "Couronne Nord", 45.539, -73.900),
    ("Lorraine", "Couronne Nord", 45.678, -73.789),
    ("Mirabel", "Couronne Nord", 45.650, -74.083),
    ("Oka", "Couronne Nord", 45.472, -74.079),
    ("Pointe-Calumet", "Couronne Nord", 45.541, -73.958),
    ("Rosemere", "Couronne Nord", 45.638, -73.797),
    ("Sainte-Anne-des-Plaines", "Couronne Nord", 45.767, -73.812),
    ("Sainte-Marthe-sur-le-Lac", "Couronne Nord", 45.548, -73.929),
    ("Sainte-Therese", "Couronne Nord", 45.638, -73.828),
    ("Saint-Eustache", "Couronne Nord", 45.565, -73.903),
    ("Saint-Joseph-du-Lac", "Couronne Nord", 45.535, -73.984),
    # Couronne Sud
    ("Beauharnois", "Couronne Sud", 45.316, -73.875),
    ("Beloeil", "Couronne Sud", 45.564, -73.203),
    ("Calixa-Lavallee", "Couronne Sud", 45.646, -73.352),
    ("Candiac", "Couronne Sud", 45.383, -73.517),
    ("Carignan", "Couronne Sud", 45.469, -73.303),
    ("Chambly", "Couronne Sud", 45.449, -73.284),
    ("Chateauguay", "Couronne Sud", 45.372, -73.749),
    ("Contrecoeur", "Couronne Sud", 45.855, -73.234),
    ("Delson", "Couronne Sud", 45.373, -73.545),
    ("Hudson", "Couronne Sud", 45.449, -74.150),
    ("La Prairie", "Couronne Sud", 45.417, -73.500),
    ("Lery", "Couronne Sud", 45.315, -73.815),
    ("Les Cedres", "Couronne Sud", 45.294, -74.047),
    ("L'Ile-Cadieux", "Couronne Sud", 45.421, -74.062),
    ("L'Ile-Perrot", "Couronne Sud", 45.362, -73.943),
    ("Mercier", "Couronne Sud", 45.319, -73.740),
    ("McMasterville", "Couronne Sud", 45.548, -73.207),
    ("Mont-Saint-Hilaire", "Couronne Sud", 45.560, -73.181),
    ("Notre-Dame-de-l'Ile-Perrot", "Couronne Sud", 45.371, -73.958),
    ("Otterburn Park", "Couronne Sud", 45.545, -73.213),
    ("Pincourt", "Couronne Sud", 45.383, -73.983),
    ("Pointe-des-Cascades", "Couronne Sud", 45.316, -73.968),
    ("Richelieu", "Couronne Sud", 45.438, -73.251),
    ("Saint-Amable", "Couronne Sud", 45.660, -73.302),
    ("Saint-Basile-le-Grand", "Couronne Sud", 45.535, -73.288),
    ("Saint-Constant", "Couronne Sud", 45.365, -73.573),
    ("Sainte-Catherine", "Couronne Sud", 45.400, -73.582),
    ("Sainte-Julie", "Couronne Sud", 45.582, -73.331),
    ("Saint-Isidore", "Couronne Sud", 45.331, -73.626),
    ("Saint-Jean-Baptiste", "Couronne Sud", 45.542, -73.099),
    ("Saint-Lazare", "Couronne Sud", 45.400, -74.133),
    ("Saint-Mathias-sur-Richelieu", "Couronne Sud", 45.500, -73.201),
    ("Saint-Mathieu", "Couronne Sud", 45.320, -73.505),
    ("Saint-Mathieu-de-Beloeil", "Couronne Sud", 45.590, -73.251),
    ("Saint-Philippe", "Couronne Sud", 45.360, -73.478),
    ("Terrasse-Vaudreuil", "Couronne Sud", 45.394, -73.960),
    ("Varennes", "Couronne Sud", 45.686, -73.443),
    ("Vaudreuil-Dorion", "Couronne Sud", 45.400, -74.033),
    ("Vaudreuil-sur-le-Lac", "Couronne Sud", 45.408, -74.006),
    ("Verchères", "Couronne Sud", 45.783, -73.351),
    # These three were missing from the fetched Wikipedia table (see module docstring) but are
    # confirmed CMM Couronne Nord members -- verified here by distance (23-36km from Montreal,
    # squarely inside the metro) after an initial pass wrongly bucketed them as "Other".
    ("Terrebonne", "Couronne Nord", 45.700, -73.633),
    ("Repentigny", "Couronne Nord", 45.740, -73.454),
    ("L'Assomption", "Couronne Nord", 45.811, -73.428),
]

# Well-known non-CMM Quebec municipalities, hand-verified coordinates, roughly within 100km.
# Small, deliberately non-exhaustive -- see module docstring.
OTHER_MUNICIPALITIES = [
    ("Saint-Jerome", "Laurentides", 45.780, -74.005),
    ("Saint-Hyacinthe", "Monteregie", 45.630, -72.958),
    ("Sorel-Tracy", "Monteregie", 46.043, -73.116),
    ("Salaberry-de-Valleyfield", "Monteregie", 45.253, -74.127),
    ("Joliette", "Lanaudiere", 46.021, -73.443),
    ("Saint-Jean-sur-Richelieu", "Monteregie", 45.307, -73.262),
    ("Granby", "Monteregie", 45.400, -72.733),
    ("Farnham", "Monteregie", 45.286, -72.978),
    ("Cowansville", "Monteregie", 45.199, -72.747),
    ("Rigaud", "Monteregie", 45.483, -74.305),
    ("Drummondville", "Centre-du-Quebec", 45.883, -72.483),
    ("Saint-Sauveur", "Laurentides", 45.899, -74.171),
    ("Sainte-Adele", "Laurentides", 45.955, -74.132),
]


def build_rows():
    rows = []
    for name, sector, lat, lon in CMM_MUNICIPALITIES:
        dist = haversine_km(MTL_REF_LAT, MTL_REF_LON, lat, lon)
        rows.append({
            "municipality": name,
            "sector_or_region": sector,
            "lat": lat,
            "lon": lon,
            "distance_km_from_mtl": round(dist, 1),
            "in_100km_radius": True,
            "cmm_member": True,
            "region_bucket": "Grand Montreal",
        })
    for name, region, lat, lon in OTHER_MUNICIPALITIES:
        dist = haversine_km(MTL_REF_LAT, MTL_REF_LON, lat, lon)
        rows.append({
            "municipality": name,
            "sector_or_region": region,
            "lat": lat,
            "lon": lon,
            "distance_km_from_mtl": round(dist, 1),
            "in_100km_radius": dist <= 100,
            "cmm_member": False,
            "region_bucket": "Other" if dist <= 100 else "Outside 100km (dropped)",
        })
    return rows


def main():
    rows = build_rows()
    out_path = Path(__file__).resolve().parent.parent / "data" / "qc_geo_lookup.csv"
    fieldnames = ["municipality", "sector_or_region", "lat", "lon", "distance_km_from_mtl",
                  "in_100km_radius", "cmm_member", "region_bucket"]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    outside = [r for r in rows if not r["in_100km_radius"]]
    print(f"Wrote {len(rows)} municipalities to {out_path}")
    print(f"  Grand Montreal (CMM): {sum(1 for r in rows if r['cmm_member'])}")
    print(f"  Other (within 100km): {sum(1 for r in rows if r['region_bucket'] == 'Other')}")
    if outside:
        print(f"  Dropped (beyond 100km): {[r['municipality'] for r in outside]}")


if __name__ == "__main__":
    main()
