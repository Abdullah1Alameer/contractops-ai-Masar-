"""Structured extraction schema for consent / authorization documents."""
from .schemas import _obj, _nullable

CONSENT_CATEGORIES = frozenset(
    {
        "Consent Agreement",
        "Authorization Form",
        "Employment Screening Consent",
        "Data Processing Consent",
        "Privacy Consent",
        "Background Check Authorization",
        "Release of Information",
        "Electronic Signature Consent",
        "Other Legal Consent",
    }
)


def is_consent_category(category: str | None) -> bool:
    return category in CONSENT_CATEGORIES if category else False


CONSENT_EXTRACTION_SCHEMA = {
    "name": "consent_extraction",
    "strict": True,
    "schema": _obj(
        {
            "document_title": _nullable("string"),
            "consenting_party": _nullable("string"),
            "receiving_organizations": {"type": "array", "items": {"type": "string"}},
            "purpose": _nullable("string"),
            "authorized_actions": {"type": "array", "items": {"type": "string"}},
            "personal_data_categories": {"type": "array", "items": {"type": "string"}},
            "criminal_check_authorized": {"type": "boolean"},
            "employment_check_authorized": {"type": "boolean"},
            "education_check_authorized": {"type": "boolean"},
            "international_transfer_authorized": {"type": "boolean"},
            "withdrawal_method": _nullable("string"),
            "governing_privacy_references": {"type": "array", "items": {"type": "string"}},
            "electronic_signature_acknowledgment": {"type": "boolean"},
            "signature_name": _nullable("string"),
            "signature_date": _nullable("string"),
            "consent_limitations": _nullable("string"),
            "duration": _nullable("string"),
            "confidence": {"type": "number"},
        }
    ),
}

CONSENT_SYSTEM = """You extract structured consent and authorization terms from legal consent forms.
Do NOT treat the document as an employment agreement or commercial contract.
Extract only what is explicitly stated in the document excerpt."""
