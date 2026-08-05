"""Stage 0 — contract scope classification before any extraction."""
from __future__ import annotations

import re

from .client import complete_json
from .schemas import _obj

CONFIDENCE_THRESHOLD = 0.80

CONSENT_SUPPORTED_CATEGORIES: list[str] = [
    "Consent Agreement",
    "Authorization Form",
    "Employment Screening Consent",
    "Data Processing Consent",
    "Privacy Consent",
    "Background Check Authorization",
    "Release of Information",
    "Electronic Signature Consent",
    "Other Legal Consent",
]

# General commercial categories (classifier output)
GENERAL_SUPPORTED_CATEGORIES: list[str] = [
    "NDA",
    "Service Agreement",
    "Vendor Agreement",
    "Supplier Agreement",
    "Procurement Agreement",
    "Sales Agreement",
    "Partnership Agreement",
    "Consulting Agreement",
    "Software/SaaS Agreement",
    "Licensing Agreement",
    "Employment Agreement",
    "Lease Agreement",
    "Distribution Agreement",
    "Maintenance Agreement",
    "Master Service Agreement",
    "Statement of Work",
    "Construction Contract",
    "Subcontract",
    "Other Commercial Contract",
] + CONSENT_SUPPORTED_CATEGORIES

# Legacy construction-era labels — still supported for existing DB rows
LEGACY_SUPPORTED_CATEGORIES: list[str] = [
    "Main Construction Contract",
    "Subcontract Agreement",
    "Material Supply Agreement",
    "Supplier Agreement",
    "Procurement Agreement",
    "Construction Service Agreement",
    "Consultant Agreement (Construction)",
    "Purchase Order (Construction)",
    "Maintenance Contract (Construction)",
    "Variation Order",
    "Work Order",
]

SUPPORTED_CATEGORIES: list[str] = GENERAL_SUPPORTED_CATEGORIES + LEGACY_SUPPORTED_CATEGORIES
SUPPORTED_SET = frozenset(SUPPORTED_CATEGORIES)

UNSUPPORTED_CATEGORIES: list[str] = [
    "Unsupported Personal Document",
    "Marriage Contract",
    "Personal Loan Agreement",
    "Personal Identification Document",
    "Court Judgment",
    "Medical Record",
    "Vehicle Sale Agreement",
    "Curriculum Vitae",
    "Unknown",
]

ALL_CATEGORIES = SUPPORTED_CATEGORIES + UNSUPPORTED_CATEGORIES

PARENT_LIKE = frozenset(
    {
        "Construction Contract",
        "Main Construction Contract",
        "Master Service Agreement",
    }
)
CHILD_LIKE = frozenset(
    {
        "Subcontract",
        "Subcontract Agreement",
        "Statement of Work",
    }
)

# Categories that must not enter comparison or full commercial extraction
PERSONAL_UNSUPPORTED = frozenset(
    {
        "Unsupported Personal Document",
        "Marriage Contract",
        "Personal Loan Agreement",
        "Personal Identification Document",
        "Court Judgment",
        "Medical Record",
        "Vehicle Sale Agreement",
        "Curriculum Vitae",
    }
)

CONSENT_TRIGGER_PATTERNS = [
    re.compile(r"\bi\s+consent\b", re.I),
    re.compile(r"\bi\s+authorize\b", re.I),
    re.compile(r"\bi\s+agree\b", re.I),
    re.compile(r"\bi\s+acknowledge\b", re.I),
    re.compile(r"permission\s+to\s+process", re.I),
    re.compile(r"release\s+(of\s+)?information", re.I),
    re.compile(r"electronic\s+signature", re.I),
    re.compile(r"withdraw(al)?\s+of\s+consent", re.I),
    re.compile(r"background\s+(check|screening)", re.I),
    re.compile(r"criminal\s+record", re.I),
    re.compile(r"personal\s+data", re.I),
]

CV_ONLY_PATTERNS = [
    re.compile(r"curriculum\s+vitae", re.I),
    re.compile(r"\bresume\b", re.I),
    re.compile(r"work\s+experience\s*:", re.I),
    re.compile(r"education\s*:\s*.*bachelor", re.I),
]

ID_ONLY_PATTERNS = [
    re.compile(r"national\s+identity\s+card", re.I),
    re.compile(r"identification\s+card\s+number", re.I),
    re.compile(r"passport\s+no\.?", re.I),
]

CLASSIFIER_SYSTEM = """You are a contract classifier for ContractOps AI — a general-purpose AI Contract Operations Platform for commercial and legal agreements across all industries.

Classify the document into exactly ONE category from the allowed list.

SUPPORTED COMMERCIAL (analyze fully):
- NDA, Service Agreement, Vendor Agreement, Supplier Agreement, Procurement Agreement,
  Sales Agreement, Partnership Agreement, Consulting Agreement, Software/SaaS Agreement,
  Licensing Agreement, Employment Agreement, Lease Agreement, Distribution Agreement,
  Maintenance Agreement, Master Service Agreement, Statement of Work,
  Construction Contract, Subcontract, Other Commercial Contract.
- Legacy labels still valid: Main Construction Contract, Subcontract Agreement,
  Material Supply Agreement, Construction Service Agreement, Variation Order, Work Order, etc.

SUPPORTED CONSENT / AUTHORIZATION (analyze fully — NOT employment agreements):
- Consent Agreement, Authorization Form, Employment Screening Consent,
  Data Processing Consent, Privacy Consent, Background Check Authorization,
  Release of Information, Electronic Signature Consent, Other Legal Consent.
- Personal documents CAN still be supported legal consent if they contain authorization language
  (I consent, I authorize, I agree, permission to process, release information, electronic signature, withdrawal of consent).

UNSUPPORTED (no meaningful agreement / consent / authorization):
- Unsupported Personal Document, Marriage Contract, Personal Loan Agreement,
  Personal Identification Document (ID card only), Court Judgment,
  Medical Record (test result without consent terms), Vehicle Sale Agreement (personal sale),
  Curriculum Vitae / résumé only, bank statements, brochures, unrelated correspondence.
- Unknown: use when confidence is below 0.80 AND no clear consent or contract language.

Rules:
- Read title, parties, subject matter, and defined terms from the excerpt only.
- Employment agreements ARE supported when they are actual employment contracts.
- Background screening consent forms ARE supported under Employment Screening Consent or Background Check Authorization.
- NEVER hard-reject uncertain legal consent — prefer Other Legal Consent with lower confidence.
"""

CLASSIFICATION_SCHEMA = {
    "name": "contract_classification",
    "strict": True,
    "schema": _obj({
        "contract_category": {"type": "string", "enum": ALL_CATEGORIES},
        "confidence": {"type": "number"},
        "reasoning_brief": {"type": "string"},
    }),
}


def text_has_consent_triggers(text: str) -> bool:
    return any(p.search(text) for p in CONSENT_TRIGGER_PATTERNS)


def text_looks_cv_only(text: str) -> bool:
    if not text_has_consent_triggers(text):
        return any(p.search(text) for p in CV_ONLY_PATTERNS)
    return False


def text_looks_id_only(text: str) -> bool:
    if text_has_consent_triggers(text):
        return False
    hits = sum(1 for p in ID_ONLY_PATTERNS if p.search(text))
    return hits >= 1 and len(text) < 800


def is_supported_category(category: str | None, confidence: float) -> bool:
    if confidence < CONFIDENCE_THRESHOLD:
        return False
    if not category or category in PERSONAL_UNSUPPORTED or category == "Unknown":
        return False
    return category in SUPPORTED_SET


def category_to_type(category: str | None) -> str | None:
    if not category:
        return None
    if category in CONSENT_SUPPORTED_CATEGORIES:
        return None
    if category in PARENT_LIKE:
        return "main"
    if category in CHILD_LIKE:
        return "subcontract"
    return None


def relationship_type_for_category(category: str | None) -> str:
    if category in PARENT_LIKE:
        return "parent"
    if category in CHILD_LIKE:
        return "child"
    return "standalone"


def is_comparison_eligible(contract) -> bool:
    """Contract row must be ready and a supported commercial category."""
    if contract is None:
        return False
    if contract.status not in ("ready", "needs_review"):
        return False
    if contract.supported is False:
        return False
    cat = contract.contract_category or ""
    if cat in CONSENT_SUPPORTED_CATEGORIES:
        return False
    if cat in PERSONAL_UNSUPPORTED or cat == "Unknown":
        return False
    return cat in SUPPORTED_SET or contract.supported is True


def _deterministic_gate(text: str, category: str, confidence: float) -> dict | None:
    """Return override dict or None."""
    if text_looks_cv_only(text):
        return {
            "supported": False,
            "contract_category": "Curriculum Vitae",
            "confidence": max(confidence, 0.85),
            "message": "This document appears to be a CV or résumé without contract terms.",
            "needs_review": False,
        }
    if text_looks_id_only(text):
        return {
            "supported": False,
            "contract_category": "Personal Identification Document",
            "confidence": max(confidence, 0.85),
            "message": "This document appears to be identification only.",
            "needs_review": False,
        }
    if text_has_consent_triggers(text):
        if category in PERSONAL_UNSUPPORTED or category == "Unknown" or confidence < CONFIDENCE_THRESHOLD:
            return {
                "supported": True,
                "contract_category": "Other Legal Consent",
                "confidence": round(max(confidence, 0.72), 2),
                "message": "needs_classification_review",
                "needs_review": True,
            }
        if category in CONSENT_SUPPORTED_CATEGORIES:
            return {
                "supported": True,
                "contract_category": category,
                "confidence": round(confidence, 2),
                "message": None if confidence >= CONFIDENCE_THRESHOLD else "needs_classification_review",
                "needs_review": confidence < CONFIDENCE_THRESHOLD,
            }
    return None


def classify_contract(text: str) -> dict:
    """Classify contract text (normalized excerpt). Returns gate result for pipeline + API."""
    user = (
        "Classify this document excerpt. Return contract_category and confidence (0..1).\n\n"
        f"----- DOCUMENT START -----\n{text}\n----- DOCUMENT END -----"
    )
    raw = complete_json(CLASSIFIER_SYSTEM, user, CLASSIFICATION_SCHEMA)
    category = raw.get("contract_category") or "Unknown"
    confidence = float(raw.get("confidence") or 0)

    override = _deterministic_gate(text, category, confidence)
    if override:
        return {
            **override,
            "supported_categories": list(GENERAL_SUPPORTED_CATEGORIES),
        }

    message: str | None = None
    needs_review = False
    supported = is_supported_category(category, confidence)

    if confidence < CONFIDENCE_THRESHOLD:
        if text_has_consent_triggers(text):
            category = "Other Legal Consent"
            supported = True
            needs_review = True
            message = "needs_classification_review"
        else:
            category = "Unknown"
            supported = False
            message = "Unable to confidently classify this document."
    elif category in PERSONAL_UNSUPPORTED:
        supported = False
        message = "This document is outside commercial contract scope."
    elif category in CONSENT_SUPPORTED_CATEGORIES:
        supported = True
    elif not supported:
        message = "This contract type is currently not supported."

    return {
        "supported": supported,
        "contract_category": category,
        "confidence": round(confidence, 2),
        "message": message,
        "needs_review": needs_review,
        "supported_categories": list(GENERAL_SUPPORTED_CATEGORIES),
    }


# Any supported commercial contract may be compared (not construction-only)
FLOWDOWN_ELIGIBLE = SUPPORTED_SET - frozenset(CONSENT_SUPPORTED_CATEGORIES)
