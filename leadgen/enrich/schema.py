"""Contact-enrichment schema shared by `leadgen ingest` and whatever gathered the raw leads
(a live agent run, or you pasting results by hand).

Enrichment itself is NOT implemented in Python -- REQ/company-site/LinkedIn-snippet lookups
require live, per-site judgment calls (see docs/STEP0_SOURCE_FEASIBILITY.md and
docs/ROUTINE_PROMPT.md) that belong to whoever runs the search, not a fixed scraper. This module
only validates the *shape* of whatever contact fields show up in an ingest record, so a
malformed or silently-degraded contact never looks the same as a verified one in the Sheet.
"""
from dataclasses import dataclass
from typing import List

CONTACT_SOURCE_TIERS = ("req_registry", "company_site", "linkedin_search", "generic_fallback", "")
CONTACT_CONFIDENCE_LEVELS = ("High", "Medium", "Low", "")


@dataclass
class Contact:
    name: str = ""
    title: str = ""
    email: str = ""
    phone: str = ""
    source_tier: str = ""
    confidence: str = ""

    @classmethod
    def from_raw(cls, raw: dict) -> "Contact":
        return cls(
            name=(raw.get("contact_name") or "").strip(),
            title=(raw.get("contact_title") or "").strip(),
            email=(raw.get("contact_email") or "").strip(),
            phone=(raw.get("contact_phone") or "").strip(),
            source_tier=(raw.get("contact_source_tier") or "").strip(),
            confidence=(raw.get("contact_confidence") or "").strip(),
        )

    def validate(self) -> List[str]:
        errors = []
        if self.source_tier not in CONTACT_SOURCE_TIERS:
            errors.append(f"invalid contact_source_tier '{self.source_tier}'")
        if self.confidence not in CONTACT_CONFIDENCE_LEVELS:
            errors.append(f"invalid contact_confidence '{self.confidence}'")
        if self.source_tier == "generic_fallback" and self.confidence not in ("Low", ""):
            errors.append("contact_source_tier=generic_fallback should be tagged confidence=Low, "
                           "so it never looks the same as a verified named contact")
        if self.source_tier and not (self.email or self.phone):
            errors.append(f"contact_source_tier='{self.source_tier}' set but no email or phone given")
        if self.source_tier and self.source_tier != "generic_fallback" and not self.name:
            errors.append(f"contact_source_tier='{self.source_tier}' implies a named contact but "
                           f"contact_name is blank")
        return errors
