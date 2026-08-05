"""Prompt B — AI Negotiation Assistant (strict JSON output)."""
from .schemas import _obj

NEGOTIATION_SYSTEM = """You are a senior commercial contract negotiation advisor supporting in-house legal teams.

STRICT RULES:
- Use ONLY facts from the provided contract metadata, clause text, reviewer comment, and review decision.
- NEVER invent parties, amounts, dates, or obligations not in the input.
- NEVER rewrite unrelated clauses or change the fundamental intent of the agreement without explicit negotiation framing.
- Always explain WHY in professional legal/business language.
- Produce counter-clause wording suitable for insertion (English in counter_clause, Arabic in arabic_counter_clause).
- recommendation must be exactly one of: accept_client, negotiate, reject_client.
- risk_level must be exactly one of: low, medium, high, critical.
- pros and cons must be short bullet strings (2-5 each) grounded in the inputs.
- If the reviewer comment is vague, state assumptions clearly in reasoning without fabricating contract facts.
"""

NEGOTIATION_SCHEMA = {
    "name": "negotiation_recommendation",
    "strict": True,
    "schema": _obj({
        "summary": {"type": "string"},
        "business_impact": {"type": "string"},
        "legal_impact": {"type": "string"},
        "risk_level": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
        "recommendation": {
            "type": "string",
            "enum": ["accept_client", "negotiate", "reject_client"],
        },
        "reasoning": {"type": "string"},
        "counter_clause": {"type": "string"},
        "arabic_counter_clause": {"type": "string"},
        "pros": {"type": "array", "items": {"type": "string"}},
        "cons": {"type": "array", "items": {"type": "string"}},
    }),
}


def build_negotiation_prompt(context: dict) -> str:
    lines = [
        "Analyze the following client review feedback and produce a negotiation recommendation.",
        "",
        "=== CONTRACT ===",
        f"Title: {context.get('contract_title') or '—'}",
        f"Parties: {context.get('party_a') or '—'} / {context.get('party_b') or '—'}",
        f"Category: {context.get('contract_category') or '—'}",
        f"Governing law: {context.get('governing_law') or '—'}",
        "",
        "=== REVIEW ===",
        f"Review status: {context.get('review_status') or '—'}",
        f"Reviewer decision: {context.get('reviewer_decision') or '—'}",
        f"Overall review comment: {context.get('overall_comment') or '—'}",
        "",
        "=== CLAUSE ===",
        f"Clause ref: {context.get('clause_ref') or '—'}",
        f"Original clause text:\n{context.get('original_clause') or '(not provided)'}",
        "",
        "=== REVIEWER COMMENT (this clause) ===",
        context.get("reviewer_comment") or "(none)",
        "",
        "=== CONTRACT SUMMARY (from platform) ===",
        context.get("contract_summary") or "(none)",
    ]
    return "\n".join(lines)
