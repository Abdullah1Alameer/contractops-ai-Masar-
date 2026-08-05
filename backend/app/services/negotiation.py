"""Feature 7 — AI Negotiation Assistant service."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..ai.client import complete_json
from ..ai.negotiation_prompt import NEGOTIATION_SCHEMA, NEGOTIATION_SYSTEM, build_negotiation_prompt
from ..models import Clause, Contract, Negotiation, NegotiationMessage, ReviewComment, ReviewRequest, ReviewResponse
from .reviews import build_email_template, build_review_dossier, create_review_request, review_link, serialize_review_request

ALLOWED_RISK = frozenset({"low", "medium", "high", "critical"})
ALLOWED_RECOMMENDATION = frozenset({"accept_client", "negotiate", "reject_client"})
ALLOWED_STATUS = frozenset({"draft", "approved", "edited", "sent", "closed"})
ALLOWED_WORKFLOW_STATUS = frozenset(
    {
        "pending_analysis",
        "ready",
        "edited_by_legal",
        "sent_to_client",
        "client_responded",
        "accepted",
        "closed",
    }
)
NEGOTIATION_ELIGIBLE_REVIEW = frozenset({"rejected", "changes_requested"})


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def _find_clause_text(db: Session, contract_id, clause_ref: str | None) -> str | None:
    if not clause_ref:
        return None
    row = (
        db.query(Clause)
        .filter(Clause.contract_id == contract_id, Clause.clause_ref == clause_ref)
        .first()
    )
    if row and row.quote:
        return row.quote
    rows = db.query(Clause).filter(Clause.contract_id == contract_id).all()
    for c in rows:
        if c.clause_ref and clause_ref in c.clause_ref and c.quote:
            return c.quote
    return None


def build_context(
    review: ReviewRequest,
    contract: Contract,
    db: Session,
    *,
    comment: ReviewComment | None,
    response: ReviewResponse | None,
) -> dict:
    dossier = build_review_dossier(review.contract_id, db)
    clause_ref = comment.clause_ref if comment else None
    original = _find_clause_text(db, review.contract_id, clause_ref)
    reviewer_comment = comment.comment if comment else None
    if not reviewer_comment and response and response.overall_comment:
        reviewer_comment = response.overall_comment

    decision = None
    if response:
        if response.decision == "reject":
            decision = "reject"
        elif response.decision == "changes_requested":
            decision = "changes_requested"

    return {
        "contract_title": contract.title,
        "party_a": contract.party_a,
        "party_b": contract.party_b,
        "contract_category": contract.contract_category,
        "governing_law": contract.governing_law,
        "review_status": review.status,
        "reviewer_decision": decision,
        "overall_comment": response.overall_comment if response else None,
        "clause_ref": clause_ref,
        "original_clause": original,
        "reviewer_comment": reviewer_comment,
        "contract_summary": dossier.get("ai_summary"),
    }


def _confidence_from_risk(risk: str | None) -> float | None:
    return {"low": 0.85, "medium": 0.7, "high": 0.55, "critical": 0.4}.get(risk or "", None)


def _reconcile_negotiation_status(n: Negotiation, db: Session) -> None:
    if not n.sent_review_request_id or n.workflow_status in ("accepted", "closed"):
        return
    sent_review = db.get(ReviewRequest, n.sent_review_request_id)
    if not sent_review:
        return
    resp = db.query(ReviewResponse).filter_by(review_request_id=sent_review.id).first()
    if not resp:
        if n.workflow_status == "sent_to_client":
            return
        return
    if resp.decision == "approve":
        n.workflow_status = "accepted"
    elif resp.decision in ("reject", "changes_requested"):
        n.workflow_status = "client_responded"


def serialize_negotiation(n: Negotiation, db: Session | None = None) -> dict:
    out = {
        "id": str(n.id),
        "contract_id": str(n.contract_id),
        "review_request_id": str(n.review_request_id) if n.review_request_id else None,
        "review_comment_id": str(n.review_comment_id) if n.review_comment_id else None,
        "clause_ref": n.clause_ref,
        "original_clause": n.original_clause,
        "reviewer_comment": n.reviewer_comment,
        "reviewer_decision": n.reviewer_decision,
        "ai_summary": n.ai_summary,
        "business_impact": n.business_impact,
        "legal_impact": n.legal_impact,
        "risk_level": n.risk_level,
        "recommendation": n.recommendation,
        "reasoning": n.reasoning,
        "counter_clause": n.counter_clause,
        "counter_clause_ar": n.counter_clause_ar,
        "pros": n.pros or [],
        "cons": n.cons or [],
        "status": n.status,
        "edited_by_lawyer": n.edited_by_lawyer,
        "sent_review_request_id": str(n.sent_review_request_id) if n.sent_review_request_id else None,
        "workflow_status": n.workflow_status or "pending_analysis",
        "lawyer_final_clause": n.lawyer_final_clause,
        "lawyer_final_clause_ar": n.lawyer_final_clause_ar,
        "sent_at": _iso(n.sent_at),
        "final_summary": n.final_summary,
        "confidence": _confidence_from_risk(n.risk_level),
        "created_at": _iso(n.created_at),
        "updated_at": _iso(n.updated_at),
    }
    if db is not None:
        from . import versions as ver_svc

        out["is_stale"] = ver_svc.is_stale_workflow(n, n.contract_id, db)
        out["version_id"] = str(n.version_id) if n.version_id else None
    return out


def _validate_review_for_negotiation(review: ReviewRequest | None) -> ReviewRequest:
    if review is None:
        raise ValueError("invalid_review")
    if review.status not in NEGOTIATION_ELIGIBLE_REVIEW:
        raise ValueError("invalid_review")
    return review


def analyze(review_id, comment_id, db: Session) -> Negotiation:
    review = _validate_review_for_negotiation(db.get(ReviewRequest, review_id))
    contract = db.get(Contract, review.contract_id)
    if contract is None:
        raise ValueError("invalid_review")

    comment = db.get(ReviewComment, comment_id) if comment_id else None
    if comment_id and (comment is None or comment.review_request_id != review.id):
        raise ValueError("invalid_review")

    response = db.query(ReviewResponse).filter_by(review_request_id=review.id).first()
    ctx = build_context(review, contract, db, comment=comment, response=response)

    if not (ctx.get("reviewer_comment") or ctx.get("overall_comment")):
        raise ValueError("no_comment_or_reason")

    raw = complete_json(NEGOTIATION_SYSTEM, build_negotiation_prompt(ctx), NEGOTIATION_SCHEMA)

    existing = None
    if comment_id:
        existing = (
            db.query(Negotiation)
            .filter_by(review_request_id=review.id, review_comment_id=comment_id)
            .first()
        )
    elif not comment_id:
        existing = (
            db.query(Negotiation)
            .filter_by(review_request_id=review.id, review_comment_id=None)
            .first()
        )

    if existing is None:
        neg = Negotiation(
            id=uuid.uuid4(),
            contract_id=review.contract_id,
            review_request_id=review.id,
            review_comment_id=comment_id,
            clause_ref=ctx.get("clause_ref"),
            original_clause=ctx.get("original_clause"),
            reviewer_comment=ctx.get("reviewer_comment"),
            reviewer_decision=ctx.get("reviewer_decision"),
            status="draft",
            workflow_status="pending_analysis",
        )
        db.add(neg)
    else:
        neg = existing

    neg.ai_summary = raw.get("summary")
    neg.business_impact = raw.get("business_impact")
    neg.legal_impact = raw.get("legal_impact")
    neg.risk_level = raw.get("risk_level")
    neg.recommendation = raw.get("recommendation")
    neg.reasoning = raw.get("reasoning")
    neg.counter_clause = raw.get("counter_clause")
    neg.counter_clause_ar = raw.get("arabic_counter_clause")
    neg.pros = raw.get("pros") or []
    neg.cons = raw.get("cons") or []
    neg.workflow_status = "ready"
    neg.updated_at = _utcnow()
    from .versions import current_version

    cur = current_version(review.contract_id, db)
    if cur:
        neg.version_id = cur.id

    from .approvals import log_activity

    log_activity(
        db,
        review.contract_id,
        "negotiation_generated",
        metadata={
            "version_number": cur.version_number if cur else None,
            "negotiation_id": str(neg.id),
            "review_request_id": str(review.id),
        },
    )

    db.add(
        NegotiationMessage(
            id=uuid.uuid4(),
            negotiation_id=neg.id,
            author="ai",
            content=json.dumps(raw, ensure_ascii=False),
        )
    )
    db.commit()
    db.refresh(neg)
    return neg


def list_negotiations_for_contract(contract_id, db: Session) -> list[dict]:
    rows = (
        db.query(Negotiation)
        .filter_by(contract_id=contract_id)
        .order_by(Negotiation.created_at.desc())
        .all()
    )
    for n in rows:
        _reconcile_negotiation_status(n, db)
    db.commit()
    return [serialize_negotiation(n, db) for n in rows]


def apply_patch(neg: Negotiation, body: dict, db: Session) -> Negotiation:
    if neg.workflow_status == "sent_to_client" and neg.status == "sent":
        raise ValueError("negotiation_sent")

    if "workflow_status" in body and body["workflow_status"] is not None:
        if body["workflow_status"] not in ALLOWED_WORKFLOW_STATUS:
            raise ValueError("invalid_workflow_status")
        neg.workflow_status = body["workflow_status"]

    for field in ("lawyer_final_clause", "lawyer_final_clause_ar"):
        if field in body:
            setattr(neg, field, body[field])
            neg.edited_by_lawyer = True
            if body.get("workflow_status") is None and neg.workflow_status not in ("sent_to_client", "accepted", "closed"):
                neg.workflow_status = "edited_by_legal"

    if "risk_level" in body and body["risk_level"] is not None:
        if body["risk_level"] not in ALLOWED_RISK:
            raise ValueError("invalid_risk_level")
        neg.risk_level = body["risk_level"]

    if "recommendation" in body and body["recommendation"] is not None:
        if body["recommendation"] not in ALLOWED_RECOMMENDATION:
            raise ValueError("invalid_recommendation")
        neg.recommendation = body["recommendation"]

    for field in ("reasoning", "counter_clause", "counter_clause_ar", "ai_summary", "business_impact", "legal_impact"):
        if field in body:
            setattr(neg, field, body[field])

    if "status" in body and body["status"] is not None:
        if body["status"] not in ALLOWED_STATUS:
            raise ValueError("invalid_status")
        neg.status = body["status"]

    neg.edited_by_lawyer = True
    if "status" not in body and neg.status == "draft":
        neg.status = "edited"
    if (
        "workflow_status" not in body
        and neg.workflow_status == "ready"
        and any(k in body for k in ("reasoning", "counter_clause", "lawyer_final_clause"))
    ):
        neg.workflow_status = "edited_by_legal"
    neg.updated_at = _utcnow()
    if "workflow_status" in body and body["workflow_status"] is not None:
        from .approvals import log_activity
        from .versions import current_version

        cur = current_version(neg.contract_id, db)
        ws = body["workflow_status"]
        if ws == "accepted":
            log_activity(
                db,
                neg.contract_id,
                "negotiation_accepted",
                metadata={"negotiation_id": str(neg.id), "version_number": cur.version_number if cur else None},
            )
        elif ws == "closed":
            log_activity(
                db,
                neg.contract_id,
                "negotiation_closed",
                metadata={"negotiation_id": str(neg.id), "version_number": cur.version_number if cur else None},
            )
    db.commit()
    db.refresh(neg)
    return neg


def _build_final_summary(neg: Negotiation, link: str) -> dict:
    final_en = neg.lawyer_final_clause or neg.counter_clause
    final_ar = neg.lawyer_final_clause_ar or neg.counter_clause_ar
    return {
        "original_request": neg.reviewer_comment,
        "original_clause": neg.original_clause,
        "ai_recommendation": neg.recommendation,
        "ai_wording_en": neg.counter_clause,
        "ai_wording_ar": neg.counter_clause_ar,
        "lawyer_edits_en": neg.lawyer_final_clause,
        "lawyer_edits_ar": neg.lawyer_final_clause_ar,
        "final_wording_en": final_en,
        "final_wording_ar": final_ar,
        "review_link": link,
        "sent_at": _utcnow().isoformat(),
    }


def send_updated(neg: Negotiation, db: Session) -> dict:
    if neg.status == "sent" and neg.workflow_status == "sent_to_client":
        raise ValueError("negotiation_sent")
    review = db.get(ReviewRequest, neg.review_request_id) if neg.review_request_id else None
    contract = db.get(Contract, neg.contract_id)
    if contract is None:
        raise ValueError("not_found")

    msg_parts = [
        "Updated contract terms for your review.",
        f"Clause: {neg.clause_ref or 'General'}",
    ]
    if neg.counter_clause:
        msg_parts.append(f"Proposed wording (EN): {neg.lawyer_final_clause or neg.counter_clause}")
    if neg.counter_clause_ar or neg.lawyer_final_clause_ar:
        msg_parts.append(f"Proposed wording (AR): {neg.lawyer_final_clause_ar or neg.counter_clause_ar}")
    if neg.reasoning:
        msg_parts.append(f"Reasoning: {neg.reasoning}")

    new_req = create_review_request(
        contract,
        db,
        actor=review.sender_name if review and review.sender_name else "legal",
        recipient_name=review.recipient_name if review else "Client",
        recipient_email=review.recipient_email if review else "client@example.com",
        message="\n\n".join(msg_parts),
        sender_name=review.sender_name if review else None,
        sender_email=review.sender_email if review else None,
        review_context="negotiation_followup",
    )
    neg.sent_review_request_id = new_req.id
    neg.status = "sent"
    neg.workflow_status = "sent_to_client"
    neg.sent_at = _utcnow()
    link = review_link(new_req.token)
    neg.final_summary = _build_final_summary(neg, link)
    neg.updated_at = _utcnow()
    db.commit()
    db.refresh(neg)

    email = build_email_template(new_req, contract, link)
    return {
        "negotiation": serialize_negotiation(neg, db),
        "review_link": link,
        "email": email,
        "request": serialize_review_request(new_req, db, include_token=True),
    }


def list_negotiation_candidates(contract_id, db: Session) -> list[dict]:
    """Review comments + overall reject/changes rows eligible for analyze."""
    reviews = (
        db.query(ReviewRequest)
        .filter_by(contract_id=contract_id)
        .filter(ReviewRequest.status.in_(NEGOTIATION_ELIGIBLE_REVIEW))
        .order_by(ReviewRequest.created_at.desc())
        .all()
    )
    out: list[dict] = []
    for rev in reviews:
        response = db.query(ReviewResponse).filter_by(review_request_id=rev.id).first()
        comments = db.query(ReviewComment).filter_by(review_request_id=rev.id).all()
        for cm in comments:
            neg = (
                db.query(Negotiation)
                .filter_by(review_request_id=rev.id, review_comment_id=cm.id)
                .first()
            )
            if neg:
                _reconcile_negotiation_status(neg, db)
            original = _find_clause_text(db, contract_id, cm.clause_ref)
            out.append(
                {
                    "review_id": str(rev.id),
                    "comment_id": str(cm.id),
                    "clause_ref": cm.clause_ref,
                    "reviewer_comment": cm.comment,
                    "review_status": rev.status,
                    "original_clause": original,
                    "negotiation": serialize_negotiation(neg, db) if neg else None,
                }
            )
        if not comments and response:
            neg = (
                db.query(Negotiation)
                .filter_by(review_request_id=rev.id, review_comment_id=None)
                .first()
            )
            if neg:
                _reconcile_negotiation_status(neg, db)
            out.append(
                {
                    "review_id": str(rev.id),
                    "comment_id": None,
                    "clause_ref": None,
                    "reviewer_comment": response.overall_comment,
                    "review_status": rev.status,
                    "original_clause": None,
                    "negotiation": serialize_negotiation(neg, db) if neg else None,
                }
            )
    db.commit()
    return out
