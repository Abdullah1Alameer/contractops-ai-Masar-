"""Strict structured-output JSON schema for Prompt A.

A copy is snapshotted to shared/extraction.schema.json for teammates —
THIS file is the source of truth.
"""


def _obj(props: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": props,
        "required": required if required is not None else list(props.keys()),
    }


def _nullable(t: str) -> dict:
    return {"type": [t, "null"]}


_SOURCE_FIELDS = {
    "clause_ref": _nullable("string"),
    "quote": {"type": "string"},
    "page": {"type": "integer"},
}

_DATE_RAW = _obj({
    "value": {"type": "string"},
    "detected_calendar": {"type": "string", "enum": ["hijri", "gregorian"]},
    **_SOURCE_FIELDS,
    "confidence": {"type": "number"},
})

_DATE_RAW_NULLABLE = {"anyOf": [_DATE_RAW, {"type": "null"}]}

_DUE_DATE_RAW = {
    "anyOf": [
        _obj({
            "value": {"type": "string"},
            "detected_calendar": {"type": "string", "enum": ["hijri", "gregorian"]},
        }),
        {"type": "null"},
    ]
}

EXTRACTION_SCHEMA = {
    "name": "contract_extraction",
    "strict": True,
    "schema": _obj({
        "language": {"type": "string", "enum": ["ar", "en", "mixed"]},
        "calendar": {"type": "string", "enum": ["gregorian", "hijri", "mixed"]},
        "parties": _obj({"a": _nullable("string"), "b": _nullable("string")}),
        "value_sar": _nullable("number"),
        "start_date_raw": _DATE_RAW_NULLABLE,
        "end_date_raw": _DATE_RAW_NULLABLE,
        "governing_law": _nullable("string"),
        "retention_pct": _nullable("number"),
        "bond_expiry_raw": _DATE_RAW_NULLABLE,
        "warranty_end_raw": _DATE_RAW_NULLABLE,
        "notice_periods": {
            "type": "array",
            "description": (
                "EVERY clause creating a time window in days for a party to notify, claim, "
                "object, respond, or pay. Includes claim/extension notices, defect notification "
                "windows, suspension notices, AND payment windows (e.g. paying an invoice within "
                "15 days of receipt). Do not skip payment windows — they belong here AND in "
                "obligations."
            ),
            "items": _obj({
                "purpose": {"type": "string"},
                "days": {"type": "integer"},
                **_SOURCE_FIELDS,
                "confidence": {"type": "number"},
            }),
        },
        "obligations": {
            "type": "array",
            "items": _obj({
                "description": {"type": "string"},
                "responsible_party": {"type": "string"},
                "due_date_raw": _DUE_DATE_RAW,
                "due_in_days": _nullable("integer"),
                "penalty_text": _nullable("string"),
                **_SOURCE_FIELDS,
                "confidence": {"type": "number"},
            }),
        },
        "payment_milestones": {
            "type": "array",
            "items": _obj({
                "seq": {"type": "integer"},
                "label": {"type": "string"},
                "amount_sar": _nullable("number"),
                "amount_pct": _nullable("number"),
                "preconditions": {"type": "array", "items": {"type": "string"}},
                **_SOURCE_FIELDS,
                "confidence": {"type": "number"},
            }),
        },
        "penalties": {
            "type": "array",
            "items": _obj({
                "type": {"type": "string"},
                "rate": {"type": "string"},
                "cap": _nullable("string"),
                **_SOURCE_FIELDS,
                "confidence": {"type": "number"},
            }),
        },
        "field_confidences": _obj({
            "parties": {"type": "number"},
            "value_sar": {"type": "number"},
            "start_date": {"type": "number"},
            "end_date": {"type": "number"},
            "governing_law": {"type": "number"},
            "retention_pct": {"type": "number"},
            "bond_expiry": {"type": "number"},
            "warranty_end": {"type": "number"},
        }),
    }),
}
