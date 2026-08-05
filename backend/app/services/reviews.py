"""Client Review Portal — secure links, dossier aggregation, decisions (no SMTP)."""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..config import REVIEW_BASE_URL
from ..models import (
    ActivityEvent,
    Clause,
    Contract,
    ContractVersion,
    Extraction,
    FlowdownFinding,
    Negotiation,
    Obligation,
    ReviewComment,
    ReviewRequest,
    ReviewResponse,
)
from . import approvals
from .deadlines import deadline_summary, list_deadlines_for_contract
from .flowdown import list_flowdown_for_pair
from .lifecycle import LifecycleEvent, LifecycleService, TransitionResult
from .outbound_messages import (
    TokenMaterial,
    create_token_material,
    hash_public_token,
    public_token_from_nonce,
)
from .payments import list_payment_milestones_for_contract, payments_summary
from . import versions as ver_svc

DEFAULT_EXPIRY_DAYS = 14
_DECISION_STATUSES = frozenset({"approved", "rejected", "changes_requested"})
_ACTIONABLE_STATUSES = frozenset({"sent", "opened"})
_TERMINAL_STATUSES = _DECISION_STATUSES | frozenset({"expired", "cancelled"})
_USABLE_CONTRACT_STATUSES = frozenset({"ready", "needs_review"})
_INITIAL_REVIEW = "initial"
_NEGOTIATION_FOLLOWUP = "negotiation_followup"


class ReviewError(ValueError):
    def __init__(self, status_code: int, code: str, **payload):
        self.status_code = status_code
        self.code = code
        self.payload = {"error": code, **payload}
        super().__init__(code)


def _raise_review_error(status_code: int, code: str, **payload) -> None:
    raise ReviewError(status_code, code, **payload)


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def generate_token_material() -> TokenMaterial:
    return create_token_material()


def hash_token(public_token: str) -> str:
    return hash_public_token(public_token)


def public_token_for_request(req: ReviewRequest) -> str:
    if req.token_nonce:
        return public_token_from_nonce(req.token_nonce)
    if req.token:
        return req.token
    _raise_review_error(500, "review_token_unavailable")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def _num(v):
    return float(v) if v is not None else None


def _lock_contract(contract_id, db: Session) -> Contract:
    contract = (
        db.query(Contract)
        .filter(Contract.id == contract_id)
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    if contract is None:
        _raise_review_error(404, "review_not_found")
    return contract


def _lock_review(review_id, db: Session) -> ReviewRequest:
    req = (
        db.query(ReviewRequest)
        .filter(ReviewRequest.id == review_id)
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    if req is None:
        _raise_review_error(404, "review_not_found")
    return req


def _locked_current_version(contract_id, db: Session) -> ContractVersion | None:
    versions = (
        db.query(ContractVersion)
        .filter(ContractVersion.contract_id == contract_id)
        .with_for_update()
        .order_by(ContractVersion.version_number.desc())
        .all()
    )
    return next((version for version in versions if version.is_current), None)


def _is_stale(req: ReviewRequest, current: ContractVersion | None) -> bool:
    return current is None or req.version_id is None or str(req.version_id) != str(current.id)


def _is_negotiation_followup(req: ReviewRequest, db: Session) -> bool:
    return (
        db.query(Negotiation.id)
        .filter(Negotiation.sent_review_request_id == req.id)
        .first()
        is not None
    )


def _activity_metadata(
    req: ReviewRequest,
    version: ContractVersion,
    *,
    actor_type: str,
) -> dict:
    return {
        "review_id": str(req.id),
        "review_request_id": str(req.id),
        "version_id": str(version.id),
        "version_number": version.version_number,
        "actor_type": actor_type,
    }


def _log_review_transition(
    db: Session,
    *,
    contract: Contract,
    req: ReviewRequest,
    version: ContractVersion,
    workflow_event: LifecycleEvent,
    actor: str,
    actor_type: str,
    transition: TransitionResult | None,
    comment: str | None = None,
) -> None:
    metadata = _activity_metadata(req, version, actor_type=actor_type)
    approvals.log_activity(
        db,
        contract.id,
        workflow_event.value,
        actor=actor,
        comment=comment,
        metadata=metadata,
    )
    if transition is None or not transition.changed:
        return
    approvals.log_activity(
        db,
        contract.id,
        transition.activity_event.value,
        actor=actor,
        metadata={**metadata, **transition.activity_metadata},
    )


def _transition_review(
    contract: Contract,
    req: ReviewRequest,
    version: ContractVersion,
    event: LifecycleEvent,
    *,
    actor: str,
    actor_type: str,
    metadata: dict | None = None,
) -> TransitionResult:
    return LifecycleService.transition(
        contract=contract,
        event=event,
        actor=actor,
        metadata={
            **_activity_metadata(req, version, actor_type=actor_type),
            "current_version": True,
            "active_review": req.status in _ACTIONABLE_STATUSES,
            **(metadata or {}),
        },
    )


def _commit(db: Session, *refresh_rows) -> None:
    try:
        db.commit()
        for row in refresh_rows:
            db.refresh(row)
    except Exception:
        db.rollback()
        raise


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
            try:
                req = _lock_review(req.id, db)
                contract = _lock_contract(req.contract_id, db)
                current = _locked_current_version(req.contract_id, db)
                if req.status in _TERMINAL_STATUSES or _is_stale(req, current):
                    db.rollback()
                    return req
                is_followup = _is_negotiation_followup(req, db)
                transition = None
                if not is_followup:
                    transition = _transition_review(
                        contract,
                        req,
                        current,
                        LifecycleEvent.REVIEW_EXPIRED,
                        actor="system",
                        actor_type="system",
                    )
                req.status = "expired"
                _log_review_transition(
                    db,
                    contract=contract,
                    req=req,
                    version=current,
                    workflow_event=LifecycleEvent.REVIEW_EXPIRED,
                    actor="system",
                    actor_type="system",
                    transition=transition,
                )
                _commit(db, req, contract)
            except Exception:
                db.rollback()
                raise
    return req


def can_respond(req: ReviewRequest) -> bool:
    return req.status in _ACTIONABLE_STATUSES


def mark_opened(req: ReviewRequest, db: Session) -> None:
    if req.status != "sent":
        return
    try:
        req = _lock_review(req.id, db)
        contract = _lock_contract(req.contract_id, db)
        current = _locked_current_version(req.contract_id, db)
        if req.status != "sent" or _is_stale(req, current):
            db.rollback()
            return
        is_followup = _is_negotiation_followup(req, db)
        transition = None
        if not is_followup:
            transition = _transition_review(
                contract,
                req,
                current,
                LifecycleEvent.REVIEW_OPENED,
                actor="client",
                actor_type="client",
            )
        req.status = "opened"
        req.opened_at = _utcnow()
        _log_review_transition(
            db,
            contract=contract,
            req=req,
            version=current,
            workflow_event=LifecycleEvent.REVIEW_OPENED,
            actor="client",
            actor_type="client",
            transition=transition,
        )
        _commit(db, req, contract)
    except Exception:
        db.rollback()
        raise


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
    contract = db.get(Contract, req.contract_id)
    is_stale = _is_stale(req, ver_svc.current_version(req.contract_id, db))
    actionable = can_respond(req) and not is_stale
    next_allowed_actions = (
        ["comment", "approve", "reject", "request_changes"] if actionable else []
    )
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
        "is_stale": is_stale,
        "contract_stage": contract.stage if contract else None,
        "actionable": actionable,
        "terminal_decision": (
            response.decision
            if response
            else req.status if req.status in _TERMINAL_STATUSES else None
        ),
        "next_allowed_actions": next_allowed_actions,
    }
    if include_token:
        public_token = public_token_for_request(req)
        out["token"] = public_token
        out["review_link"] = review_link(public_token)
    return out


def create_review_request(
    contract: Contract,
    db: Session,
    *,
    actor: str,
    recipient_name: str,
    recipient_email: str,
    message: str | None = None,
    sender_name: str | None = None,
    sender_email: str | None = None,
    expires_in_days: int = DEFAULT_EXPIRY_DAYS,
    review_context: str = _INITIAL_REVIEW,
    commit: bool = True,
) -> ReviewRequest:
    if review_context not in {_INITIAL_REVIEW, _NEGOTIATION_FOLLOWUP}:
        _raise_review_error(422, "invalid_transition_payload")
    clean_name = recipient_name.strip()
    clean_email = recipient_email.strip()
    if not clean_name or "@" not in clean_email:
        _raise_review_error(422, "invalid_transition_payload")

    try:
        contract = _lock_contract(contract.id, db)
        current = _locked_current_version(contract.id, db)
        if (
            contract.status not in _USABLE_CONTRACT_STATUSES
            or contract.supported is False
            or current is None
        ):
            _raise_review_error(409, "contract_not_ready")

        active = (
            db.query(ReviewRequest)
            .filter(
                ReviewRequest.contract_id == contract.id,
                ReviewRequest.version_id == current.id,
                ReviewRequest.status.in_(_ACTIONABLE_STATUSES),
            )
            .with_for_update()
            .first()
        )
        if active is not None:
            _raise_review_error(409, "review_already_active")

        material = generate_token_material()
        while db.query(ReviewRequest).filter_by(token_hash=material.token_hash).first():
            material = generate_token_material()

        req = ReviewRequest(
            id=uuid.uuid4(),
            contract_id=contract.id,
            version_id=current.id,
            token=None,
            token_nonce=material.nonce,
            token_hash=material.token_hash,
            recipient_name=clean_name,
            recipient_email=clean_email,
            sender_name=sender_name,
            sender_email=sender_email,
            message=message,
            status="sent",
            expires_at=_utcnow() + timedelta(days=max(1, min(expires_in_days, 90))),
        )
        db.add(req)

        transition = None
        if review_context == _INITIAL_REVIEW:
            transition = _transition_review(
                contract,
                req,
                current,
                LifecycleEvent.REVIEW_SENT,
                actor=actor,
                actor_type="internal",
                metadata={"active_review": False},
            )
        approvals.log_activity(
            db,
            contract.id,
            "version_sent_for_review",
            actor=actor,
            metadata=_activity_metadata(req, current, actor_type="internal"),
        )
        _log_review_transition(
            db,
            contract=contract,
            req=req,
            version=current,
            workflow_event=LifecycleEvent.REVIEW_SENT,
            actor=actor,
            actor_type="internal",
            transition=transition,
        )
        if commit:
            _commit(db, req, contract)
        else:
            db.flush()
        return req
    except Exception:
        db.rollback()
        raise


def get_request_by_token(token: str, db: Session) -> ReviewRequest | None:
    return (
        db.query(ReviewRequest)
        .filter(
            or_(
                ReviewRequest.token_hash == hash_token(token),
                ReviewRequest.token == token,
            )
        )
        .first()
    )


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
        "contract_stage": serialized["contract_stage"],
        "actionable": serialized["actionable"],
        "is_stale": serialized["is_stale"],
        "terminal_decision": serialized["terminal_decision"],
        "next_allowed_actions": serialized["next_allowed_actions"],
        "read_only": not serialized["actionable"],
    }


def record_decision(
    req: ReviewRequest,
    db: Session,
    decision: str,
    overall_comment: str | None = None,
    *,
    actor: str = "client",
) -> ReviewRequest:
    expire_if_needed(req, db)
    if decision not in ("approve", "reject", "changes_requested"):
        _raise_review_error(422, "invalid_transition_payload")
    clean_comment = overall_comment.strip() if overall_comment else None

    try:
        req = _lock_review(req.id, db)
        contract = _lock_contract(req.contract_id, db)
        current = _locked_current_version(req.contract_id, db)
        if _is_stale(req, current):
            _raise_review_error(409, "workflow_stale")
        is_followup = _is_negotiation_followup(req, db)
        if not can_respond(req):
            _raise_review_error(
                409,
                "negotiation_closed" if is_followup else "review_closed",
            )
        if db.query(ReviewResponse).filter_by(review_request_id=req.id).first():
            _raise_review_error(
                409,
                "negotiation_closed" if is_followup else "review_closed",
            )
        if decision == "reject" and not clean_comment:
            _raise_review_error(422, "review_reason_required")

        source_comment = (
            db.query(ReviewComment)
            .filter_by(review_request_id=req.id)
            .order_by(ReviewComment.created_at.asc(), ReviewComment.id.asc())
            .first()
        )
        if decision == "changes_requested" and not clean_comment and source_comment is None:
            _raise_review_error(422, "change_request_required")

        status_map = {
            "approve": "approved",
            "reject": "rejected",
            "changes_requested": "changes_requested",
        }
        event_map = {
            "approve": LifecycleEvent.REVIEW_APPROVED,
            "reject": LifecycleEvent.REVIEW_REJECTED,
            "changes_requested": LifecycleEvent.REVIEW_CHANGES_REQUESTED,
        }
        db.add(
            ReviewResponse(
                id=uuid.uuid4(),
                review_request_id=req.id,
                decision=decision,
                overall_comment=clean_comment,
            )
        )

        transition = None
        negotiation_result = None
        if not is_followup:
            transition = _transition_review(
                contract,
                req,
                current,
                event_map[decision],
                actor=actor,
                actor_type="client",
            )
        else:
            from .negotiation import apply_followup_review_decision

            negotiation_result = apply_followup_review_decision(
                req,
                db,
                decision=decision,
                comment=clean_comment,
                actor=actor,
                current_version=current,
            )

        req.status = status_map[decision]
        req.responded_at = _utcnow()
        negotiation_created = False
        if decision == "changes_requested" and not is_followup:
            existing = (
                db.query(Negotiation)
                .filter_by(review_request_id=req.id, review_comment_id=None)
                .first()
            )
            if existing is None:
                negotiation = Negotiation(
                    id=uuid.uuid4(),
                    contract_id=req.contract_id,
                    version_id=current.id,
                    review_request_id=req.id,
                    review_comment_id=None,
                    reviewer_comment=clean_comment or source_comment.comment,
                    reviewer_decision="changes_requested",
                    status="draft",
                    workflow_status="pending_analysis",
                )
                db.add(negotiation)
                negotiation_created = True

        _log_review_transition(
            db,
            contract=contract,
            req=req,
            version=current,
            workflow_event=event_map[decision],
            actor=actor,
            actor_type="client",
            transition=transition,
        )
        if negotiation_created:
            approvals.log_activity(
                db,
                contract.id,
                "negotiation_analysis_requested",
                actor=actor,
                metadata=_activity_metadata(req, current, actor_type="client"),
            )
        _commit(db, req, contract)
        if negotiation_result is not None:
            req._negotiation_result = negotiation_result
        return req
    except Exception:
        db.rollback()
        raise


def cancel_review(
    req: ReviewRequest,
    db: Session,
    *,
    actor: str,
    reason: str,
) -> ReviewRequest:
    clean_reason = reason.strip()
    if not clean_reason:
        _raise_review_error(422, "review_reason_required")
    try:
        req = _lock_review(req.id, db)
        contract = _lock_contract(req.contract_id, db)
        current = _locked_current_version(req.contract_id, db)
        if _is_stale(req, current):
            _raise_review_error(409, "workflow_stale")
        if not can_respond(req):
            _raise_review_error(409, "review_closed")

        is_followup = _is_negotiation_followup(req, db)
        transition = None
        if not is_followup:
            transition = _transition_review(
                contract,
                req,
                current,
                LifecycleEvent.REVIEW_CANCELLED,
                actor=actor,
                actor_type="internal",
            )
        req.status = "cancelled"
        _log_review_transition(
            db,
            contract=contract,
            req=req,
            version=current,
            workflow_event=LifecycleEvent.REVIEW_CANCELLED,
            actor=actor,
            actor_type="internal",
            transition=transition,
            comment=clean_reason,
        )
        _commit(db, req, contract)
        return req
    except Exception:
        db.rollback()
        raise


def add_comment(
    req: ReviewRequest,
    db: Session,
    comment: str,
    clause_ref: str | None = None,
    page: int | None = None,
) -> ReviewComment:
    expire_if_needed(req, db)
    try:
        req = _lock_review(req.id, db)
        _lock_contract(req.contract_id, db)
        current = _locked_current_version(req.contract_id, db)
        if _is_stale(req, current):
            _raise_review_error(409, "workflow_stale")
        if not can_respond(req):
            _raise_review_error(409, "review_closed")
        cm = ReviewComment(
            id=uuid.uuid4(),
            review_request_id=req.id,
            clause_ref=clause_ref,
            page=page,
            comment=comment.strip(),
        )
        db.add(cm)
        _commit(db, cm)
        return cm
    except Exception:
        db.rollback()
        raise


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
