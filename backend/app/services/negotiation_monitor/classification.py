"""Email response classification."""
from __future__ import annotations

import re
from typing import Any

from ...ai.client import complete_json
from ...ai.email_classification_prompt import (
    EMAIL_CLASSIFICATION_SCHEMA,
    EMAIL_CLASSIFICATION_SYSTEM,
    build_classification_prompt,
)

_APPROVAL = re.compile(r"\b(approved|accept(ed)?|we agree|proceed as written)\b", re.I)
_REJECTION = re.compile(r"\b(reject(ed)?|cannot accept|decline)\b", re.I)
_INFO = re.compile(r"\b(thank you|thanks|received|acknowledged|noted)\b", re.I)
_CHANGES = re.compile(r"\b(revis(ed|e)|changes requested|clause|objection|counter)\b", re.I)


def _deterministic(subject: str | None, body: str | None) -> dict[str, Any] | None:
    text = f"{subject or ''}\n{body or ''}".strip()
    if not text:
        return {
            "classification": "unknown",
            "requires_response": True,
            "summary": "Empty message",
            "mentioned_clauses": [],
            "attachment_expected": False,
            "confidence": 0.2,
            "needs_review": True,
        }
    if _APPROVAL.search(text) and not _CHANGES.search(text):
        return {
            "classification": "approval",
            "requires_response": False,
            "summary": "Counterparty appears to approve.",
            "mentioned_clauses": [],
            "attachment_expected": False,
            "confidence": 0.85,
            "needs_review": False,
        }
    if _REJECTION.search(text):
        return {
            "classification": "rejection",
            "requires_response": True,
            "summary": "Counterparty rejected terms.",
            "mentioned_clauses": [],
            "attachment_expected": False,
            "confidence": 0.8,
            "needs_review": False,
        }
    if _INFO.search(text) and len(text) < 200 and not _CHANGES.search(text):
        return {
            "classification": "informational",
            "requires_response": False,
            "summary": "Informational acknowledgment.",
            "mentioned_clauses": [],
            "attachment_expected": False,
            "confidence": 0.75,
            "needs_review": False,
        }
    return None


def classify_email(*, subject: str | None, body_text: str | None, has_attachment: bool = False) -> dict[str, Any]:
    pre = _deterministic(subject, body_text)
    if pre:
        if has_attachment and pre["classification"] in ("informational", "approval"):
            pre["classification"] = "revised_contract"
            pre["attachment_expected"] = True
            pre["requires_response"] = True
        return pre

    if has_attachment:
        return {
            "classification": "revised_contract",
            "requires_response": True,
            "summary": "Attachment present; treat as revised contract until analyzed.",
            "mentioned_clauses": [],
            "attachment_expected": True,
            "confidence": 0.7,
            "needs_review": False,
        }

    try:
        result = complete_json(
            EMAIL_CLASSIFICATION_SYSTEM,
            build_classification_prompt(subject=subject, body_text=body_text),
            EMAIL_CLASSIFICATION_SCHEMA,
        )
        if not result.get("mentioned_clauses"):
            result["mentioned_clauses"] = []
        return result
    except Exception:
        return {
            "classification": "unknown",
            "requires_response": True,
            "summary": "Classification failed; manual review required.",
            "mentioned_clauses": [],
            "attachment_expected": False,
            "confidence": 0.0,
            "needs_review": True,
        }
