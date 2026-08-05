"""Single-call dashboard aggregate for the home page."""
from __future__ import annotations

from datetime import date

from sqlalchemy import case, desc, func
from sqlalchemy.orm import Session, defer

from ..models import (
    ActivityEvent,
    ApprovalWorkflow,
    Clause,
    Contract,
    ContractVersion,
    Deadline,
    Extraction,
    Negotiation,
    Obligation,
    PaymentMilestone,
    ReviewRequest,
    SignatureRequest,
)
from .approvals import approval_summary
from .deadlines import deadline_summary, serialize_deadline
from .payments import _extr_milestones_by_seq, payments_summary, serialize_milestone
from .reviews import reviews_dashboard_summary
from .signature import signature_summary


def _iso(dt):
    return dt.isoformat() if dt else None


def _serialize_contract_row(c: Contract, obl: dict, version_stats: dict) -> dict:
    vs = version_stats.get(c.id, {})
    return {
        "id": str(c.id),
        "title": c.title,
        "type": c.type,
        "relationship_type": c.relationship_type,
        "contract_category": c.contract_category,
        "supported": c.supported,
        "party_b": c.party_b,
        "value_sar": float(c.value_sar) if c.value_sar is not None else None,
        "status": c.status,
        "stage": c.stage or "negotiation",
        "created_at": _iso(c.created_at),
        "current_version_number": vs.get("current_version_number"),
        "total_versions": vs.get("total_versions", 0),
        "obligation_counts": obl,
    }


def _version_stats_for_contracts(db: Session, contract_ids: list) -> dict:
    if not contract_ids:
        return {}
    totals = (
        db.query(
            ContractVersion.contract_id,
            func.count(ContractVersion.id).label("total"),
            func.max(ContractVersion.version_number).label("max_num"),
        )
        .filter(ContractVersion.contract_id.in_(contract_ids))
        .group_by(ContractVersion.contract_id)
        .all()
    )
    current = (
        db.query(ContractVersion.contract_id, ContractVersion.version_number)
        .filter(ContractVersion.contract_id.in_(contract_ids), ContractVersion.is_current.is_(True))
        .all()
    )
    cur_map = {row.contract_id: row.version_number for row in current}
    out = {}
    for cid, total, max_num in totals:
        out[cid] = {
            "total_versions": int(total or 0),
            "current_version_number": cur_map.get(cid, max_num),
        }
    return out


def build_dashboard_summary(db: Session) -> dict:
    # Defer raw_text (~29KB avg per row) — never needed for dashboard KPIs.
    contracts = (
        db.query(Contract)
        .options(defer(Contract.raw_text))
        .order_by(Contract.created_at.desc())
        .all()
    )
    total = len(contracts)
    active = sum(1 for c in contracts if c.status in ("ready", "needs_review"))
    negotiations = sum(1 for c in contracts if (c.stage or "negotiation") == "negotiation")
    completed = sum(1 for c in contracts if c.stage == "active")
    rejected = sum(1 for c in contracts if c.stage in ("rejected", "declined"))

    obligation_rows = (
        db.query(
            Obligation.contract_id,
            func.sum(case((Obligation.status == "pending", 1), else_=0)).label("pending"),
            func.sum(case((Obligation.status == "overdue", 1), else_=0)).label("overdue"),
        )
        .group_by(Obligation.contract_id)
        .all()
    )
    obl_by_id = {
        row.contract_id: {"pending": int(row.pending or 0), "overdue": int(row.overdue or 0)}
        for row in obligation_rows
    }

    recent_contracts = [
        _serialize_contract_row(
            c,
            obl_by_id.get(c.id, {"pending": 0, "overdue": 0}),
            {},
        )
        for c in contracts[:8]
    ]

    activity_rows = (
        db.query(ActivityEvent, Contract.title)
        .join(Contract, Contract.id == ActivityEvent.contract_id)
        .order_by(desc(ActivityEvent.created_at))
        .limit(15)
        .all()
    )
    recent_activity = [
        {
            "id": str(ev.id),
            "contract_id": str(ev.contract_id),
            "contract_title": title,
            "event_type": ev.event_type,
            "actor": ev.actor,
            "role": ev.role,
            "comment": ev.comment,
            "metadata": ev.event_metadata,
            "created_at": _iso(ev.created_at),
        }
        for ev, title in activity_rows
    ]

    ready_ids = [c.id for c in contracts if c.status in ("ready", "needs_review")][:40]
    contract_titles = {c.id: c.title for c in contracts}
    contract_by_id = {c.id: c for c in contracts}

    all_deadlines: list[dict] = []
    payments_agg = {
        "total": 0,
        "claimable_sar": 0.0,
        "blocked_sar": 0.0,
        "overdue_sar": 0.0,
        "paid_sar": 0.0,
        "needs_review_count": 0,
    }
    risk_by_contract: dict = {}

    if ready_ids:
        today = date.today()
        deadline_rows = db.query(Deadline).filter(Deadline.contract_id.in_(ready_ids)).all()
        clauses = db.query(Clause).filter(Clause.contract_id.in_(ready_ids)).all()
        clause_by_id = {cl.id: cl for cl in clauses}
        extractions = db.query(Extraction).filter(Extraction.contract_id.in_(ready_ids)).all()
        extr_by_contract: dict = {}
        for e in extractions:
            extr_by_contract.setdefault(e.contract_id, []).append(e)

        def extr_map_for(cid):
            from .deadlines import _extr_by_clause

            return _extr_by_clause(extr_by_contract.get(cid, []))

        for d in deadline_rows:
            clause = clause_by_id.get(d.source_clause_id) if d.source_clause_id else None
            extr_item = extr_map_for(d.contract_id).get(str(d.source_clause_id)) if d.source_clause_id else None
            ser = serialize_deadline(d, today, clause, extr_item)
            ser["_contract_id"] = str(d.contract_id)
            ser["_contract_title"] = contract_titles.get(d.contract_id, "")
            all_deadlines.append(ser)

        milestone_rows = db.query(PaymentMilestone).filter(PaymentMilestone.contract_id.in_(ready_ids)).all()
        ms_by_contract: dict = {}
        for row in milestone_rows:
            ms_by_contract.setdefault(row.contract_id, []).append(row)
        for cid in ready_ids:
            ms_rows = ms_by_contract.get(cid, [])
            if not ms_rows:
                continue
            by_seq = _extr_milestones_by_seq(extr_by_contract.get(cid, []))
            cid_clauses = {cl.id: cl for cl in clauses if cl.contract_id == cid}
            ms = []
            for row in ms_rows:
                extr_item = by_seq.get(row.seq)
                clause = cid_clauses.get(row.source_clause_id) if row.source_clause_id else None
                ms.append(serialize_milestone(row, today, extr_item, clause))
            ps = payments_summary(ms, contract_by_id.get(cid))
            for k in ("total", "needs_review_count"):
                payments_agg[k] += ps.get(k, 0)
            for k in ("claimable_sar", "blocked_sar", "overdue_sar", "paid_sar"):
                payments_agg[k] += ps.get(k, 0.0)

    for cid in ready_ids:
        dl = [d for d in all_deadlines if d.get("_contract_id") == str(cid)]
        rs = 0
        for d in dl:
            if d.get("status") in ("missed", "time_barred") or (
                d.get("days_remaining") is not None and d["days_remaining"] < 0
            ):
                rs += 10
            elif d.get("severity") == "critical" and d.get("days_remaining") is not None and d["days_remaining"] <= 30:
                rs += 8
            elif d.get("severity") == "critical":
                rs += 5
            if d.get("needs_review"):
                rs += 3
        if rs:
            risk_by_contract[cid] = rs

    def _deadline_overdue(d: dict) -> bool:
        if d.get("status") in ("missed", "time_barred"):
            return True
        if d.get("days_remaining") is not None and d["days_remaining"] < 0:
            return True
        return False

    overdue_list = []
    upcoming_list = []
    for d in all_deadlines:
        cid = d.get("_contract_id", "")
        title = d.get("_contract_title", "")
        if _deadline_overdue(d):
            overdue_list.append({"contract_id": cid, "contract_title": title, "row": d})
        elif d.get("days_remaining") is not None and 0 <= d["days_remaining"] <= 7:
            upcoming_list.append({"contract_id": cid, "contract_title": title, "row": d})
    overdue_list.sort(key=lambda x: (x["row"].get("days_remaining") or -999))
    upcoming_list.sort(key=lambda x: (x["row"].get("days_remaining") or 999))
    risk_contracts = sorted(
        [{"id": str(cid), "title": contract_titles.get(cid, ""), "score": sc} for cid, sc in risk_by_contract.items()],
        key=lambda x: -x["score"],
    )

    reviews_items = reviews_dashboard_summary(db, skip_expire=True)
    pending_reviews = sum(1 for r in reviews_items if r.get("status") in ("sent", "opened"))

    appr = approval_summary(db)
    sig = signature_summary(db)

    kpis = {
        "total_contracts": total,
        "active": active,
        "negotiations": negotiations,
        "pending_reviews": pending_reviews,
        "awaiting_legal": appr.get("pending_legal", 0),
        "awaiting_finance": appr.get("pending_finance", 0),
        "awaiting_executive": appr.get("pending_executive", 0),
        "ready_to_sign": sig.get("awaiting_signature", 0),
        "completed": completed,
        "rejected": rejected + sig.get("declined_requests", 0),
    }

    return {
        "kpis": kpis,
        "recent_contracts": recent_contracts,
        "recent_activity": recent_activity,
        "deadlines_summary": deadline_summary(all_deadlines),
        "payments_summary": payments_agg,
        "reviews_summary": {"items": reviews_items},
        "approvals_summary": appr,
        "signature_summary": sig,
        "aggregate": {
            "total": total,
            "active": active,
            "upcoming7": len(upcoming_list),
            "overdue": len(overdue_list),
            "claimable_sar": payments_agg["claimable_sar"],
            "high_risk_count": sum(1 for r in risk_contracts if r["score"] >= 8),
            "overdue_list": overdue_list[:20],
            "upcoming_list": upcoming_list[:20],
            "risk_contracts": risk_contracts[:20],
        },
    }


def workflow_summaries_by_contract(db: Session) -> dict:
    """Canonical latest workflow statuses per contract using bulk queries."""
    out: dict = {}

    def ensure(cid):
        if cid not in out:
            out[cid] = {
                "review_status": None,
                "negotiation_status": None,
                "approval_status": None,
                "signature_status": None,
            }

    review_rows = (
        db.query(ReviewRequest)
        .order_by(ReviewRequest.contract_id, ReviewRequest.created_at.desc(), ReviewRequest.id.desc())
        .all()
    )
    seen_review: set = set()
    for r in review_rows:
        if r.contract_id in seen_review:
            continue
        seen_review.add(r.contract_id)
        ensure(r.contract_id)
        out[r.contract_id]["review_status"] = r.status

    negotiation_rows = (
        db.query(Negotiation)
        .order_by(
            Negotiation.contract_id,
            Negotiation.updated_at.desc(),
            Negotiation.created_at.desc(),
            Negotiation.id.desc(),
        )
        .all()
    )
    first_negotiation: dict = {}
    active_negotiation: dict = {}
    for negotiation in negotiation_rows:
        first_negotiation.setdefault(negotiation.contract_id, negotiation)
        if negotiation.workflow_status not in {"accepted", "closed"}:
            active_negotiation.setdefault(negotiation.contract_id, negotiation)
    for cid, latest in first_negotiation.items():
        selected = active_negotiation.get(cid, latest)
        ensure(cid)
        out[cid]["negotiation_status"] = selected.workflow_status

    wf_rows = (
        db.query(ApprovalWorkflow)
        .order_by(ApprovalWorkflow.contract_id, ApprovalWorkflow.created_at.desc(), ApprovalWorkflow.id.desc())
        .all()
    )
    seen_wf: set = set()
    for w in wf_rows:
        if w.contract_id in seen_wf:
            continue
        seen_wf.add(w.contract_id)
        ensure(w.contract_id)
        out[w.contract_id]["approval_status"] = w.status

    sig_rows = (
        db.query(SignatureRequest)
        .order_by(SignatureRequest.contract_id, SignatureRequest.created_at.desc(), SignatureRequest.id.desc())
        .all()
    )
    seen_sig: set = set()
    for s in sig_rows:
        if s.contract_id in seen_sig:
            continue
        seen_sig.add(s.contract_id)
        ensure(s.contract_id)
        out[s.contract_id]["signature_status"] = s.status

    return out
