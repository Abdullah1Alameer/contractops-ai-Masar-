"""Lawyer review package synthesis schema (Feature 16)."""
from __future__ import annotations

from .schemas import _obj

_CITATION = {
    "type": "object",
    "properties": {
        "quote": {"type": "string"},
        "location": {"type": "string"},
    },
    "required": ["quote", "location"],
    "additionalProperties": False,
}

_CHANGE = {
    "type": "object",
    "properties": {
        "clause_category": {"type": "string"},
        "clause_reference": {"type": "string"},
        "original_text": {"type": "string"},
        "revised_text": {"type": "string"},
        "template_text": {"type": "string"},
        "change_type": {"type": "string", "enum": ["added", "removed", "modified", "missing"]},
        "risk_level": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
        "business_impact": {"type": "string"},
        "legal_impact": {"type": "string"},
        "playbook_position": {
            "type": "string",
            "enum": [
                "standard",
                "acceptable",
                "fallback",
                "non_standard",
                "unacceptable",
                "missing",
                "needs_review",
            ],
        },
        "required_approver": {
            "type": "string",
            "enum": ["none", "legal", "finance", "compliance", "executive"],
        },
        "recommendation": {"type": "string"},
        "counter_clause_en": {"type": "string"},
        "counter_clause_ar": {"type": "string"},
        "citations": {
            "type": "object",
            "properties": {
                "previous_version": _CITATION,
                "new_version": _CITATION,
                "template": _CITATION,
            },
            "required": ["previous_version", "new_version", "template"],
            "additionalProperties": False,
        },
        "confidence": {"type": "number"},
    },
    "required": [
        "clause_category",
        "clause_reference",
        "original_text",
        "revised_text",
        "template_text",
        "change_type",
        "risk_level",
        "business_impact",
        "legal_impact",
        "playbook_position",
        "required_approver",
        "recommendation",
        "counter_clause_en",
        "counter_clause_ar",
        "citations",
        "confidence",
    ],
    "additionalProperties": False,
}

REVIEW_PACKAGE_SCHEMA = {
    "name": "negotiation_review_package",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "executive_summary": {"type": "string"},
            "counterparty_intent": {"type": "string"},
            "overall_risk_score": {"type": "integer"},
            "recommended_strategy": {
                "type": "string",
                "enum": ["accept", "accept_with_conditions", "negotiate", "reject", "escalate"],
            },
            "changes": {"type": "array", "items": _CHANGE},
            "draft_email_subject_en": {"type": "string"},
            "draft_email_subject_ar": {"type": "string"},
            "draft_email_body_en": {"type": "string"},
            "draft_email_body_ar": {"type": "string"},
            "open_questions": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "executive_summary",
            "counterparty_intent",
            "overall_risk_score",
            "recommended_strategy",
            "changes",
            "draft_email_subject_en",
            "draft_email_subject_ar",
            "draft_email_body_en",
            "draft_email_body_ar",
            "open_questions",
        ],
        "additionalProperties": False,
    },
}

REVIEW_PACKAGE_SYSTEM = """You prepare a lawyer review package for contract negotiation.
Never send email automatically. Never claim legal certainty.
Never invent template language or clause references without citations.
If a citation is missing, set playbook_position to needs_review and confidence low.
Produce professional Arabic and English counter-clause wording and email drafts.
Separate legal, business, financial, and operational impact in change descriptions."""


def build_review_package_prompt(context: dict) -> str:
    import json

    return json.dumps(context, ensure_ascii=False, indent=2)
