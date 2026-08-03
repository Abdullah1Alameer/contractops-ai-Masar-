"""Stage 0 — contract scope classification before any extraction."""
from __future__ import annotations

from .client import complete_json
from .schemas import _obj

CONFIDENCE_THRESHOLD = 0.80

SUPPORTED_CATEGORIES: list[str] = [
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

SUPPORTED_SET = frozenset(SUPPORTED_CATEGORIES)

UNSUPPORTED_CATEGORIES: list[str] = [
    "Employment Contract",
    "Residential Lease",
    "Personal Rental Agreement",
    "Marriage Contract",
    "Personal Loan Agreement",
    "Vehicle Sale Agreement",
    "Generic NDA",
    "General Commercial Contract",
    "Unknown",
]

ALL_CATEGORIES = SUPPORTED_CATEGORIES + UNSUPPORTED_CATEGORIES

CLASSIFIER_SYSTEM = """You are a contract classifier for ContractOps AI — a domain-specific platform for Saudi construction and real estate operational contracts ONLY.

Classify the document into exactly ONE category from the allowed list.

SUPPORTED (construction / real-estate operations):
- Main Construction Contract: employer–contractor, full project scope, FIDIC-style, BOQ, LDs, retention, bonds.
- Subcontract Agreement: main contractor ↔ subcontractor, scope of works for a trade (MEP, concrete, finishing, etc.).
- Material Supply Agreement: supply/delivery of construction materials.
- Supplier Agreement: supplier of goods/services to a construction project.
- Procurement Agreement: project procurement / purchasing terms.
- Construction Service Agreement: services on a construction site (not employment).
- Consultant Agreement (Construction): engineer/architect/consultant on a construction project.
- Purchase Order (Construction): PO for construction-related goods or works.
- Maintenance Contract (Construction): O&M or maintenance tied to built assets.
- Variation Order: change order / additional works to an existing construction contract.
- Work Order: directed works under an existing agreement.

UNSUPPORTED (stop — not this platform):
- Employment Contract (including background checks, HR, offer letters).
- Residential Lease, Personal Rental Agreement.
- Marriage Contract, Personal Loan Agreement, Vehicle Sale Agreement.
- Generic NDA unless clearly tied to a specific construction subcontract scope.
- General Commercial Contract with no construction/real-estate operational context.
- Unknown: use when you cannot confidently assign a category (confidence must be below 0.80).

Rules:
- Read title, parties, subject matter, and defined terms only from the provided excerpt.
- NEVER guess. If the document is ambiguous or not clearly a supported type, choose Unknown and set confidence below 0.80.
- Generic NDA with no construction context → Generic NDA (unsupported).
- Employment screening / consent forms → Employment Contract (unsupported).
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


def category_to_type(category: str | None) -> str | None:
    if category == "Main Construction Contract":
        return "main"
    if category == "Subcontract Agreement":
        return "subcontract"
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

    message: str | None = None
    supported = category in SUPPORTED_SET and confidence >= CONFIDENCE_THRESHOLD

    if confidence < CONFIDENCE_THRESHOLD:
        category = "Unknown"
        supported = False
        message = "Unable to confidently classify this document."
    elif not supported:
        message = "This contract type is currently not supported."

    return {
        "supported": supported,
        "contract_category": category,
        "confidence": round(confidence, 2),
        "message": message,
        "supported_categories": list(SUPPORTED_CATEGORIES),
    }


FLOWDOWN_ELIGIBLE = frozenset({"Main Construction Contract", "Subcontract Agreement"})
