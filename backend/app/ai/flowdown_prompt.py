"""Prompt B — Contract Comparison & Compliance (strict json_schema)."""
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
    "confidentiality",
    "liability",
    "indemnity",
    "intellectual_property",
    "data_protection",
    "sla",
    "renewal",
    "auto_renewal",
    "termination",
    "notice_requirements",
    "dispute_resolution",
    "governing_law",
    "jurisdiction",
    "compliance",
    "liquidated_damages",
    "delay_clauses",
    "extension_of_time",
    "warranty",
    "defects_liability_period",
    "variation_orders",
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

FLOWDOWN_SYSTEM = """You are a senior commercial contracts lawyer performing Contract Comparison & Compliance analysis between a Primary contract and a Related contract (MSA vs SOW, template vs draft, parent vs subcontract, or any valid pair).

This is LEGAL SEMANTIC comparison — NOT a text diff. Compare obligations, thresholds, dates, and risk allocation category by category.

STRICT RULES:
1. You MUST produce exactly one finding per category in the provided categories list.
2. category MUST be one of the allowed enum values exactly.
3. status reflects how the Related contract compares to the Primary for that topic:
   - fully_flowed_down: equivalent obligation or protection aligned
   - modified: present but materially different terms
   - missing: Primary requires it; Related silent or absent in dossier
   - weaker: Related obligation/protection is less strict (exposure for Primary party)
   - stronger: Related is stricter than Primary
   - conflict: incompatible terms
4. risk_level: critical | high | medium | low | informational — based on commercial/legal exposure.
5. main_clause_id and sub_clause_id MUST be UUID strings from the Primary and Related dossiers only, or null.
6. main_citation / sub_citation: short label e.g. "Clause 12.4"; null if no dossier item.
7. explanation_ar, explanation_en, recommendation_ar, recommendation_en — both languages always, same meaning.
8. confidence 0..1 — honest.
9. NEVER invent clause_ids.
10. When both sides lack dossier items for a category, status=fully_flowed_down, risk_level=informational, clause_ids null.
"""


def build_flowdown_user_prompt(main_dossier: dict, sub_dossier: dict) -> str:
    payload = {
        "categories": FLOWDOWN_CATEGORIES,
        "primary": main_dossier,
        "related": sub_dossier,
    }
    return (
        "Compare the Primary contract dossier to the Related contract dossier. "
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
