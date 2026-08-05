"""Client Review Portal — secure links, dossier aggregation, decisions (no SMTP)."""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..config import REVIEW_BASE_URL
from ..models import (
    Clause,
    Contract,
    Extraction,
    FlowdownFinding,
    Obligation,
    ReviewComment,
    ReviewRequest,
    ReviewResponse,
)
from .deadlines import deadline_summary, list_deadlines_for_contract
from .flowdown import list_flowdown_for_pair
from .payments import list_payment_milestones_for_contract, payments_summary
from . import versions as ver_svc

DEFAULT_EXPIRY_DAYS = 14
_DECISION_STATUSES = frozenset({"approved", "rejected", "changes_requested"})
_TERMINAL_STATUSES = _DECISION_STATUSES | frozenset({"expired"})


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def _num(v):
    return float(v) if v is not None else None


def review_link(token: str) -> str:
    base = REVIEW_BASE_URL.rstrip("/")
    return f"{base}/review/{token}"


def expire_if_needed(req: ReviewRequest, db: Session) -> ReviewRequest:
    if req.status in _TERMINAL_STATUSES:
        return req
    exp = req.expires_at
    if exp is not None:
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < _utcnow():
            req.status = "expired"
            db.commit()
            db.refresh(req)
    return req


def can_respond(req: ReviewRequest) -> bool:
    return req.status in ("sent", "opened")


def mark_opened(req: ReviewRequest, db: Session) -> None:
    if req.status == "sent":
        req.status = "opened"
        req.opened_at = _utcnow()
        db.commit()
        from .approvals import log_activity
        from .versions import current_version

        cur = current_version(req.contract_id, db)
        log_activity(
            db,
            req.contract_id,
            "review_opened",
            metadata={
                "version_number": cur.version_number if cur else None,
                "review_request_id": str(req.id),
            },
        )


def _contract_brief(c: Contract) -> dict:
    return {
        "id": str(c.id),
        "title": c.title,
        "party_a": c.party_a,
        "party_b": c.party_b,
        "value_sar": _num(c.value_sar),
        "start_date": c.start_date.isoformat() if c.start_date else None,
        "end_date": c.end_date.isoformat() if c.end_date else None,
        "governing_law": c.governing_law,
        "status": c.status,
        "contract_category": c.contract_category,
    }


def _serialize_obligations(contract_id, db: Session) -> list[dict]:
    clauses = {cl.id: cl for cl in db.query(Clause).filter_by(contract_id=contract_id)}
    out = []
    for o in db.query(Obligation).filter_by(contract_id=contract_id).order_by(Obligation.due_date.asc().nullslast()):
        clause = clauses.get(o.source_clause_id)
        out.append(
            {
                "id": str(o.id),
                "description": o.description,
                "responsible_party": o.responsible_party,
                "due_date": o.due_date.isoformat() if o.due_date else None,
                "penalty_text": o.penalty_text,
                "status": o.status,
                "clause_ref": clause.clause_ref if clause else None,
                "page": clause.page if clause else None,
            }
        )
    return out


def _comparison_for_contract(contract_id, db: Session) -> dict | None:
    row = (
        db.query(FlowdownFinding)
        .filter(
            or_(
                FlowdownFinding.main_contract_id == contract_id,
                FlowdownFinding.subcontract_id == contract_id,
            )
        )
        .order_by(FlowdownFinding.created_at.desc())
        .first()
    )
    if row is None:
        return None
    return list_flowdown_for_pair(row.main_contract_id, row.subcontract_id, db)


def _penalties_from_extractions(contract_id, db: Session) -> list:
    extr = db.query(Extraction).filter_by(contract_id=contract_id, field_name="penalties").first()
    if extr and isinstance(extr.value_json, list):
        return extr.value_json
    return []


def build_ai_summary(
    contract: Contract,
    obligations: list[dict],
    timeline_summary: dict,
    payments_sum: dict,
    comparison: dict | None,
) -> str:
    lines = []
    if contract.title:
        lines.append(f"Contract: {contract.title}")
    if contract.party_a or contract.party_b:
        lines.append(f"Parties: {contract.party_a or '—'} / {contract.party_b or '—'}")
    if contract.value_sar is not None:
        lines.append(f"Contract value (SAR): {_num(contract.value_sar):,.0f}")
    if contract.governing_law:
        lines.append(f"Governing law: {contract.governing_law}")
    if contract.start_date or contract.end_date:
        lines.append(
            f"Term: {contract.start_date or '—'} to {contract.end_date or '—'}"
        )
    lines.append(f"Obligations tracked: {len(obligations)}")
    if timeline_summary:
        lines.append(
            f"Timeline — within 14 days: {timeline_summary.get('within_14_days', 0)}, "
            f"critical: {timeline_summary.get('critical', 0)}, "
            f"missed/time-barred: {timeline_summary.get('missed_or_time_barred', 0)}"
        )
    if payments_sum:
        lines.append(
            f"Payments — milestones: {payments_sum.get('total', 0)}, "
            f"claimable SAR: {payments_sum.get('claimable_sar', 0)}"
        )
    if comparison and comparison.get("summary"):
        s = comparison["summary"]
        lines.append(
            f"Comparison coverage: {s.get('coverage_pct', 0)}% — "
            f"critical findings: {s.get('critical_count', 0)}"
        )
    return "\n".join(lines) if lines else "No summary available yet."


def build_risk_summary(
    contract_id,
    db: Session,
    timeline_summary: dict,
    comparison: dict | None,
    penalties: list,
) -> dict:
    items: list[dict] = []
    for p in penalties:
        items.append(
            {
                "type": "penalty",
                "label": p.get("type") or "Penalty",
                "detail": p.get("rate") or p.get("cap") or "",
                "severity": "medium",
            }
        )
    if timeline_summary.get("missed_or_time_barred", 0) > 0:
        items.append(
            {
                "type": "deadline",
                "label": "Missed or time-barred deadlines",
                "detail": str(timeline_summary.get("missed_or_time_barred")),
                "severity": "high",
            }
        )
    if timeline_summary.get("critical", 0) > 0:
        items.append(
            {
                "type": "deadline",
                "label": "Critical upcoming deadlines",
                "detail": str(timeline_summary.get("critical")),
                "severity": "critical",
            }
        )
    if comparison and comparison.get("findings"):
        for f in comparison["findings"]:
            if f.get("risk_level") in ("critical", "high"):
                items.append(
                    {
                        "type": "comparison",
                        "label": f.get("category") or "Clause",
                        "detail": f.get("status") or "",
                        "severity": f.get("risk_level") or "medium",
                    }
                )
    return {"items": items[:30], "count": len(items)}


def build_review_dossier(contract_id, db: Session) -> dict:
    c = db.get(Contract, contract_id)
    if c is None:
        raise ValueError("not_found")

    obligations = _serialize_obligations(contract_id, db)
    deadlines = list_deadlines_for_contract(contract_id, db)
    timeline_summary = deadline_summary(deadlines)
    milestones = list_payment_milestones_for_contract(contract_id, db)
    pay_sum = payments_summary(milestones, c)
    comparison = _comparison_for_contract(contract_id, db)
    penalties = _penalties_from_extractions(contract_id, db)

    ai_summary = build_ai_summary(c, obligations, timeline_summary, pay_sum, comparison)
    risks = build_risk_summary(contract_id, db, timeline_summary, comparison, penalties)

    notice_extr = db.query(Extraction).filter_by(contract_id=contract_id, field_name="notice_periods").first()
    notices = notice_extr.value_json if notice_extr and isinstance(notice_extr.value_json, list) else []

    return {
        "contract": _contract_brief(c),
        "ai_summary": ai_summary,
        "notices": notices,
        "obligations": obligations,
        "timeline": {"deadlines": deadlines, "summary": timeline_summary},
        "payments": {"milestones": milestones, "summary": pay_sum},
        "comparison": comparison,
        "risks": risks,
        "penalties": penalties,
    }


def build_email_template(req: ReviewRequest, contract: Contract, link: str) -> dict:
    title = contract.title or "Contract"
    subject = f"Contract review request: {title}"
    body = (
        f"Hello {req.recipient_name},\n\n"
        f"You have been invited to review a contract: {title}.\n\n"
    )
    if req.message:
        body += f"Message from sender:\n{req.message}\n\n"
    body += (
        f"Please open the secure link below to read the summary, risks, and key terms, "
        f"then approve, reject, or request changes.\n\n"
        f"{link}\n\n"
        f"This link expires on {_iso(req.expires_at)}.\n"
    )
    return {"subject": subject, "body": body, "review_link": link}


def serialize_review_request(req: ReviewRequest, db: Session, *, include_token: bool = False) -> dict:
    comments = (
        db.query(ReviewComment)
        .filter_by(review_request_id=req.id)
        .order_by(ReviewComment.created_at.asc())
        .all()
    )
    response = db.query(ReviewResponse).filter_by(review_request_id=req.id).first()
    out = {
        "id": str(req.id),
        "contract_id": str(req.contract_id),
        "recipient_name": req.recipient_name,
        "recipient_email": req.recipient_email,
        "sender_name": req.sender_name,
        "sender_email": req.sender_email,
        "message": req.message,
        "status": req.status,
        "expires_at": _iso(req.expires_at),
        "opened_at": _iso(req.opened_at),
        "responded_at": _iso(req.responded_at),
        "created_at": _iso(req.created_at),
        "comments": [
            {
                "id": str(cm.id),
                "clause_ref": cm.clause_ref,
                "page": cm.page,
                "comment": cm.comment,
                "created_at": _iso(cm.created_at),
            }
            for cm in comments
        ],
        "decision": response.decision if response else None,
        "overall_comment": response.overall_comment if response else None,
        "version_id": str(req.version_id) if req.version_id else None,
        "is_stale": ver_svc.is_stale_workflow(req, req.contract_id, db),
    }
    if include_token:
        out["token"] = req.token
        out["review_link"] = review_link(req.token)
    return out


def create_review_request(
    contract: Contract,
    db: Session,
    *,
    recipient_name: str,
    recipient_email: str,
    message: str | None = None,
    sender_name: str | None = None,
    sender_email: str | None = None,
    expires_in_days: int = DEFAULT_EXPIRY_DAYS,
) -> ReviewRequest:
    if contract.status not in ("ready", "needs_review"):
        raise ValueError("extraction_not_complete")
    if contract.supported is False:
        raise ValueError("contract_not_supported")

    token = generate_token()
    while db.query(ReviewRequest).filter_by(token=token).first():
        token = generate_token()

    req = ReviewRequest(
        id=uuid.uuid4(),
        contract_id=contract.id,
        token=token,
        recipient_name=recipient_name.strip(),
        recipient_email=recipient_email.strip(),
        sender_name=sender_name,
        sender_email=sender_email,
        message=message,
        status="sent",
        expires_at=_utcnow() + timedelta(days=max(1, min(expires_in_days, 90))),
    )
    db.add(req)
    from .approvals import log_activity
    from .versions import current_version

    cur = current_version(contract.id, db)
    if cur:
        req.version_id = cur.id
        log_activity(db, contract.id, "version_sent_for_review", metadata={"version_number": cur.version_number})
        log_activity(
            db,
            contract.id,
            "review_sent",
            actor=sender_name,
            metadata={"version_number": cur.version_number, "review_request_id": str(req.id)},
        )
    db.commit()
    db.refresh(req)
    return req


def get_request_by_token(token: str, db: Session) -> ReviewRequest | None:
    return db.query(ReviewRequest).filter_by(token=token).first()


def build_public_payload(req: ReviewRequest, db: Session) -> dict:
    expire_if_needed(req, db)
    mark_opened(req, db)
    dossier = build_review_dossier(req.contract_id, db)
    serialized = serialize_review_request(req, db)
    return {
        **dossier,
        "recipient_name": req.recipient_name,
        "status": req.status,
        "expires_at": serialized["expires_at"],
        "opened_at": serialized["opened_at"],
        "responded_at": serialized["responded_at"],
        "comments": serialized["comments"],
        "decision": serialized["decision"],
        "overall_comment": serialized["overall_comment"],
        "read_only": not can_respond(req),
    }


def record_decision(
    req: ReviewRequest,
    db: Session,
    decision: str,
    overall_comment: str | None = None,
) -> ReviewRequest:
    expire_if_needed(req, db)
    if not can_respond(req):
        raise ValueError("review_closed")
    if decision not in ("approve", "reject", "changes_requested"):
        raise ValueError("invalid_decision")
    if db.query(ReviewResponse).filter_by(review_request_id=req.id).first():
        raise ValueError("review_closed")

    status_map = {
        "approve": "approved",
        "reject": "rejected",
        "changes_requested": "changes_requested",
    }
    db.add(
        ReviewResponse(
            id=uuid.uuid4(),
            review_request_id=req.id,
            decision=decision,
            overall_comment=overall_comment,
        )
    )
    req.status = status_map[decision]
    req.responded_at = _utcnow()
    from .approvals import log_activity
    from .versions import current_version

    cur = current_version(req.contract_id, db)
    event_map = {
        "approved": "review_approved",
        "rejected": "review_rejected",
        "changes_requested": "review_changes_requested",
    }
    log_activity(
        db,
        req.contract_id,
        event_map.get(req.status, "review_completed"),
        metadata={
            "version_number": cur.version_number if cur else None,
            "review_request_id": str(req.id),
        },
    )
    db.commit()
    db.refresh(req)
    return req


def add_comment(
    req: ReviewRequest,
    db: Session,
    comment: str,
    clause_ref: str | None = None,
    page: int | None = None,
) -> ReviewComment:
    expire_if_needed(req, db)
    if req.status == "expired":
        raise ValueError("review_expired")
    if req.status in _DECISION_STATUSES:
        raise ValueError("review_closed")

    cm = ReviewComment(
        id=uuid.uuid4(),
        review_request_id=req.id,
        clause_ref=clause_ref,
        page=page,
        comment=comment.strip(),
    )
    db.add(cm)
    db.commit()
    db.refresh(cm)
    return cm


def list_reviews_for_contract(contract_id, db: Session) -> list[dict]:
    rows = (
        db.query(ReviewRequest)
        .filter_by(contract_id=contract_id)
        .order_by(ReviewRequest.created_at.desc())
        .all()
    )
    return [serialize_review_request(r, db, include_token=True) for r in rows]


def reviews_dashboard_summary(db: Session, *, skip_expire: bool = False) -> list[dict]:
    rows = (
        db.query(ReviewRequest, Contract.title)
        .join(Contract, Contract.id == ReviewRequest.contract_id)
        .order_by(ReviewRequest.created_at.desc())
        .limit(50)
        .all()
    )
    out = []
    for req, title in rows:
        if not skip_expire:
            expire_if_needed(req, db)
        out.append(
            {
                **serialize_review_request(req, db),
                "contract_title": title,
            }
        )
    return out
