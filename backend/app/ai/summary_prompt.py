"""Bilingual executive contract summary (Feature 18)."""
from __future__ import annotations

PROMPT_VERSION = "executive_summary_v1"

_CITATION = {
    "type": "object",
    "properties": {
        "clause_ref": {"type": "string"},
        "page": {"type": "integer"},
        "quote": {"type": "string"},
    },
    "required": ["clause_ref", "page", "quote"],
    "additionalProperties": False,
}

_ITEM = {
    "type": "object",
    "properties": {
        "text_ar": {"type": "string"},
        "text_en": {"type": "string"},
        "citations": {"type": "array", "items": _CITATION},
    },
    "required": ["text_ar", "text_en", "citations"],
    "additionalProperties": False,
}

_SECTION = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["stated", "not_stated"]},
        "overview_ar": {"type": "string"},
        "overview_en": {"type": "string"},
        "items": {"type": "array", "items": _ITEM},
    },
    "required": ["status", "overview_ar", "overview_en", "items"],
    "additionalProperties": False,
}

SUMMARY_SCHEMA = {
    "name": "contract_executive_summary",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "purpose": _SECTION,
            "parties": _SECTION,
            "term_and_key_dates": _SECTION,
            "financial_terms": _SECTION,
            "key_obligations": _SECTION,
            "termination_renewal": _SECTION,
            "notable_risks": _SECTION,
            "next_steps": _SECTION,
        },
        "required": [
            "purpose",
            "parties",
            "term_and_key_dates",
            "financial_terms",
            "key_obligations",
            "termination_renewal",
            "notable_risks",
            "next_steps",
        ],
        "additionalProperties": False,
    },
}

SUMMARY_SYSTEM = """You produce a bilingual executive summary of a contract for legal and business readers.
Rules:
- Use ONLY facts supported by the supplied contract text and structured extraction hints.
- Do NOT invent parties, amounts, dates, obligations, or risks not present in the source.
- If a topic is not addressed in the contract, set section status to not_stated and leave overview/items minimal (state that it is not stated).
- Each factual bullet must include at least one citation with an exact quote substring copied verbatim from the contract text.
- Write professional Modern Standard Arabic in overview_ar and text_ar fields; clear business English in overview_en and text_en.
- next_steps must be actionable operational steps grounded in the contract (not generic legal advice).
"""

SECTION_KEYS = (
    "purpose",
    "parties",
    "term_and_key_dates",
    "financial_terms",
    "key_obligations",
    "termination_renewal",
    "notable_risks",
    "next_steps",
)


def build_summary_user_prompt(
    *,
    title: str | None,
    category: str | None,
    raw_excerpt: str,
    structured_hints: str,
) -> str:
    return (
        "Summarize this contract into the required JSON sections.\n\n"
        f"Title hint: {title or 'Unknown'}\n"
        f"Category hint: {category or 'Unknown'}\n\n"
        f"Structured platform hints (may be incomplete):\n{structured_hints}\n\n"
        f"----- CONTRACT TEXT START -----\n{raw_excerpt}\n----- CONTRACT TEXT END -----"
    )
