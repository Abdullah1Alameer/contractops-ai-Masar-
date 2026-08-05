"""Structured negotiation opportunity detection (not keyword-only)."""
from __future__ import annotations

import re
import uuid as _uuid
from typing import Any

from sqlalchemy.orm import Session

from ..models import Clause, Contract, Extraction, NegotiationOpportunity

_AUTO_RENEW = re.compile(r"automatically\s+renew|renewed\s+for\s+an\s+equivalent|تجديد\s+تلقائي", re.I)
_SHORT_NOTICE = re.compile(r"at\s+least\s+(\d+)\s+days\s+before\s+the\s+contract\s+end", re.I)
_STATUTORY = re.compile(r"Labor\s+Law|HRSD|Ministry\s+of\s+Human\s+Resources|نظام\s+العمل|وزارة\s+الموارد", re.I)
_ONE_SIDED_TERM = re.compile(
    r"First\s+Party\s+may\s+terminate|without\s+liability\s+to\s+the\s+First\s+Party|"
    r"يحق\s+للطرف\s+الأول\s+.*(?:إنهاء|فسخ)",
    re.I,
)


def rebuild_negotiation_opportunities(contract_id, db: Session) -> list[NegotiationOpportunity]:
    contract = db.get(Contract, contract_id)
    if contract is None:
        raise ValueError("contract_not_found")

    preserved = {
        (o.category, o.clause_ref, str(o.source_clause_id))
        for o in db.query(NegotiationOpportunity).filter_by(contract_id=contract_id)
        if o.human_decision
    }

    db.query(NegotiationOpportunity).filter(
        NegotiationOpportunity.contract_id == contract_id,
        NegotiationOpportunity.generated.is_(True),
    ).delete(synchronize_session=False)

    clauses = db.query(Clause).filter_by(contract_id=contract_id).all()
    extr = {e.field_name: e.value_json for e in db.query(Extraction).filter_by(contract_id=contract_id)}
    notices = extr.get("notice_periods") or []
    out: list[NegotiationOpportunity] = []

    def add(**kwargs):
        key = (kwargs.get("category"), kwargs.get("clause_ref"), str(kwargs.get("source_clause_id")))
        if key in preserved:
            return
        row = NegotiationOpportunity(id=_uuid.uuid4(), contract_id=contract_id, generated=True, **kwargs)
        db.add(row)
        out.append(row)

    for item in notices if isinstance(notices, list) else []:
        quote = item.get("quote") or ""
        if _AUTO_RENEW.search(quote):
            m = _SHORT_NOTICE.search(quote)
            days = int(m.group(1)) if m else None
            negotiability = "negotiable"
            issue = "Automatic renewal with a short non-renewal notice window."
            if days is not None and days <= 14:
                add(
                    category="auto_renewal",
                    clause_ref=item.get("clause_ref"),
                    current_text=quote[:800],
                    issue=issue,
                    business_impact="May bind the organization beyond intended term.",
                    legal_impact="Notice window may be difficult to operationalize.",
                    financial_impact="Extended obligations if notice is missed.",
                    recommendation="negotiate",
                    suggested_counterproposal="Extend non-renewal notice or require mutual written renewal.",
                    confidence=0.85 if days else 0.7,
                    human_decision_required=True,
                    negotiability=negotiability,
                    source_clause_id=_clause_uuid(item),
                )

    for c in clauses:
        text = c.quote or ""
        if not text.strip():
            continue
        if _STATUTORY.search(text):
            continue
        if _ONE_SIDED_TERM.search(text) and not re.search(r"Second\s+Party\s+may\s+terminate", text, re.I):
            add(
                category="termination_imbalance",
                clause_ref=c.clause_ref,
                current_text=text[:800],
                issue="Termination rights appear one-sided.",
                business_impact="Limited exit flexibility for one party.",
                legal_impact="Potential imbalance; legal review recommended.",
                financial_impact="Exit costs may be uneven.",
                recommendation="legal_review",
                suggested_counterproposal="Align termination rights and notice periods for both parties.",
                confidence=0.75,
                human_decision_required=True,
                negotiability="negotiable",
                source_clause_id=c.id,
            )

    db.flush()
    return out


def _clause_uuid(item: dict) -> _uuid.UUID | None:
    cid = item.get("clause_id")
    if not cid:
        return None
    try:
        return _uuid.UUID(str(cid))
    except ValueError:
        return None


def list_negotiation_opportunities(contract_id, db: Session) -> list[dict[str, Any]]:
    rows = db.query(NegotiationOpportunity).filter_by(contract_id=contract_id).order_by(
        NegotiationOpportunity.created_at.desc()
    )
    return [serialize_opportunity(r) for r in rows]


def serialize_opportunity(row: NegotiationOpportunity) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "contract_id": str(row.contract_id),
        "category": row.category,
        "clause_ref": row.clause_ref,
        "current_text": row.current_text,
        "issue": row.issue,
        "business_impact": row.business_impact,
        "legal_impact": row.legal_impact,
        "financial_impact": row.financial_impact,
        "recommendation": row.recommendation,
        "suggested_counterproposal": row.suggested_counterproposal,
        "confidence": float(row.confidence) if row.confidence is not None else None,
        "human_decision_required": bool(row.human_decision_required),
        "negotiability": row.negotiability,
        "human_decision": row.human_decision,
        "source_clause_id": str(row.source_clause_id) if row.source_clause_id else None,
    }
