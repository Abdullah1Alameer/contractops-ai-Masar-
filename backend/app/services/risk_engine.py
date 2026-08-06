"""Deterministic explainable risk scoring (risk-v2)."""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ..models import Clause, Contract, Deadline, Obligation, PaymentMilestone, RiskFinding
from .date_semantics import sync_contract_date_semantics

CALCULATION_VERSION = "risk-v2"

CATEGORY_POINTS = {
    "missing_date": 2,
    "temporal": 2,
    "financial": 3,
    "operational": 2,
    "ambiguous_clause": 2,
    "compliance": 2,
}


def _level(score: int) -> str:
    if score >= 60:
        return "critical"
    if score >= 40:
        return "high"
    if score >= 20:
        return "medium"
    return "low"


def rebuild_risk_findings(contract_id, db: Session) -> dict[str, Any]:
    contract = db.get(Contract, contract_id)
    if contract is None:
        raise ValueError("contract_not_found")

    sync_contract_date_semantics(contract, db)
    db.query(RiskFinding).filter(
        RiskFinding.contract_id == contract_id,
        RiskFinding.generated.is_(True),
    ).delete(synchronize_session=False)

    seen: set[tuple[str, str, str | None]] = set()
    rows: list[RiskFinding] = []

    def add(category: str, code: str, explanation: str, explanation_ar: str, link_tab: str, clause_id=None):
        key = (category, code, str(clause_id) if clause_id else None)
        if key in seen:
            return
        seen.add(key)
        pts = CATEGORY_POINTS.get(category, 2)
        r = RiskFinding(
            id=_uuid.uuid4(),
            contract_id=contract_id,
            category=category,
            code=code,
            points=pts,
            count=1,
            explanation=explanation,
            explanation_ar=explanation_ar,
            link_tab=link_tab,
            source_clause_id=clause_id,
            calculation_version=CALCULATION_VERSION,
            generated=True,
        )
        db.add(r)
        rows.append(r)

    facts = contract.date_facts if isinstance(contract.date_facts, dict) else {}
    for inc in facts.get("inconsistencies") or []:
        add(
            "missing_date",
            inc.get("code") or "date_inconsistency",
            inc.get("explanation") or "Date inconsistency detected.",
            inc.get("explanation") or "تعارض في التواريخ.",
            "deadlines",
        )

    for d in db.query(Deadline).filter_by(contract_id=contract_id):
        if d.needs_review:
            add(
                "temporal",
                f"deadline_{d.event_type or d.type}",
                d.calculation_explanation or "One deadline could not be resolved.",
                d.calculation_explanation_ar or "تعذر حل موعد نهائي واحد.",
                "deadlines",
                d.source_clause_id,
            )

    for m in db.query(PaymentMilestone).filter_by(contract_id=contract_id):
        if m.role == "component":
            continue
        if m.status == "needs_review":
            add(
                "financial",
                f"milestone_{m.seq}",
                "One financial obligation requires review.",
                "التزام مالي واحد يتطلب مراجعة.",
                "milestones",
                m.source_clause_id,
            )

    for o in db.query(Obligation).filter_by(contract_id=contract_id):
        if o.status == "needs_review":
            add(
                "operational",
                f"obligation_{o.id}",
                "One obligation requires review.",
                "التزام واحد يتطلب مراجعة.",
                "obligations",
                o.source_clause_id,
            )

    db.flush()
    return serialize_risk(contract_id, db)


def serialize_risk(contract_id, db: Session) -> dict[str, Any]:
    findings = db.query(RiskFinding).filter_by(contract_id=contract_id).all()
    breakdown_map: dict[str, dict] = {}
    for f in findings:
        cat = f.category
        if cat not in breakdown_map:
            breakdown_map[cat] = {
                "category": cat,
                "count": 0,
                "points": 0,
                # Both languages, so the frontend can localize the category
                # rollup exactly like it already does for each individual
                # finding, instead of only ever showing whichever language
                # happened to be recorded first for this category.
                "explanation": f.explanation or "",
                "explanation_ar": f.explanation_ar or "",
            }
        breakdown_map[cat]["count"] += f.count
        breakdown_map[cat]["points"] += f.points

    breakdown = list(breakdown_map.values())
    score = sum(b["points"] for b in breakdown)

    # Resolve each finding's source clause (when it has one) into the same
    # {clause_ref, quote, page, char_start, char_end} shape obligations
    # already expose — a risk finding was previously only traceable to an
    # opaque source_clause_id with no way for the UI to show the original
    # text or jump to it. See docs/analysis-traceability-audit.md.
    clause_ids = {f.source_clause_id for f in findings if f.source_clause_id}
    clauses = {}
    if clause_ids:
        clauses = {cl.id: cl for cl in db.query(Clause).filter(Clause.id.in_(clause_ids))}

    return {
        "score": score,
        "level": _level(score),
        "breakdown": breakdown,
        "calculation_version": CALCULATION_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "findings": [
            {
                "id": str(f.id),
                "category": f.category,
                "code": f.code,
                "points": f.points,
                "count": f.count,
                "explanation": f.explanation,
                "explanation_ar": f.explanation_ar,
                "link_tab": f.link_tab,
                "source_clause_id": str(f.source_clause_id) if f.source_clause_id else None,
                "source": (
                    {
                        "clause_ref": clauses[f.source_clause_id].clause_ref,
                        "quote": clauses[f.source_clause_id].quote,
                        "page": clauses[f.source_clause_id].page,
                        "char_start": clauses[f.source_clause_id].char_start,
                        "char_end": clauses[f.source_clause_id].char_end,
                    }
                    if f.source_clause_id and f.source_clause_id in clauses
                    else None
                ),
            }
            for f in findings
        ],
    }
