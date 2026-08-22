"""Sector exclusion filter: NAICS-first, narrow keyword fallback, explicit whitelist.

Never excludes based on full job-description text -- only company_name and job_title -- to
avoid false-excludes like a grocery distributor whose description happens to mention "meat".
"""
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "naics_exclude.yaml"


def _normalize(text: str) -> str:
    """Lowercase + strip accents, so 'épicerie'/'Epicerie'/'ÉPICERIE' all match the same rule.
    Real-world postings mix accented and unaccented company names inconsistently."""
    text = text.lower()
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


@dataclass
class ExclusionResult:
    excluded: bool
    method: Optional[str] = None  # "naics" | "keyword" | None
    reason: Optional[str] = None


class SectorExcluder:
    def __init__(self, config_path: Path = _CONFIG_PATH):
        with open(config_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        self.naics_exclude = cfg["naics_exclude"]
        self.keyword_exclude = [_normalize(kw) for kw in cfg["keyword_exclude_fr"] + cfg["keyword_exclude_en"]]
        self.never_exclude = [_normalize(kw) for kw in cfg["never_exclude_fr"] + cfg["never_exclude_en"]]

    def evaluate(self, company_name: str = "", job_title: str = "", naics_code: str = "") -> ExclusionResult:
        text = _normalize(f"{company_name} {job_title}")

        # Whitelist wins outright, even over a NAICS match, since a NAICS code on a hand-entered
        # or partially-filled record is more error-prone than on a structured Job Bank export.
        if any(term in text for term in self.never_exclude):
            return ExclusionResult(excluded=False)

        if naics_code:
            naics4 = naics_code.strip()[:4]
            if naics4 in self.naics_exclude:
                return ExclusionResult(excluded=True, method="naics",
                                        reason=f"NAICS {naics4}: {self.naics_exclude[naics4]}")

        for kw in self.keyword_exclude:
            if kw in text:
                return ExclusionResult(excluded=True, method="keyword", reason=f"matched keyword '{kw.strip()}'")

        return ExclusionResult(excluded=False)
