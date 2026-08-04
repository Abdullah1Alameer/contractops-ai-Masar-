"""Prompt B — Flow-Down X-Ray comparison (strict json_schema)."""
from __future__ import annotations

import json

from .schemas import _obj, _nullable

FLOWDOWN_CATEGORIES: list[str] = [
    "scope_of_work",
    "deliverables",
    "milestones",
    "completion_dates",
    "payment_terms",
    "retention",
    "performance_bond",
    "advance_payment",
    "insurance",
    "quality_requirements",
    "inspection_requirements",
    "hse_requirements",
    "liquidated_damages",
    "delay_clauses",
    "extension_of_time",
    "warranty",
    "defects_liability_period",
    "termination",
    "variation_orders",
    "notice_requirements",
    "dispute_resolution",
    "governing_law",
    "force_majeure",
]

FLOWDOWN_STATUSES = [
    "fully_flowed_down",
    "modified",
    "missing",
    "weaker",
    "stronger",
    "conflict",
]

FLOWDOWN_RISKS = ["critical", "high", "medium", "low", "informational"]

FLOWDOWN_SYSTEM = """You are a senior Saudi construction contracts lawyer performing back-to-back flow-down analysis between a Main Construction Contract and a Subcontract Agreement.

This is LEGAL SEMANTIC comparison — NOT a text diff. Compare obligations, thresholds, dates, and risk allocation category by category.

STRICT RULES:
1. You MUST produce exactly one finding per category in the provided categories list (same order not required).
2. category MUST be one of the allowed enum values exactly.
3. status MUST reflect how the subcontract compares to the main contract for that topic:
   - fully_flowed_down: equivalent obligation transferred
   - modified: present but materially different terms
   - missing: main requires it; subcontract silent or absent in dossier
   - weaker: subcontract obligation is less strict than main (exposure for main contractor)
   - stronger: subcontract is stricter than main
   - conflict: incompatible terms (e.g. different completion dates)
4. risk_level: critical | high | medium | low | informational — based on commercial/legal exposure to the main contractor.
5. main_clause_id and sub_clause_id MUST be UUID strings copied ONLY from the dossier bundles for that side, or null if not found in dossier.
6. main_citation / sub_citation: short human label e.g. "Clause 12.4"; use null (not any string) if the side has no item for this category — the UI localises the "Not Found" message.
7. You MUST always return BOTH languages for every finding:
   - explanation_ar and explanation_en (professional legal Arabic and English prose of the same meaning)
   - recommendation_ar and recommendation_en (concrete actionable advice in both languages)
   Never leave a language empty. If dossier is thin, still write a short honest sentence in each language.
8. confidence 0..1 — honest; below 0.7 means uncertain dossier coverage.
9. NEVER invent clause_ids. If dossier has no item for a side, clause_id null and citation null.
10. When both sides have no dossier items for a category, status=fully_flowed_down, risk_level=informational, both clause_ids null, and the explanation/recommendation in both languages should state that neither contract addresses this category.
"""


def build_flowdown_user_prompt(main_dossier: dict, sub_dossier: dict) -> str:
    payload = {
        "categories": FLOWDOWN_CATEGORIES,
        "main": main_dossier,
        "sub": sub_dossier,
    }
    return (
        "Compare the main contract dossier to the subcontract dossier. "
        "Return one finding object per category.\n\n"
        f"{json.dumps(payload, ensure_ascii=False, default=str)}"
    )


_FINDING_ITEM = _obj({
    "category": {"type": "string", "enum": FLOWDOWN_CATEGORIES},
    "status": {"type": "string", "enum": FLOWDOWN_STATUSES},
    "risk_level": {"type": "string", "enum": FLOWDOWN_RISKS},
    "explanation_ar": {"type": "string"},
    "explanation_en": {"type": "string"},
    "recommendation_ar": {"type": "string"},
    "recommendation_en": {"type": "string"},
    "main_clause_id": _nullable("string"),
    "sub_clause_id": _nullable("string"),
    "main_citation": _nullable("string"),
    "sub_citation": _nullable("string"),
    "confidence": {"type": "number"},
})

FLOWDOWN_SCHEMA = {
    "name": "flowdown_analysis",
    "strict": True,
    "schema": _obj({
        "findings": {
            "type": "array",
            "items": _FINDING_ITEM,
        },
    }),
}
