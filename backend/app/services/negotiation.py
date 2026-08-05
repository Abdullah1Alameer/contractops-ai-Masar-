"""Feature 7 — AI Negotiation Assistant service."""
from __future__ import annotations

import json
import hashlib
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy.orm import Session

from ..ai.client import complete_json
from ..ai.negotiation_prompt import NEGOTIATION_SCHEMA, NEGOTIATION_SYSTEM, build_negotiation_prompt
from ..models import (
    ActivityEvent,
    Clause,
    Contract,
    ContractVersion,
    Negotiation,
    NegotiationMessage,
    NegotiationRound,
    NegotiationThread,
    ReviewComment,
    ReviewRequest,
    ReviewResponse,
)
from . import approvals
from . import versions as ver_svc
from .lifecycle import ContractStage, LifecycleEvent, LifecycleService, TransitionResult, normalize_stage
from .reviews import (
    build_email_template,
    build_review_dossier,
    create_review_request,
    public_token_for_request,
    review_link,
    serialize_review_request,
)

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
_TERMINAL_WORKFLOW_STATUS = frozenset({"accepted", "closed"})
_LIFECYCLE_META_KEY = "lifecycle"


class NegotiationClosureOutcome(str, Enum):
    AGREEMENT_REACHED = "agreement_reached"
    COUNTERPARTY_REJECTED = "counterparty_rejected"
    INTERNALLY_ABANDONED = "internally_abandoned"
    SUPERSEDED = "superseded"
    APPROVAL_OVERRIDDEN = "approval_overridden"


# Outcomes that stop an item from blocking approval without being an agreement.
_NON_BLOCKING_OUTCOMES = frozenset(
    {
        NegotiationClosureOutcome.SUPERSEDED.value,
        NegotiationClosureOutcome.APPROVAL_OVERRIDDEN.value,
    }
)


class NegotiationError(ValueError):
    def __init__(self, status_code: int, code: str, **payload):
        self.status_code = status_code
        self.code = code
        self.payload = {"error": code, **payload}
        super().__init__(code)


def _raise_negotiation_error(status_code: int, code: str, **payload) -> None:
    raise NegotiationError(status_code, code, **payload)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def _lock_contract(contract_id, db: Session) -> Contract:
    contract = (
        db.query(Contract)
        .filter(Contract.id == contract_id)
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    if contract is None:
        _raise_negotiation_error(404, "negotiation_not_found")
    return contract


def _lock_negotiation(negotiation_id, db: Session) -> Negotiation:
    negotiation = (
        db.query(Negotiation)
        .filter(Negotiation.id == negotiation_id)
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    if negotiation is None:
        _raise_negotiation_error(404, "negotiation_not_found")
    return negotiation


def _locked_current_version(contract_id, db: Session) -> ContractVersion | None:
    rows = (
        db.query(ContractVersion)
        .filter(ContractVersion.contract_id == contract_id)
        .with_for_update()
        .order_by(ContractVersion.version_number.desc())
        .all()
    )
    return next((row for row in rows if row.is_current), None)


def _lifecycle_meta(negotiation: Negotiation) -> dict[str, Any]:
    summary = negotiation.final_summary if isinstance(negotiation.final_summary, dict) else {}
    value = summary.get(_LIFECYCLE_META_KEY)
    return dict(value) if isinstance(value, dict) else {}


def _set_lifecycle_meta(negotiation: Negotiation, **updates: Any) -> dict[str, Any]:
    summary = dict(negotiation.final_summary) if isinstance(negotiation.final_summary, dict) else {}
    lifecycle = _lifecycle_meta(negotiation)
    lifecycle.update(updates)
    summary[_LIFECYCLE_META_KEY] = lifecycle
    negotiation.final_summary = summary
    return lifecycle


def _round_number(negotiation: Negotiation) -> int:
    return int(_lifecycle_meta(negotiation).get("round_number") or 1)


def _closure_outcome(negotiation: Negotiation) -> str | None:
    value = _lifecycle_meta(negotiation).get("closure_outcome")
    return str(value) if value else None


def _is_resolved(negotiation: Negotiation) -> bool:
    if negotiation.workflow_status == "accepted":
        return True
    return (
        negotiation.workflow_status == "closed"
        and _closure_outcome(negotiation) == NegotiationClosureOutcome.AGREEMENT_REACHED.value
    )


def _is_stale(negotiation: Negotiation, current: ContractVersion | None) -> bool:
    return (
        current is None
        or negotiation.version_id is None
        or str(negotiation.version_id) != str(current.id)
    )


def _safe_metadata(
    negotiation: Negotiation,
    version: ContractVersion,
    *,
    actor_type: str,
    outcome: str | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "negotiation_id": str(negotiation.id),
        "round_id": str(negotiation.id),
        "round_number": _round_number(negotiation),
        "version_id": str(version.id),
        "actor_type": actor_type,
    }
    if negotiation.review_request_id:
        metadata["source_review_id"] = str(negotiation.review_request_id)
    if outcome:
        metadata["outcome"] = outcome
    return metadata


def _transition_and_log(
    db: Session,
    *,
    contract: Contract,
    negotiation: Negotiation,
    version: ContractVersion,
    event: LifecycleEvent,
    actor: str,
    actor_type: str,
    metadata: dict[str, Any] | None = None,
    validation_metadata: dict[str, Any] | None = None,
    log_workflow_event: bool = True,
) -> TransitionResult:
    safe = {
        **_safe_metadata(negotiation, version, actor_type=actor_type),
        **(metadata or {}),
    }
    transition = LifecycleService.transition(
        contract,
        event,
        actor,
        metadata={
            **safe,
            **(validation_metadata or {}),
            "current_version": True,
        },
    )
    if log_workflow_event:
        approvals.log_activity(
            db,
            contract.id,
            event.value,
            actor=actor,
            metadata=safe,
        )
    if transition.changed:
        approvals.log_activity(
            db,
            contract.id,
            transition.activity_event.value,
            actor=actor,
            metadata={
                **safe,
                "from": transition.previous_stage.value,
                "to": transition.next_stage.value,
                "event": transition.event.value,
            },
        )
    return transition


def _validate_actionable(
    negotiation: Negotiation,
    contract: Contract,
    current: ContractVersion | None,
) -> ContractVersion:
    if negotiation.contract_id != contract.id:
        _raise_negotiation_error(404, "negotiation_not_found")
    if _is_stale(negotiation, current):
        _raise_negotiation_error(409, "workflow_stale")
    if normalize_stage(contract.stage) != ContractStage.NEGOTIATION:
        _raise_negotiation_error(
            409,
            "invalid_stage_transition",
            current_stage=contract.stage,
        )
    if negotiation.workflow_status in _TERMINAL_WORKFLOW_STATUS:
        _raise_negotiation_error(409, "negotiation_closed")
    return current


def _current_rows(contract_id, version_id, db: Session) -> list[Negotiation]:
    return (
        db.query(Negotiation)
        .filter(
            Negotiation.contract_id == contract_id,
            Negotiation.version_id == version_id,
        )
        .with_for_update()
        .order_by(Negotiation.created_at.asc(), Negotiation.id.asc())
        .all()
    )


def _unresolved_rows(contract_id, version_id, db: Session) -> list[Negotiation]:
    return [
        row
        for row in _current_rows(contract_id, version_id, db)
        if not _is_resolved(row) and _closure_outcome(row) not in _NON_BLOCKING_OUTCOMES
    ]


def unresolved_for_version(contract_id, version_id, db: Session) -> list[Negotiation]:
    """Items on one version that still block approval, locked for the caller's transaction."""
    return _unresolved_rows(contract_id, version_id, db)


def _event_exists(db: Session, negotiation: Negotiation, event: LifecycleEvent) -> bool:
    return (
        db.query(ActivityEvent.id)
        .filter(
            ActivityEvent.contract_id == negotiation.contract_id,
            ActivityEvent.event_type == event.value,
            ActivityEvent.event_metadata["negotiation_id"].astext == str(negotiation.id),
        )
        .first()
        is not None
    )


def _commit(db: Session, *refresh_rows) -> None:
    try:
        db.commit()
        for row in refresh_rows:
            db.refresh(row)
    except Exception:
        db.rollback()
        raise


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
    """Legacy compatibility hook; lifecycle mutations now happen on response write."""
    return None


def serialize_negotiation(n: Negotiation, db: Session | None = None) -> dict:
    lifecycle = _lifecycle_meta(n)
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
        "editing_status": n.status,
        "edited_by_lawyer": n.edited_by_lawyer,
        "sent_review_request_id": str(n.sent_review_request_id) if n.sent_review_request_id else None,
        "workflow_status": n.workflow_status or "pending_analysis",
        "lawyer_final_clause": n.lawyer_final_clause,
        "lawyer_final_clause_ar": n.lawyer_final_clause_ar,
        "sent_at": _iso(n.sent_at),
        "final_summary": n.final_summary,
        "confidence": _confidence_from_risk(n.risk_level),
        "closure_outcome": lifecycle.get("closure_outcome"),
        "current_round": int(lifecycle.get("round_number") or 1),
        "analysis_status": lifecycle.get("analysis_status") or (
            "ready" if n.workflow_status != "pending_analysis" else "pending"
        ),
        "human_decision_required": lifecycle.get("human_decision_required", True),
        "created_at": _iso(n.created_at),
        "updated_at": _iso(n.updated_at),
    }
    if db is not None:
        contract = db.get(Contract, n.contract_id)
        current = ver_svc.current_version(n.contract_id, db)
        stale = _is_stale(n, current)
        rows = db.query(Negotiation).filter_by(contract_id=n.contract_id).all()
        total_rounds = max((_round_number(row) for row in rows), default=1)
        unresolved = [
            row
            for row in rows
            if current is not None
            and row.version_id == current.id
            and not _is_resolved(row)
            and _closure_outcome(row) != NegotiationClosureOutcome.SUPERSEDED.value
        ]
        actionable = bool(
            contract
            and not stale
            and normalize_stage(contract.stage) == ContractStage.NEGOTIATION
            and n.workflow_status not in _TERMINAL_WORKFLOW_STATUS
        )
        actions: list[str] = []
        if actionable:
            if n.workflow_status == "pending_analysis":
                actions.append("analyze")
            if n.workflow_status in {"ready", "edited_by_legal"}:
                actions.extend(["edit", "approve", "send"])
            if n.workflow_status == "sent_to_client":
                actions.append("await_response")
            actions.append("abandon")
        out["is_stale"] = stale
        out["version_id"] = str(n.version_id) if n.version_id else None
        out["current_version_id"] = str(current.id) if current else None
        out["contract_stage"] = contract.stage if contract else None
        out["total_rounds"] = total_rounds
        out["unresolved_count"] = len(unresolved)
        out["actionable"] = actionable
        out["next_allowed_actions"] = actions
    return out


def _validate_review_for_negotiation(review: ReviewRequest | None) -> ReviewRequest:
    if review is None:
        raise ValueError("invalid_review")
    if review.status not in NEGOTIATION_ELIGIBLE_REVIEW:
        raise ValueError("invalid_review")
    return review


def analyze(
    review_id,
    comment_id,
    db: Session,
    *,
    actor: str = "legal",
) -> Negotiation:
    try:
        review = (
            db.query(ReviewRequest)
            .filter(ReviewRequest.id == review_id)
            .with_for_update()
            .populate_existing()
            .one_or_none()
        )
        review = _validate_review_for_negotiation(review)
        contract = _lock_contract(review.contract_id, db)
        current = _locked_current_version(contract.id, db)
        if (
            current is None
            or review.version_id is None
            or str(review.version_id) != str(current.id)
        ):
            _raise_negotiation_error(409, "workflow_stale")
        if normalize_stage(contract.stage) != ContractStage.NEGOTIATION:
            _raise_negotiation_error(
                409,
                "invalid_stage_transition",
                current_stage=contract.stage,
            )

        comment = db.get(ReviewComment, comment_id) if comment_id else None
        if comment_id and (comment is None or comment.review_request_id != review.id):
            _raise_negotiation_error(422, "negotiation_response_required")

        query = db.query(Negotiation).filter_by(
            review_request_id=review.id,
            review_comment_id=comment_id,
        )
        negotiation = (
            query.with_for_update()
            .order_by(Negotiation.created_at.asc(), Negotiation.id.asc())
            .first()
        )
        if negotiation is not None and (
            negotiation.workflow_status != "pending_analysis"
            or _lifecycle_meta(negotiation).get("analysis_status") == "ready"
            or bool(negotiation.ai_summary)
        ):
            return negotiation

        response = db.query(ReviewResponse).filter_by(review_request_id=review.id).first()
        ctx = build_context(review, contract, db, comment=comment, response=response)
        if not (ctx.get("reviewer_comment") or ctx.get("overall_comment")):
            _raise_negotiation_error(422, "negotiation_response_required")

        if negotiation is None:
            negotiation = Negotiation(
                id=uuid.uuid4(),
                contract_id=review.contract_id,
                version_id=current.id,
                review_request_id=review.id,
                review_comment_id=comment_id,
                clause_ref=ctx.get("clause_ref"),
                original_clause=ctx.get("original_clause"),
                reviewer_comment=ctx.get("reviewer_comment"),
                reviewer_decision=ctx.get("reviewer_decision"),
                status="draft",
                workflow_status="pending_analysis",
                final_summary={
                    _LIFECYCLE_META_KEY: {
                        "round_number": 1,
                        "human_decision_required": True,
                    }
                },
            )
            db.add(negotiation)
            db.flush()
        else:
            _validate_actionable(negotiation, contract, current)

        negotiation.workflow_status = "pending_analysis"
        negotiation.version_id = current.id
        negotiation.updated_at = _utcnow()
        _set_lifecycle_meta(
            negotiation,
            analysis_status="analyzing",
            retryable=False,
            human_decision_required=True,
            source_version_id=str(current.id),
            basis="source_contract_only",
        )
        already_started = _event_exists(
            db,
            negotiation,
            LifecycleEvent.NEGOTIATION_ANALYSIS_STARTED,
        )
        _transition_and_log(
            db,
            contract=contract,
            negotiation=negotiation,
            version=current,
            event=LifecycleEvent.NEGOTIATION_ANALYSIS_STARTED,
            actor=actor,
            actor_type="internal",
            log_workflow_event=not already_started,
        )

        try:
            raw = complete_json(
                NEGOTIATION_SYSTEM,
                build_negotiation_prompt(ctx),
                NEGOTIATION_SCHEMA,
            )
        except Exception:
            _set_lifecycle_meta(
                negotiation,
                analysis_status="failed",
                retryable=True,
                human_decision_required=True,
            )
            _transition_and_log(
                db,
                contract=contract,
                negotiation=negotiation,
                version=current,
                event=LifecycleEvent.NEGOTIATION_ANALYSIS_FAILED,
                actor=actor,
                actor_type="system",
            )
            _commit(db, negotiation, contract)
            _raise_negotiation_error(502, "ai_failed", retryable=True)

        negotiation.ai_summary = raw.get("summary")
        negotiation.business_impact = raw.get("business_impact")
        negotiation.legal_impact = raw.get("legal_impact")
        negotiation.risk_level = raw.get("risk_level")
        negotiation.recommendation = raw.get("recommendation")
        negotiation.reasoning = raw.get("reasoning")
        negotiation.counter_clause = raw.get("counter_clause")
        negotiation.counter_clause_ar = raw.get("arabic_counter_clause")
        negotiation.pros = raw.get("pros") or []
        negotiation.cons = raw.get("cons") or []
        if not negotiation.ai_summary or not (
            negotiation.counter_clause or negotiation.counter_clause_ar
        ):
            _set_lifecycle_meta(
                negotiation,
                analysis_status="failed",
                retryable=True,
            )
            _commit(db, negotiation, contract)
            _raise_negotiation_error(502, "ai_failed", retryable=True)
        negotiation.workflow_status = "ready"
        negotiation.updated_at = _utcnow()
        _set_lifecycle_meta(
            negotiation,
            analysis_status="ready",
            retryable=False,
            human_decision_required=True,
        )
        _transition_and_log(
            db,
            contract=contract,
            negotiation=negotiation,
            version=current,
            event=LifecycleEvent.NEGOTIATION_ANALYZED,
            actor=actor,
            actor_type="system",
        )
        db.add(
            NegotiationMessage(
                id=uuid.uuid4(),
                negotiation_id=negotiation.id,
                author="ai",
                content=json.dumps(raw, ensure_ascii=False),
            )
        )
        _commit(db, negotiation, contract)
        return negotiation
    except NegotiationError:
        if db.is_active:
            db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


def list_negotiations_for_contract(contract_id, db: Session) -> list[dict]:
    rows = (
        db.query(Negotiation)
        .filter_by(contract_id=contract_id)
        .order_by(Negotiation.created_at.desc())
        .all()
    )
    return [serialize_negotiation(n, db) for n in rows]


def apply_patch(
    neg: Negotiation,
    body: dict,
    db: Session,
    *,
    actor: str = "legal",
) -> Negotiation:
    try:
        neg = _lock_negotiation(neg.id, db)
        contract = _lock_contract(neg.contract_id, db)
        current = _validate_actionable(
            neg,
            contract,
            _locked_current_version(contract.id, db),
        )
        if "workflow_status" in body:
            _raise_negotiation_error(409, "invalid_stage_transition")

        immutable_ai_fields = {
            "ai_summary",
            "business_impact",
            "legal_impact",
            "risk_level",
            "recommendation",
            "reasoning",
            "counter_clause",
            "counter_clause_ar",
        }
        if immutable_ai_fields.intersection(body):
            _raise_negotiation_error(409, "ai_output_immutable")

        edited = False
        for field in ("lawyer_final_clause", "lawyer_final_clause_ar"):
            if field in body:
                setattr(neg, field, body[field])
                edited = True

        if "status" in body and body["status"] is not None:
            status = body["status"]
            if status not in {"draft", "approved", "edited"}:
                _raise_negotiation_error(422, "invalid_status")
            neg.status = status
            edited = True

        if not edited:
            return neg
        neg.edited_by_lawyer = True
        if "status" not in body and neg.status == "draft":
            neg.status = "edited"
        neg.workflow_status = "edited_by_legal"
        neg.updated_at = _utcnow()
        _set_lifecycle_meta(
            neg,
            legal_edited_at=_utcnow().isoformat(),
            legal_edited_by=actor,
            human_decision_required=True,
        )
        _transition_and_log(
            db,
            contract=contract,
            negotiation=neg,
            version=current,
            event=LifecycleEvent.NEGOTIATION_EDITED,
            actor=actor,
            actor_type="internal",
        )
        _commit(db, neg, contract)
        return neg
    except Exception:
        db.rollback()
        raise


def _build_final_summary(neg: Negotiation, link: str) -> dict:
    final_en = neg.lawyer_final_clause or neg.counter_clause
    final_ar = neg.lawyer_final_clause_ar or neg.counter_clause_ar
    return {
        **(neg.final_summary if isinstance(neg.final_summary, dict) else {}),
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


def send_updated(
    neg: Negotiation,
    db: Session,
    *,
    actor: str = "legal",
) -> dict:
    try:
        neg = _lock_negotiation(neg.id, db)
        contract = _lock_contract(neg.contract_id, db)
        current = _validate_actionable(
            neg,
            contract,
            _locked_current_version(contract.id, db),
        )
        if neg.sent_review_request_id is not None or (
            neg.status == "sent" and neg.workflow_status == "sent_to_client"
        ):
            _raise_negotiation_error(409, "followup_review_already_active")

        final_en = (neg.lawyer_final_clause or neg.counter_clause or "").strip()
        final_ar = (neg.lawyer_final_clause_ar or neg.counter_clause_ar or "").strip()
        if neg.status != "approved" or not (final_en or final_ar):
            _raise_negotiation_error(422, "counterproposal_required")

        source_review = (
            db.get(ReviewRequest, neg.review_request_id)
            if neg.review_request_id
            else None
        )
        if source_review is None:
            _raise_negotiation_error(422, "negotiation_response_required")

        wording_hash = hashlib.sha256(
            f"{final_en}\0{final_ar}".encode("utf-8")
        ).hexdigest()
        lifecycle = _lifecycle_meta(neg)
        if lifecycle.get("sent_fingerprint") == wording_hash:
            _raise_negotiation_error(409, "followup_review_already_active")

        new_version = ver_svc.stage_negotiation_snapshot(
            contract,
            current,
            db,
            actor=actor,
            negotiation_id=neg.id,
            change_summary=f"Negotiation counterproposal for clause {neg.clause_ref or 'general'}",
        )
        db.flush()
        for active in _current_rows(contract.id, current.id, db):
            active.version_id = new_version.id
            _set_lifecycle_meta(
                active,
                source_version_id=str(current.id),
                current_version_id=str(new_version.id),
            )
        neg.version_id = new_version.id

        message_parts = [
            "Updated contract terms for your review.",
            f"Clause: {neg.clause_ref or 'General'}",
        ]
        if final_en:
            message_parts.append(f"Proposed wording (EN): {final_en}")
        if final_ar:
            message_parts.append(f"Proposed wording (AR): {final_ar}")

        new_req = create_review_request(
            contract,
            db,
            actor=actor,
            recipient_name=source_review.recipient_name,
            recipient_email=source_review.recipient_email,
            message="\n\n".join(message_parts),
            sender_name=source_review.sender_name,
            sender_email=source_review.sender_email,
            review_context="negotiation_followup",
            commit=False,
        )
        neg.sent_review_request_id = new_req.id
        neg.status = "sent"
        neg.workflow_status = "sent_to_client"
        neg.sent_at = _utcnow()
        link = review_link(public_token_for_request(new_req))
        neg.final_summary = _build_final_summary(neg, link)
        _set_lifecycle_meta(
            neg,
            sent_fingerprint=wording_hash,
            sent_version_id=str(new_version.id),
            current_version_id=str(new_version.id),
            human_decision_required=True,
        )
        neg.updated_at = _utcnow()
        _transition_and_log(
            db,
            contract=contract,
            negotiation=neg,
            version=new_version,
            event=LifecycleEvent.COUNTERPROPOSAL_SENT,
            actor=actor,
            actor_type="internal",
            metadata={"followup_review_id": str(new_req.id)},
        )
        _commit(db, neg, new_req, contract, new_version)

        email = build_email_template(new_req, contract, link)
        return {
            "negotiation": serialize_negotiation(neg, db),
            "review_link": link,
            "email": email,
            "request": serialize_review_request(new_req, db, include_token=True),
        }
    except Exception:
        db.rollback()
        raise


def _mark_closed(
    negotiation: Negotiation,
    *,
    outcome: NegotiationClosureOutcome,
    workflow_status: str = "closed",
) -> None:
    negotiation.status = "closed"
    negotiation.workflow_status = workflow_status
    negotiation.updated_at = _utcnow()
    _set_lifecycle_meta(
        negotiation,
        closure_outcome=outcome.value,
        closed_at=_utcnow().isoformat(),
        human_decision_required=True,
    )


def apply_followup_review_decision(
    review: ReviewRequest,
    db: Session,
    *,
    decision: str,
    comment: str | None,
    actor: str,
    current_version: ContractVersion,
) -> dict:
    """Apply a public follow-up response without committing the caller's transaction."""
    negotiation = (
        db.query(Negotiation)
        .filter(Negotiation.sent_review_request_id == review.id)
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    if negotiation is None:
        _raise_negotiation_error(404, "negotiation_not_found")
    contract = _lock_contract(review.contract_id, db)
    current = _locked_current_version(contract.id, db)
    if (
        current is None
        or current.id != current_version.id
        or review.version_id != current.id
    ):
        _raise_negotiation_error(409, "workflow_stale")
    current = _validate_actionable(negotiation, contract, current)

    if decision == "approve":
        _mark_closed(
            negotiation,
            outcome=NegotiationClosureOutcome.AGREEMENT_REACHED,
            workflow_status="accepted",
        )
        unresolved = _unresolved_rows(contract.id, current.id, db)
        metadata = {
            "outcome": NegotiationClosureOutcome.AGREEMENT_REACHED.value,
            "unresolved_count": len(unresolved),
        }
        if not unresolved:
            metadata["negotiations_resolved"] = True
            _transition_and_log(
                db,
                contract=contract,
                negotiation=negotiation,
                version=current,
                event=LifecycleEvent.NEGOTIATION_ACCEPTED,
                actor=actor,
                actor_type="counterparty",
                metadata=metadata,
            )
        else:
            approvals.log_activity(
                db,
                contract.id,
                LifecycleEvent.NEGOTIATION_ACCEPTED.value,
                actor=actor,
                metadata={
                    **_safe_metadata(
                        negotiation,
                        current,
                        actor_type="counterparty",
                        outcome=NegotiationClosureOutcome.AGREEMENT_REACHED.value,
                    ),
                    "unresolved_count": len(unresolved),
                },
            )
        approvals.log_activity(
            db,
            contract.id,
            LifecycleEvent.NEGOTIATION_CLOSED.value,
            actor=actor,
            metadata={
                **_safe_metadata(
                    negotiation,
                    current,
                    actor_type="counterparty",
                    outcome=NegotiationClosureOutcome.AGREEMENT_REACHED.value,
                ),
                "unresolved_count": len(unresolved),
            },
        )
        result_row = negotiation

    elif decision == "changes_requested":
        negotiation.status = "closed"
        negotiation.workflow_status = "client_responded"
        negotiation.updated_at = _utcnow()
        next_round_number = _round_number(negotiation) + 1
        existing_next = (
            db.query(Negotiation)
            .filter_by(
                contract_id=contract.id,
                review_request_id=review.id,
                version_id=current.id,
            )
            .with_for_update()
            .first()
        )
        if existing_next is not None:
            _raise_negotiation_error(409, "round_already_exists")
        result_row = Negotiation(
            id=uuid.uuid4(),
            contract_id=contract.id,
            version_id=current.id,
            review_request_id=review.id,
            clause_ref=negotiation.clause_ref,
            original_clause=negotiation.lawyer_final_clause
            or negotiation.counter_clause
            or negotiation.original_clause,
            reviewer_comment=comment,
            reviewer_decision="changes_requested",
            status="draft",
            workflow_status="pending_analysis",
            final_summary={
                _LIFECYCLE_META_KEY: {
                    "round_number": next_round_number,
                    "parent_negotiation_id": str(negotiation.id),
                    "source_review_id": str(review.id),
                    "source_version_id": str(current.id),
                    "analysis_status": "pending",
                    "human_decision_required": True,
                }
            },
        )
        db.add(result_row)
        db.flush()
        for event in (
            LifecycleEvent.NEGOTIATION_CLIENT_RESPONDED,
            LifecycleEvent.NEGOTIATION_ROUND_STARTED,
            LifecycleEvent.NEGOTIATION_ANALYSIS_REQUESTED,
        ):
            _transition_and_log(
                db,
                contract=contract,
                negotiation=result_row if event != LifecycleEvent.NEGOTIATION_CLIENT_RESPONDED else negotiation,
                version=current,
                event=event,
                actor=actor,
                actor_type="counterparty",
                metadata={
                    "parent_negotiation_id": str(negotiation.id),
                    "source_review_id": str(review.id),
                },
            )
        unresolved = _unresolved_rows(contract.id, current.id, db)

    elif decision == "reject":
        rows = _current_rows(contract.id, current.id, db)
        for row in rows:
            if row.workflow_status not in _TERMINAL_WORKFLOW_STATUS:
                _mark_closed(
                    row,
                    outcome=NegotiationClosureOutcome.COUNTERPARTY_REJECTED,
                )
                approvals.log_activity(
                    db,
                    contract.id,
                    LifecycleEvent.NEGOTIATION_CLOSED.value,
                    actor=actor,
                    metadata=_safe_metadata(
                        row,
                        current,
                        actor_type="counterparty",
                        outcome=NegotiationClosureOutcome.COUNTERPARTY_REJECTED.value,
                    ),
                )
        _transition_and_log(
            db,
            contract=contract,
            negotiation=negotiation,
            version=current,
            event=LifecycleEvent.NEGOTIATION_REJECTED,
            actor=actor,
            actor_type="counterparty",
            metadata={"outcome": NegotiationClosureOutcome.COUNTERPARTY_REJECTED.value},
        )
        unresolved = []
        result_row = negotiation
    else:
        _raise_negotiation_error(422, "negotiation_response_required")

    payload = serialize_negotiation(result_row, db)
    payload["unresolved_count"] = len(unresolved)
    payload["contract_stage"] = contract.stage
    return payload


def abandon(
    neg: Negotiation,
    db: Session,
    *,
    actor: str,
    reason: str,
) -> dict:
    clean_reason = reason.strip()
    if not clean_reason:
        _raise_negotiation_error(422, "negotiation_reason_required")
    try:
        neg = _lock_negotiation(neg.id, db)
        contract = _lock_contract(neg.contract_id, db)
        current = _validate_actionable(
            neg,
            contract,
            _locked_current_version(contract.id, db),
        )
        rows = _current_rows(contract.id, current.id, db)
        for row in rows:
            if row.workflow_status not in _TERMINAL_WORKFLOW_STATUS:
                _mark_closed(
                    row,
                    outcome=NegotiationClosureOutcome.INTERNALLY_ABANDONED,
                )
                approvals.log_activity(
                    db,
                    contract.id,
                    LifecycleEvent.NEGOTIATION_CLOSED.value,
                    actor=actor,
                    metadata=_safe_metadata(
                        row,
                        current,
                        actor_type="internal",
                        outcome=NegotiationClosureOutcome.INTERNALLY_ABANDONED.value,
                    ),
                )
        _transition_and_log(
            db,
            contract=contract,
            negotiation=neg,
            version=current,
            event=LifecycleEvent.NEGOTIATION_ABANDONED,
            actor=actor,
            actor_type="internal",
            metadata={
                "reason_provided": True,
                "outcome": NegotiationClosureOutcome.INTERNALLY_ABANDONED.value,
            },
            validation_metadata={"reason": clean_reason},
        )
        _commit(db, neg, contract)
        return serialize_negotiation(neg, db)
    except Exception:
        db.rollback()
        raise


def supersede_version_negotiations(
    contract: Contract,
    old_version_id,
    new_version_id,
    db: Session,
    *,
    actor: str,
) -> None:
    """Close old-version negotiation items without changing contract stage."""
    rows = _current_rows(contract.id, old_version_id, db)
    old_version = db.get(ContractVersion, old_version_id)
    if old_version is None:
        return
    for row in rows:
        if row.workflow_status in _TERMINAL_WORKFLOW_STATUS:
            continue
        _mark_closed(row, outcome=NegotiationClosureOutcome.SUPERSEDED)
        _set_lifecycle_meta(row, superseded_by_version_id=str(new_version_id))
        if normalize_stage(contract.stage) == ContractStage.NEGOTIATION:
            _transition_and_log(
                db,
                contract=contract,
                negotiation=row,
                version=old_version,
                event=LifecycleEvent.NEGOTIATION_SUPERSEDED,
                actor=actor,
                actor_type="internal",
                metadata={
                    "outcome": NegotiationClosureOutcome.SUPERSEDED.value,
                    "superseded_by_version_id": str(new_version_id),
                },
            )
        else:
            approvals.log_activity(
                db,
                contract.id,
                LifecycleEvent.NEGOTIATION_SUPERSEDED.value,
                actor=actor,
                metadata={
                    **_safe_metadata(
                        row,
                        old_version,
                        actor_type="internal",
                        outcome=NegotiationClosureOutcome.SUPERSEDED.value,
                    ),
                    "superseded_by_version_id": str(new_version_id),
                },
            )


def close_for_approval_override(
    contract: Contract,
    version: ContractVersion,
    rows: list[Negotiation],
    db: Session,
    *,
    actor: str,
    reason: str,
) -> list[Negotiation]:
    """Record blocking items as overridden by an authorized approver, without committing."""
    closed: list[Negotiation] = []
    for row in rows:
        _mark_closed(row, outcome=NegotiationClosureOutcome.APPROVAL_OVERRIDDEN)
        _set_lifecycle_meta(
            row,
            override_reason=reason,
            override_actor=actor,
            override_at=_utcnow().isoformat(),
        )
        approvals.log_activity(
            db,
            contract.id,
            LifecycleEvent.NEGOTIATION_CLOSED.value,
            actor=actor,
            metadata=_safe_metadata(
                row,
                version,
                actor_type="internal",
                outcome=NegotiationClosureOutcome.APPROVAL_OVERRIDDEN.value,
            ),
        )
        closed.append(row)
    return closed


def seed_from_approval(
    contract: Contract,
    version: ContractVersion,
    db: Session,
    *,
    workflow_id,
    step_id,
    role: str,
    reason: str,
) -> tuple[Negotiation, bool]:
    """Create the single negotiation round that an approval change request opens."""
    existing = (
        db.query(Negotiation)
        .filter(
            Negotiation.contract_id == contract.id,
            Negotiation.version_id == version.id,
            Negotiation.final_summary[(_LIFECYCLE_META_KEY, "approval_step_id")].astext == str(step_id),
        )
        .with_for_update()
        .populate_existing()
        .first()
    )
    if existing is not None:
        return existing, False

    negotiation = Negotiation(
        id=uuid.uuid4(),
        contract_id=contract.id,
        version_id=version.id,
        reviewer_comment=reason,
        reviewer_decision="changes_requested",
        status="draft",
        workflow_status="pending_analysis",
    )
    _set_lifecycle_meta(
        negotiation,
        round_number=1,
        origin="internal_approval",
        approval_workflow_id=str(workflow_id),
        approval_step_id=str(step_id),
        approval_role=role,
        source_version_id=str(version.id),
        human_decision_required=True,
    )
    db.add(negotiation)
    db.flush()
    return negotiation, True


def apply_monitor_response(
    thread: NegotiationThread,
    db: Session,
    *,
    decision: str,
    actor: str,
    reason: str | None = None,
) -> dict:
    """Apply a human-confirmed monitor response without committing."""
    thread = (
        db.query(NegotiationThread)
        .filter(NegotiationThread.id == thread.id)
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    if thread is None:
        _raise_negotiation_error(404, "negotiation_not_found")
    contract = _lock_contract(thread.contract_id, db)
    current = _locked_current_version(contract.id, db)
    if (
        current is None
        or thread.current_version_id is None
        or thread.current_version_id != current.id
    ):
        _raise_negotiation_error(409, "workflow_stale")
    if normalize_stage(contract.stage) != ContractStage.NEGOTIATION:
        _raise_negotiation_error(
            409,
            "invalid_stage_transition",
            current_stage=contract.stage,
        )
    if thread.status in {"agreement_reached", "rejected", "cancelled", "closed"}:
        _raise_negotiation_error(409, "negotiation_closed")

    latest_round = (
        db.query(NegotiationRound)
        .filter_by(thread_id=thread.id)
        .with_for_update()
        .order_by(NegotiationRound.round_number.desc())
        .first()
    )
    safe = {
        "thread_id": str(thread.id),
        "round_id": str(latest_round.id) if latest_round else None,
        "version_id": str(current.id),
        "actor_type": "internal",
        "source": "negotiation_monitor",
    }

    if decision == "accept":
        thread.status = "agreement_reached"
        if latest_round:
            latest_round.status = "accepted"
            latest_round.closed_at = _utcnow()
        unresolved = _unresolved_rows(contract.id, current.id, db)
        if unresolved:
            approvals.log_activity(
                db,
                contract.id,
                LifecycleEvent.NEGOTIATION_ACCEPTED.value,
                actor=actor,
                metadata={**safe, "unresolved_count": len(unresolved)},
            )
        else:
            transition = LifecycleService.transition(
                contract,
                LifecycleEvent.NEGOTIATION_ACCEPTED,
                actor,
                metadata={
                    **safe,
                    "current_version": True,
                    "negotiations_resolved": True,
                },
            )
            approvals.log_activity(
                db,
                contract.id,
                LifecycleEvent.NEGOTIATION_ACCEPTED.value,
                actor=actor,
                metadata={**safe, "unresolved_count": 0},
            )
            if transition.changed:
                approvals.log_activity(
                    db,
                    contract.id,
                    transition.activity_event.value,
                    actor=actor,
                    metadata={
                        **safe,
                        "from": transition.previous_stage.value,
                        "to": transition.next_stage.value,
                        "event": transition.event.value,
                    },
                )
        return {
            "contract_stage": contract.stage,
            "thread_status": thread.status,
            "unresolved_count": len(unresolved),
        }

    if decision == "reject":
        if not (reason or "").strip():
            _raise_negotiation_error(422, "negotiation_response_required")
        for row in _current_rows(contract.id, current.id, db):
            if row.workflow_status not in _TERMINAL_WORKFLOW_STATUS:
                _mark_closed(
                    row,
                    outcome=NegotiationClosureOutcome.COUNTERPARTY_REJECTED,
                )
        thread.status = "rejected"
        if latest_round:
            latest_round.status = "rejected"
            latest_round.closed_at = _utcnow()
        transition = LifecycleService.transition(
            contract,
            LifecycleEvent.NEGOTIATION_REJECTED,
            actor,
            metadata={**safe, "current_version": True},
        )
        approvals.log_activity(
            db,
            contract.id,
            LifecycleEvent.NEGOTIATION_REJECTED.value,
            actor=actor,
            metadata={
                **safe,
                "outcome": NegotiationClosureOutcome.COUNTERPARTY_REJECTED.value,
            },
        )
        if transition.changed:
            approvals.log_activity(
                db,
                contract.id,
                transition.activity_event.value,
                actor=actor,
                metadata={
                    **safe,
                    "from": transition.previous_stage.value,
                    "to": transition.next_stage.value,
                    "event": transition.event.value,
                },
            )
        return {
            "contract_stage": contract.stage,
            "thread_status": thread.status,
            "unresolved_count": 0,
        }

    if decision == "changes_requested":
        thread.status = "counterparty_responded"
        if latest_round:
            latest_round.status = "client_responded"
        LifecycleService.transition(
            contract,
            LifecycleEvent.NEGOTIATION_CLIENT_RESPONDED,
            actor,
            metadata={**safe, "current_version": True},
        )
        approvals.log_activity(
            db,
            contract.id,
            LifecycleEvent.NEGOTIATION_CLIENT_RESPONDED.value,
            actor=actor,
            metadata=safe,
        )
        return {
            "contract_stage": contract.stage,
            "thread_status": thread.status,
            "unresolved_count": len(_unresolved_rows(contract.id, current.id, db)),
        }

    _raise_negotiation_error(422, "negotiation_response_required")


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
    return out
