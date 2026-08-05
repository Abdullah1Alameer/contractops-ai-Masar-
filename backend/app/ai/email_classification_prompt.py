"""Strict JSON schema for inbound email classification."""
from __future__ import annotations

from .schemas import _obj

_CLAUSE = {
    "type": "object",
    "properties": {
        "reference": {"type": "string"},
        "quote": {"type": "string"},
        "requested_change": {"type": "string"},
    },
    "required": ["reference", "quote", "requested_change"],
    "additionalProperties": False,
}

EMAIL_CLASSIFICATION_SCHEMA = {
    "name": "email_classification",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "classification": {
                "type": "string",
                "enum": [
                    "revised_contract",
                    "clause_objection",
                    "request_changes",
                    "approval",
                    "rejection",
                    "counterproposal",
                    "informational",
                    "unknown",
                ],
            },
            "requires_response": {"type": "boolean"},
            "summary": {"type": "string"},
            "mentioned_clauses": {"type": "array", "items": _CLAUSE},
            "attachment_expected": {"type": "boolean"},
            "confidence": {"type": "number"},
            "needs_review": {"type": "boolean"},
        },
        "required": [
            "classification",
            "requires_response",
            "summary",
            "mentioned_clauses",
            "attachment_expected",
            "confidence",
            "needs_review",
        ],
        "additionalProperties": False,
    },
}

EMAIL_CLASSIFICATION_SYSTEM = """You classify counterparty negotiation emails for a legal team.
Never invent clause references — only cite clauses explicitly mentioned in the email.
Mark needs_review true when uncertain.
Never send email; classification only.
Arabic and English emails are both supported."""


def build_classification_prompt(*, subject: str | None, body_text: str | None) -> str:
    return f"Subject:\n{subject or ''}\n\nBody:\n{body_text or ''}"
