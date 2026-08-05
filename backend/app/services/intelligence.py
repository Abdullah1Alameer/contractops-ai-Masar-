"""Contract intelligence rebuild orchestrator."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..models import Contract, Obligation
from .approvals import log_activity
from .date_semantics import sync_contract_date_semantics
from .deadlines import build_deadlines_for_contract, list_deadlines_for_contract
from .negotiation_opportunities import (
    list_negotiation_opportunities,
    rebuild_negotiation_opportunities,
)
from .payments import build_payment_milestones_for_contract, list_payment_milestones_for_contract
from .risk_engine import rebuild_risk_findings, serialize_risk

ALL_TARGETS = frozenset(
    {
        "temporal_rules",
        "deadlines",
        "financial_obligations",
        "obligations",
        "risk",
        "negotiation",
        "date_semantics",
    }
)


def _rebuild_obligations(contract_id, db: Session) -> int:
    contract = db.get(Contract, contract_id)
    if contract is None:
        raise ValueError("contract_not_found")
    count = 0
    for o in db.query(Obligation).filter_by(contract_id=contract_id):
        if o.manual_status:
            continue
        desc = (o.description or "").lower()
        if "wage" in desc or "pay" in desc and "month" in desc:
            o.trigger_type = "recurring"
            o.trigger_event = "monthly_payroll"
            o.title = o.title or "Pay monthly wage"
            o.suggested_evidence = o.suggested_evidence or ["payroll_record", "bank_transfer_receipt"]
        elif "settle" in desc or "entitlement" in desc:
            o.trigger_type = "event"
            o.trigger_event = "contract_end_or_termination"
            o.title = o.title or "Settle final entitlements"
        else:
            o.trigger_type = o.trigger_type or "immediate"
            o.title = o.title or (o.description[:80] if o.description else "Obligation")
        if not o.beneficiary:
            if (o.responsible_party or "").lower().startswith("second"):
                o.beneficiary = "first_party"
            else:
                o.beneficiary = "second_party"
        o.contract_required_evidence = o.contract_required_evidence or []
        count += 1
    db.flush()
    return count


def rebuild_intelligence(
    contract_id,
    db: Session,
    targets: list[str] | None = None,
) -> dict[str, Any]:
    contract = db.get(Contract, contract_id)
    if contract is None:
        raise ValueError("contract_not_found")

    chosen = set(targets or ALL_TARGETS)
    invalid = chosen - ALL_TARGETS
    if invalid:
        raise ValueError("invalid_targets")

    summary: dict[str, Any] = {"contract_id": str(contract_id), "targets": sorted(chosen), "results": {}}

    if "date_semantics" in chosen or "temporal_rules" in chosen:
        facts = sync_contract_date_semantics(contract, db)
        summary["results"]["date_semantics"] = {"inconsistencies": len(facts.get("inconsistencies") or [])}

    if "deadlines" in chosen or "temporal_rules" in chosen:
        rows = build_deadlines_for_contract(contract_id, db)
        summary["results"]["deadlines"] = {"generated": len(rows)}

    if "financial_obligations" in chosen:
        ms = build_payment_milestones_for_contract(contract_id, db)
        summary["results"]["financial_obligations"] = {"generated": len(ms)}

    if "obligations" in chosen:
        n = _rebuild_obligations(contract_id, db)
        summary["results"]["obligations"] = {"updated": n}

    if "risk" in chosen:
        risk = rebuild_risk_findings(contract_id, db)
        summary["results"]["risk"] = {"score": risk.get("score"), "items": len(risk.get("breakdown") or [])}

    if "negotiation" in chosen:
        opps = rebuild_negotiation_opportunities(contract_id, db)
        summary["results"]["negotiation"] = {"generated": len(opps)}

    log_activity(
        db,
        contract_id,
        "intelligence_rebuilt",
        metadata={"targets": sorted(chosen), "summary": summary["results"]},
    )
    db.commit()
    return summary


def get_intelligence_snapshot(contract_id, db: Session) -> dict[str, Any]:
    contract = db.get(Contract, contract_id)
    if contract is None:
        raise ValueError("contract_not_found")
    return {
        "date_facts": contract.date_facts,
        "deadlines": list_deadlines_for_contract(contract_id, db),
        "milestones": list_payment_milestones_for_contract(contract_id, db),
        "risk": serialize_risk(contract_id, db),
        "negotiation_opportunities": list_negotiation_opportunities(contract_id, db),
    }
