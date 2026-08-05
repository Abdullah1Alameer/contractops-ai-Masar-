"""Playbook deviation engine."""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from ...models import PlaybookRule


def _parse_payment_days(text: str) -> int | None:
    m = re.search(r"(\d{1,3})\s*days", text, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"ninety|90", text, re.I)
    if m:
        return 90
    m = re.search(r"thirty|30", text, re.I)
    if m:
        return 30
    m = re.search(r"forty[- ]five|45", text, re.I)
    if m:
        return 45
    m = re.search(r"sixty|60", text, re.I)
    if m:
        return 60
    return None


def _payment_deviation(days: int | None, rule: PlaybookRule) -> str:
    if days is None:
        return "needs_review"
    pref = _parse_payment_days(rule.preferred_position or "") or 30
    fall = _parse_payment_days(rule.fallback_position or "") or 45
    unacc = _parse_payment_days(rule.unacceptable_position or "") or 61
    if days <= pref:
        return "standard"
    if days <= fall:
        return "fallback"
    if days >= unacc:
        return "unacceptable"
    return "non_standard"


def evaluate_playbook(
    db: Session,
    *,
    playbook_id,
    client_text: str,
    template_deviations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rules = db.query(PlaybookRule).filter_by(playbook_id=playbook_id).all()
    by_cat = {r.clause_category: r for r in rules}
    out: list[dict[str, Any]] = []

    for dev in template_deviations:
        cat = dev.get("clause_category") or "General"
        rule = by_cat.get(cat)
        client_pos = dev.get("client_clause") or ""
        if rule is None:
            out.append(
                {
                    "clause_category": cat,
                    "counterparty_position": client_pos,
                    "preferred_company_position": None,
                    "accepted_fallback": None,
                    "deviation_level": "needs_review",
                    "risk": "medium",
                    "required_approver": "legal",
                    "recommendation": "Manual playbook review.",
                    "source_citation": client_pos[:300],
                    "explanation": "No playbook rule for category.",
                }
            )
            continue

        deviation_level = "non_standard"
        if cat == "Payment Terms":
            days = _parse_payment_days(client_pos)
            deviation_level = _payment_deviation(days, rule)
        elif cat == "Liability" and re.search(r"unlimited", client_pos, re.I):
            deviation_level = "unacceptable"
        elif cat == "Governing Law" and re.search(r"England|New York", client_pos, re.I):
            deviation_level = "unacceptable"
        else:
            if rule.unacceptable_position and rule.unacceptable_position.lower() in client_pos.lower():
                deviation_level = "unacceptable"
            elif rule.preferred_position and rule.preferred_position.lower() in client_pos.lower():
                deviation_level = "standard"

        risk = rule.severity or "medium"
        if deviation_level == "unacceptable":
            risk = "critical" if cat == "Liability" else "high"

        rec = rule.guidance or "Counter per playbook."
        if cat == "Payment Terms" and deviation_level in ("unacceptable", "non_standard"):
            rec = f"Counter with {rule.fallback_position or '45 days'}."

        out.append(
            {
                "clause_category": cat,
                "counterparty_position": client_pos,
                "preferred_company_position": rule.preferred_position,
                "accepted_fallback": rule.fallback_position,
                "deviation_level": deviation_level,
                "risk": risk,
                "required_approver": rule.approval_required_role or "legal",
                "recommendation": rec,
                "source_citation": client_pos[:300],
                "explanation": rule.rule_name,
            }
        )

    if "Liability" not in {d["clause_category"] for d in out} and re.search(
        r"unlimited", client_text, re.I
    ):
        rule = by_cat.get("Liability")
        out.append(
            {
                "clause_category": "Liability",
                "counterparty_position": "Unlimited liability",
                "preferred_company_position": rule.preferred_position if rule else "Contract value cap",
                "accepted_fallback": rule.fallback_position if rule else None,
                "deviation_level": "unacceptable",
                "risk": "critical",
                "required_approver": rule.approval_required_role if rule else "legal",
                "recommendation": "Reject unlimited liability; cap at contract value.",
                "source_citation": "unlimited liability",
                "explanation": "Detected unlimited liability language.",
            }
        )

    return out
