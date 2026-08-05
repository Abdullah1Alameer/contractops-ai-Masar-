"""Internal approval workflow integrated with the canonical contract lifecycle."""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import (
    ActivityEvent,
    ApprovalStep,
    ApprovalWorkflow,
    Contract,
    ContractVersion,
    ReviewRequest,
    SignatureRequest,
)
from .lifecycle import (
    ContractStage,
    LifecycleEvent,
    LifecycleService,
    TransitionResult,
    normalize_stage,
)

DEFAULT_ROLES = ["business_owner", "legal", "finance", "executive"]
ALLOWED_DEMO_ROLES = frozenset(DEFAULT_ROLES)
OVERRIDE_ROLES = frozenset({"legal", "executive"})
ACTIVE_WORKFLOW = frozenset({"in_progress"})
TERMINAL_WORKFLOW = frozenset({"approved", "rejected", "changes_requested", "cancelled"})
RESOLVED_NEGOTIATION = frozenset({"accepted", "closed"})
USABLE_CONTRACT_STATUSES = frozenset({"ready", "needs_review"})
DECISIONS = frozenset({"approved", "rejected", "changes_requested"})
REASON_DECISIONS = frozenset({"rejected", "changes_requested"})
CLOSED_STEP_STATUSES = frozenset({"approved", "rejected", "changes_requested", "skipped"})
OPEN_STEP_STATUSES = frozenset({"pending", "locked"})
OVERRIDABLE_RULES = ("unresolved_negotiations",)
OVERRIDE_EVENT = "approval_override_used"


class ApprovalError(ValueError):
    def __init__(self, status_code: int, code: str, **payload):
        self.status_code = status_code
        self.code = code
        self.payload = {"error": code, **payload}
        super().__init__(code)


def _raise(status_code: int, code: str, **payload) -> None:
    raise ApprovalError(status_code, code, **payload)


def normalize_demo_role(role: str | None) -> str:
    if role in ALLOWED_DEMO_ROLES:
        return role
    return "legal"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def log_activity(
    db: Session,
    contract_id,
    event_type: str,
    *,
    actor: str | None = None,
    role: str | None = None,
    step_order: int | None = None,
    comment: str | None = None,
    metadata: dict | None = None,
) -> ActivityEvent:
    ev = ActivityEvent(
        id=uuid.uuid4(),
        contract_id=contract_id,
        event_type=event_type,
        actor=actor,
        role=role,
        step_order=step_order,
        comment=comment,
        event_metadata=metadata,
    )
    db.add(ev)
    return ev


def _reason_digest(reason: str) -> str:
    return hashlib.sha256(reason.encode("utf-8")).hexdigest()[:16]


def _reason_audit(reason: str | None) -> dict[str, Any]:
    """Reason evidence for broadly visible activity records, never the reason text."""
    clean = (reason or "").strip()
    if not clean:
        return {"reason_present": False}
    return {"reason_present": True, "reason_hash": _reason_digest(clean)}


def _stage(contract: Contract | None) -> ContractStage | None:
    if contract is None or not contract.stage:
        return None
    try:
        return normalize_stage(contract.stage)
    except Exception:
        return None


def _stage_value(contract: Contract | None) -> str | None:
    stage = _stage(contract)
    return stage.value if stage else None


def _lock_contract(contract_id, db: Session) -> Contract:
    contract = (
        db.query(Contract)
        .filter(Contract.id == contract_id)
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    if contract is None:
        _raise(404, "not_found")
    return contract


def _lock_workflow(workflow_id, db: Session) -> ApprovalWorkflow:
    workflow = (
        db.query(ApprovalWorkflow)
        .filter(ApprovalWorkflow.id == workflow_id)
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    if workflow is None:
        _raise(404, "approval_workflow_not_found")
    return workflow


def _lock_step(step_id, db: Session) -> ApprovalStep:
    step = (
        db.query(ApprovalStep)
        .filter(ApprovalStep.id == step_id)
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    if step is None:
        _raise(404, "approval_step_not_found")
    return step


def _locked_current_version(contract_id, db: Session) -> ContractVersion | None:
    rows = (
        db.query(ContractVersion)
        .filter(ContractVersion.contract_id == contract_id)
        .with_for_update()
        .order_by(ContractVersion.version_number.desc())
        .all()
    )
    return next((row for row in rows if row.is_current), None)


def _commit(db: Session, *refresh_rows) -> None:
    try:
        db.commit()
        for row in refresh_rows:
            db.refresh(row)
    except Exception:
        db.rollback()
        raise


def get_active_workflow(contract_id, db: Session) -> ApprovalWorkflow | None:
    return (
        db.query(ApprovalWorkflow)
        .filter_by(contract_id=contract_id, status="in_progress")
        .first()
    )


def _locked_active_workflow(contract_id, db: Session) -> ApprovalWorkflow | None:
    return (
        db.query(ApprovalWorkflow)
        .filter_by(contract_id=contract_id, status="in_progress")
        .with_for_update()
        .populate_existing()
        .first()
    )


def get_latest_workflow(contract_id, db: Session) -> ApprovalWorkflow | None:
    return (
        db.query(ApprovalWorkflow)
        .filter_by(contract_id=contract_id)
        .order_by(ApprovalWorkflow.created_at.desc())
        .first()
    )


def _active_signature_request(contract_id, db: Session) -> SignatureRequest | None:
    from .signature import ACTIVE_REQUEST_STATUSES

    return (
        db.query(SignatureRequest)
        .filter(SignatureRequest.contract_id == contract_id)
        .filter(SignatureRequest.status.in_(ACTIVE_REQUEST_STATUSES))
        .order_by(SignatureRequest.created_at.desc())
        .first()
    )


def _steps_for_workflow(workflow_id, db: Session) -> list[ApprovalStep]:
    return (
        db.query(ApprovalStep)
        .filter_by(workflow_id=workflow_id)
        .order_by(ApprovalStep.step_order.asc())
        .all()
    )


def _locked_steps(workflow_id, db: Session) -> list[ApprovalStep]:
    return (
        db.query(ApprovalStep)
        .filter_by(workflow_id=workflow_id)
        .with_for_update()
        .populate_existing()
        .order_by(ApprovalStep.step_order.asc())
        .all()
    )


def _negotiation_view(negotiation) -> dict:
    return {
        "id": str(negotiation.id),
        "clause_ref": negotiation.clause_ref,
        "workflow_status": negotiation.workflow_status,
    }


def _unresolved_for_version(contract_id, version_id, db: Session) -> list:
    from .negotiation import unresolved_for_version

    return unresolved_for_version(contract_id, version_id, db)


def unresolved_negotiations(contract_id, db: Session) -> list[dict]:
    """Current-version negotiation items that still block approval."""
    from .versions import current_version

    current = current_version(contract_id, db)
    if current is None:
        return []
    return [_negotiation_view(row) for row in _unresolved_for_version(contract_id, current.id, db)]


def _entry_evidence(contract: Contract, version: ContractVersion, db: Session) -> str | None:
    """Persisted proof that commercial terms were settled or formally waived."""
    approved_review = (
        db.query(ReviewRequest.id)
        .filter(
            ReviewRequest.contract_id == contract.id,
            ReviewRequest.version_id == version.id,
            ReviewRequest.status == "approved",
        )
        .first()
    )
    if approved_review is not None:
        return "client_review_approved"

    from .negotiation import NegotiationClosureOutcome, _closure_outcome
    from ..models import Negotiation

    negotiations = (
        db.query(Negotiation)
        .filter(Negotiation.contract_id == contract.id, Negotiation.version_id == version.id)
        .all()
    )
    for row in negotiations:
        if row.workflow_status == "accepted" or (
            row.workflow_status == "closed"
            and _closure_outcome(row) == NegotiationClosureOutcome.AGREEMENT_REACHED.value
        ):
            return "negotiation_agreement"

    waiver = (
        db.query(ActivityEvent.id)
        .filter(
            ActivityEvent.contract_id == contract.id,
            ActivityEvent.event_type == LifecycleEvent.CLIENT_REVIEW_WAIVED.value,
        )
        .first()
    )
    if waiver is not None:
        return "client_review_waived"
    return None


def _resolve_sequence(approver_names: dict | None) -> list[str]:
    names = approver_names or {}
    unknown = [role for role in names if role not in ALLOWED_DEMO_ROLES]
    if unknown:
        _raise(422, "invalid_approval_sequence", unknown_roles=sorted(unknown))
    sequence = list(DEFAULT_ROLES)
    if not sequence:
        _raise(422, "approvers_required")
    if len(set(sequence)) != len(sequence):
        _raise(422, "invalid_approval_sequence")
    return sequence


def _normalize_override(override: dict | None, *, force: bool) -> dict | None:
    """Structured override payload; unrestricted force is no longer accepted."""
    if override is None:
        if force:
            _raise(422, "approval_reason_required")
        return None
    reason = (override.get("reason") or "").strip()
    if not reason:
        _raise(422, "approval_reason_required")
    ids = [str(value) for value in (override.get("negotiation_ids") or [])]
    rules = [str(value) for value in (override.get("rules") or [])]
    invalid_rules = [rule for rule in rules if rule not in OVERRIDABLE_RULES]
    if invalid_rules:
        _raise(403, "forbidden_transition", rules=sorted(invalid_rules))
    return {"reason": reason, "negotiation_ids": ids, "rules": rules}


def _authorize_override(override: dict | None, role: str, unresolved: list) -> dict:
    blockers = [_negotiation_view(row) for row in unresolved]
    if override is None:
        _raise(409, "unresolved_negotiations", unresolved=blockers)
    if role not in OVERRIDE_ROLES:
        _raise(403, "approval_role_required", required_roles=sorted(OVERRIDE_ROLES))
    listed = set(override["negotiation_ids"])
    expected = {item["id"] for item in blockers}
    if listed != expected:
        _raise(
            409,
            "unresolved_negotiations",
            unresolved=[item for item in blockers if item["id"] not in listed],
        )
    return {
        "reason": override["reason"],
        "negotiation_ids": sorted(expected),
        "rules": list(OVERRIDABLE_RULES),
    }


def _safe_metadata(
    workflow: ApprovalWorkflow,
    *,
    version_id,
    role: str,
    actor_type: str = "internal",
    step: ApprovalStep | None = None,
    decision: str | None = None,
    extra: dict | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "contract_id": str(workflow.contract_id),
        "workflow_id": str(workflow.id),
        "version_id": str(version_id) if version_id else None,
        "role": role,
        "actor_type": actor_type,
        "timestamp": _iso(_utcnow()),
    }
    if step is not None:
        metadata["step_id"] = str(step.id)
        metadata["step_order"] = step.step_order
        metadata["step_role"] = step.role
    if decision:
        metadata["decision"] = decision
    if extra:
        metadata.update(extra)
    return metadata


def _log_stage_event(
    db: Session,
    contract_id,
    transition: TransitionResult,
    *,
    actor: str,
    role: str,
    metadata: dict,
) -> None:
    if not transition.changed:
        return
    log_activity(
        db,
        contract_id,
        transition.activity_event.value,
        actor=actor,
        role=role,
        metadata={
            **metadata,
            "from": transition.previous_stage.value,
            "to": transition.next_stage.value,
            "event": transition.event.value,
        },
    )


def _override_used(workflow: ApprovalWorkflow, db: Session) -> bool:
    return (
        db.query(ActivityEvent.id)
        .filter(
            ActivityEvent.contract_id == workflow.contract_id,
            ActivityEvent.event_type == OVERRIDE_EVENT,
            ActivityEvent.event_metadata["workflow_id"].astext == str(workflow.id),
        )
        .first()
        is not None
    )


def allowed_actions_for_role(workflow: ApprovalWorkflow | None, steps: list[ApprovalStep], role: str) -> list[str]:
    if workflow is None or workflow.status != "in_progress":
        return []
    current = next((s for s in steps if s.step_order == workflow.current_step_order), None)
    if current is None or current.status != "pending":
        return []
    if current.role != role:
        return []
    return ["approved", "rejected", "changes_requested"]


def serialize_step(s: ApprovalStep) -> dict:
    return {
        "id": str(s.id),
        "workflow_id": str(s.workflow_id),
        "contract_id": str(s.contract_id),
        "step_order": s.step_order,
        "role": s.role,
        "approver_name": s.approver_name,
        "status": s.status,
        "comment": s.comment,
        "acted_at": _iso(s.acted_at),
        "acted_by": s.acted_by,
    }


def serialize_workflow(w: ApprovalWorkflow, db: Session, demo_role: str) -> dict:
    from .versions import is_stale_workflow

    steps = _steps_for_workflow(w.id, db)
    current = next((s for s in steps if s.step_order == w.current_step_order), None)
    approved = sum(1 for s in steps if s.status == "approved")
    remaining = sum(1 for s in steps if s.status in OPEN_STEP_STATUSES)
    stale = is_stale_workflow(w, w.contract_id, db)
    contract = db.get(Contract, w.contract_id)
    stage = _stage_value(contract)
    actionable = (
        w.status in ACTIVE_WORKFLOW
        and not stale
        and current is not None
        and current.status == "pending"
        and stage == ContractStage.INTERNAL_REVIEW.value
    )
    allowed = allowed_actions_for_role(w, steps, demo_role) if actionable else []
    return {
        "id": str(w.id),
        "contract_id": str(w.contract_id),
        "status": w.status,
        "current_step_order": w.current_step_order,
        "started_by": w.started_by,
        "started_at": _iso(w.started_at),
        "completed_at": _iso(w.completed_at),
        "steps": [serialize_step(s) for s in steps],
        "current_step": serialize_step(current) if current else None,
        "allowed_actions": allowed,
        "next_allowed_actions": allowed,
        "approved_count": approved,
        "remaining_count": remaining,
        "completed_step_count": approved,
        "total_step_count": len(steps),
        "current_required_role": current.role if current and current.status == "pending" else None,
        "contract_stage": stage,
        "actionable": actionable,
        "stale": stale,
        "is_stale": stale,
        "override_used": _override_used(w, db),
        "version_id": str(w.version_id) if getattr(w, "version_id", None) else None,
    }


def start_workflow(
    contract_id,
    db: Session,
    *,
    approver_names: dict | None = None,
    actor: str = "demo",
    role: str | None = None,
    override: dict | None = None,
    force: bool = False,
) -> dict:
    acting_role = normalize_demo_role(role or actor)
    sequence = _resolve_sequence(approver_names)
    override_request = _normalize_override(override, force=force)
    names = approver_names or {}

    try:
        contract = _lock_contract(contract_id, db)
        current = _locked_current_version(contract_id, db)
        if current is None:
            _raise(409, "current_version_required")
        if _stage(contract) is not ContractStage.INTERNAL_REVIEW:
            _raise(409, "invalid_stage_transition", current_stage=contract.stage)
        if (contract.status or "") not in USABLE_CONTRACT_STATUSES or contract.supported is False:
            _raise(409, "contract_not_ready", contract_status=contract.status)
        evidence = _entry_evidence(contract, current, db)
        if evidence is None:
            _raise(409, "contract_not_ready", missing="approval_entry_evidence")
        if _locked_active_workflow(contract_id, db) is not None:
            _raise(409, "approval_already_active")
        if _active_signature_request(contract_id, db) is not None:
            _raise(409, "signature_request_active")

        unresolved = _unresolved_for_version(contract_id, current.id, db)
        override_granted = (
            _authorize_override(override_request, acting_role, unresolved) if unresolved else None
        )

        workflow = ApprovalWorkflow(
            id=uuid.uuid4(),
            contract_id=contract_id,
            version_id=current.id,
            status="in_progress",
            current_step_order=1,
            started_by=actor,
        )
        db.add(workflow)
        db.flush()

        for order, step_role in enumerate(sequence, start=1):
            db.add(
                ApprovalStep(
                    id=uuid.uuid4(),
                    workflow_id=workflow.id,
                    contract_id=contract_id,
                    step_order=order,
                    role=step_role,
                    approver_name=names.get(step_role),
                    status="pending" if order == 1 else "locked",
                )
            )

        base_metadata = _safe_metadata(
            workflow,
            version_id=current.id,
            role=acting_role,
            extra={"version_number": current.version_number, "entry_evidence": evidence},
        )

        if override_granted is not None:
            from .negotiation import close_for_approval_override

            close_for_approval_override(
                contract,
                current,
                unresolved,
                db,
                actor=actor,
                reason=override_granted["reason"],
            )
            log_activity(
                db,
                contract_id,
                OVERRIDE_EVENT,
                actor=actor,
                role=acting_role,
                metadata={
                    **base_metadata,
                    "overridden_negotiation_ids": override_granted["negotiation_ids"],
                    "overridden_rules": override_granted["rules"],
                    **_reason_audit(override_granted["reason"]),
                },
            )

        transition = LifecycleService.transition(
            contract,
            LifecycleEvent.APPROVAL_STARTED,
            actor,
            metadata={**base_metadata, "current_version": True, "workflow_active": False},
        )
        log_activity(
            db,
            contract_id,
            "approval_workflow_started",
            actor=actor,
            role=acting_role,
            step_order=1,
            metadata={
                **base_metadata,
                "override_used": override_granted is not None,
            },
        )
        log_activity(
            db,
            contract_id,
            "version_sent_for_approval",
            actor=actor,
            role=acting_role,
            metadata=base_metadata,
        )
        _log_stage_event(
            db,
            contract_id,
            transition,
            actor=actor,
            role=acting_role,
            metadata=base_metadata,
        )

        try:
            _commit(db, workflow, contract)
        except IntegrityError:
            _raise(409, "approval_already_active")
        return serialize_workflow(workflow, db, acting_role)
    except Exception:
        db.rollback()
        raise


def _validate_workflow_actionable(
    workflow: ApprovalWorkflow,
    contract: Contract,
    current: ContractVersion | None,
    db: Session,
) -> ContractVersion:
    if workflow.contract_id != contract.id:
        _raise(404, "approval_workflow_not_found")
    if workflow.status not in ACTIVE_WORKFLOW:
        _raise(409, "approval_step_closed", workflow_status=workflow.status)
    if current is None:
        _raise(409, "current_version_required")
    if workflow.version_id is None or str(workflow.version_id) != str(current.id):
        _raise(409, "workflow_stale")
    latest = get_latest_workflow(contract.id, db)
    if latest is not None and str(latest.id) != str(workflow.id):
        _raise(409, "workflow_stale")
    if _stage(contract) is not ContractStage.INTERNAL_REVIEW:
        _raise(409, "invalid_stage_transition", current_stage=contract.stage)
    return current


def _close_step(step: ApprovalStep, status: str, *, comment: str | None, actor: str, now: datetime) -> None:
    step.status = status
    step.comment = comment
    step.acted_at = now
    step.acted_by = actor
    step.updated_at = now


def _lock_remaining_steps(steps: list[ApprovalStep], *, acted_step_id, now: datetime) -> None:
    for row in steps:
        if row.id == acted_step_id:
            continue
        if row.status in OPEN_STEP_STATUSES:
            row.status = "locked"
            row.updated_at = now


def act_on_step(
    step_id,
    db: Session,
    *,
    decision: str,
    comment: str | None,
    demo_role: str,
    actor: str = "demo",
) -> dict:
    role = normalize_demo_role(demo_role)
    if decision not in DECISIONS:
        _raise(422, "invalid_transition_payload", field="status")
    clean_comment = (comment or "").strip()

    try:
        step = _lock_step(step_id, db)
        workflow = _lock_workflow(step.workflow_id, db)
        contract = _lock_contract(workflow.contract_id, db)
        current = _validate_workflow_actionable(
            workflow,
            contract,
            _locked_current_version(workflow.contract_id, db),
            db,
        )

        if step.role != role:
            _raise(403, "approval_role_required", required_role=step.role)
        if step.status in CLOSED_STEP_STATUSES:
            _raise(409, "approval_step_closed", step_status=step.status)
        if step.step_order != workflow.current_step_order or step.status != "pending":
            _raise(
                409,
                "approval_out_of_order",
                current_step_order=workflow.current_step_order,
            )
        if decision in REASON_DECISIONS and not clean_comment:
            _raise(422, "approval_reason_required")

        steps = _locked_steps(workflow.id, db)
        acted = next((row for row in steps if row.id == step.id), step)
        if any(row.status != "approved" for row in steps if row.step_order < acted.step_order):
            _raise(422, "invalid_approval_sequence")

        now = _utcnow()
        base_metadata = _safe_metadata(
            workflow,
            version_id=current.id,
            role=role,
            step=acted,
            decision=decision,
            extra={"version_number": current.version_number, **_reason_audit(clean_comment)},
        )

        if decision == "approved":
            _approve_step(
                db,
                contract=contract,
                workflow=workflow,
                steps=steps,
                step=acted,
                current=current,
                actor=actor,
                role=role,
                comment=clean_comment or None,
                metadata=base_metadata,
                now=now,
            )
        elif decision == "rejected":
            _reject_step(
                db,
                contract=contract,
                workflow=workflow,
                steps=steps,
                step=acted,
                actor=actor,
                role=role,
                comment=clean_comment,
                metadata=base_metadata,
                now=now,
            )
        else:
            _request_changes(
                db,
                contract=contract,
                workflow=workflow,
                steps=steps,
                step=acted,
                current=current,
                actor=actor,
                role=role,
                comment=clean_comment,
                metadata=base_metadata,
                now=now,
            )

        workflow.updated_at = now
        _commit(db, workflow, contract)
        return serialize_workflow(workflow, db, role)
    except Exception:
        db.rollback()
        raise


def _approve_step(
    db: Session,
    *,
    contract: Contract,
    workflow: ApprovalWorkflow,
    steps: list[ApprovalStep],
    step: ApprovalStep,
    current: ContractVersion,
    actor: str,
    role: str,
    comment: str | None,
    metadata: dict,
    now: datetime,
) -> None:
    final_order = max(row.step_order for row in steps)
    is_final = step.step_order >= final_order

    if is_final:
        unresolved = _unresolved_for_version(contract.id, current.id, db)
        if unresolved:
            _raise(
                409,
                "unresolved_negotiations",
                unresolved=[_negotiation_view(row) for row in unresolved],
            )
        if _active_signature_request(contract.id, db) is not None:
            _raise(409, "signature_request_active")

    _close_step(step, "approved", comment=comment, actor=actor, now=now)
    log_activity(
        db,
        contract.id,
        LifecycleEvent.APPROVAL_STEP_APPROVED.value,
        actor=actor,
        role=role,
        step_order=step.step_order,
        metadata=metadata,
    )

    if not is_final:
        next_step = next((row for row in steps if row.step_order == step.step_order + 1), None)
        if next_step is None:
            _raise(422, "invalid_approval_sequence")
        next_step.status = "pending"
        next_step.updated_at = now
        workflow.current_step_order = next_step.step_order
        LifecycleService.transition(
            contract,
            LifecycleEvent.APPROVAL_STEP_APPROVED,
            actor,
            metadata={**metadata, "current_version": True},
        )
        return None

    from .versions import mark_version_approved

    workflow.status = "approved"
    workflow.completed_at = now
    mark_version_approved(contract.id, workflow.id, db, commit=False)
    transition = LifecycleService.transition(
        contract,
        LifecycleEvent.APPROVAL_COMPLETED,
        actor,
        metadata={**metadata, "current_version": True, "approval_complete": True},
    )
    log_activity(
        db,
        contract.id,
        "approval_workflow_completed",
        actor=actor,
        role=role,
        metadata=metadata,
    )
    _log_stage_event(db, contract.id, transition, actor=actor, role=role, metadata=metadata)
    return None


def _reject_step(
    db: Session,
    *,
    contract: Contract,
    workflow: ApprovalWorkflow,
    steps: list[ApprovalStep],
    step: ApprovalStep,
    actor: str,
    role: str,
    comment: str,
    metadata: dict,
    now: datetime,
) -> None:
    _close_step(step, "rejected", comment=comment, actor=actor, now=now)
    _lock_remaining_steps(steps, acted_step_id=step.id, now=now)
    workflow.status = "rejected"
    workflow.completed_at = now
    transition = LifecycleService.transition(
        contract,
        LifecycleEvent.APPROVAL_REJECTED,
        actor,
        metadata={**metadata, "current_version": True, "comment": comment},
    )
    log_activity(
        db,
        contract.id,
        "approval_step_rejected",
        actor=actor,
        role=role,
        step_order=step.step_order,
        metadata=metadata,
    )
    log_activity(
        db,
        contract.id,
        LifecycleEvent.APPROVAL_REJECTED.value,
        actor=actor,
        role=role,
        metadata=metadata,
    )
    _log_stage_event(db, contract.id, transition, actor=actor, role=role, metadata=metadata)
    return None


def _request_changes(
    db: Session,
    *,
    contract: Contract,
    workflow: ApprovalWorkflow,
    steps: list[ApprovalStep],
    step: ApprovalStep,
    current: ContractVersion,
    actor: str,
    role: str,
    comment: str,
    metadata: dict,
    now: datetime,
) -> None:
    from .negotiation import seed_from_approval

    _close_step(step, "changes_requested", comment=comment, actor=actor, now=now)
    _lock_remaining_steps(steps, acted_step_id=step.id, now=now)
    workflow.status = "changes_requested"
    workflow.completed_at = now

    negotiation, created = seed_from_approval(
        contract,
        current,
        db,
        workflow_id=workflow.id,
        step_id=step.id,
        role=role,
        reason=comment,
    )
    seed_metadata = {**metadata, "negotiation_id": str(negotiation.id)}
    transition = LifecycleService.transition(
        contract,
        LifecycleEvent.APPROVAL_CHANGES_REQUESTED,
        actor,
        metadata={**seed_metadata, "current_version": True, "comment": comment},
    )
    log_activity(
        db,
        contract.id,
        LifecycleEvent.APPROVAL_CHANGES_REQUESTED.value,
        actor=actor,
        role=role,
        step_order=step.step_order,
        metadata=seed_metadata,
    )
    _log_stage_event(db, contract.id, transition, actor=actor, role=role, metadata=seed_metadata)
    if created:
        log_activity(
            db,
            contract.id,
            LifecycleEvent.NEGOTIATION_ANALYSIS_REQUESTED.value,
            actor=actor,
            role=role,
            metadata=seed_metadata,
        )
    return None


def cancel_workflow(
    contract_id,
    db: Session,
    *,
    actor: str = "demo",
    reason: str | None = None,
    role: str | None = None,
) -> dict:
    acting_role = normalize_demo_role(role or actor)
    clean_reason = (reason or "").strip()
    if not clean_reason:
        _raise(422, "approval_reason_required")

    try:
        contract = _lock_contract(contract_id, db)
        workflow = _locked_active_workflow(contract_id, db)
        if workflow is None:
            _raise(404, "approval_workflow_not_found")
        if _stage(contract) is not ContractStage.INTERNAL_REVIEW:
            _raise(409, "invalid_stage_transition", current_stage=contract.stage)

        from .versions import is_stale_workflow

        now = _utcnow()
        stale = is_stale_workflow(workflow, contract_id, db)
        steps = _locked_steps(workflow.id, db)
        _lock_remaining_steps(steps, acted_step_id=None, now=now)
        workflow.status = "cancelled"
        workflow.completed_at = now
        workflow.updated_at = now

        metadata = _safe_metadata(
            workflow,
            version_id=workflow.version_id,
            role=acting_role,
            extra={"stale_workflow": stale, **_reason_audit(clean_reason)},
        )
        transition = LifecycleService.transition(
            contract,
            LifecycleEvent.APPROVAL_CANCELLED,
            actor,
            metadata=metadata,
        )
        log_activity(
            db,
            contract_id,
            "approval_workflow_cancelled",
            actor=actor,
            role=acting_role,
            metadata=metadata,
        )
        _log_stage_event(
            db,
            contract_id,
            transition,
            actor=actor,
            role=acting_role,
            metadata=metadata,
        )
        _commit(db, workflow, contract)
        return serialize_workflow(workflow, db, acting_role)
    except Exception:
        db.rollback()
        raise


def list_activity(contract_id, db: Session) -> list[dict]:
    rows = (
        db.query(ActivityEvent)
        .filter_by(contract_id=contract_id)
        .order_by(ActivityEvent.created_at.desc())
        .all()
    )
    return [
        {
            "id": str(r.id),
            "event_type": r.event_type,
            "actor": r.actor,
            "role": r.role,
            "step_order": r.step_order,
            "comment": r.comment,
            "metadata": r.event_metadata,
            "created_at": _iso(r.created_at),
        }
        for r in rows
    ]


def approval_summary(db: Session) -> dict:
    """Dashboard KPI counts from real DB rows."""
    contracts = db.query(Contract).all()
    internal_review = sum(
        1 for c in contracts if _stage(c) is ContractStage.INTERNAL_REVIEW
    )
    awaiting_sig = sum(1 for c in contracts if _stage(c) is ContractStage.READY_TO_SIGN)
    pending_legal = pending_finance = pending_executive = pending_business = 0
    active = db.query(ApprovalWorkflow).filter_by(status="in_progress").all()
    for w in active:
        step = (
            db.query(ApprovalStep)
            .filter_by(workflow_id=w.id, step_order=w.current_step_order, status="pending")
            .first()
        )
        if not step:
            continue
        if step.role == "business_owner":
            pending_business += 1
        elif step.role == "legal":
            pending_legal += 1
        elif step.role == "finance":
            pending_finance += 1
        elif step.role == "executive":
            pending_executive += 1
    return {
        "internal_review": internal_review,
        "pending_business_owner": pending_business,
        "pending_legal": pending_legal,
        "pending_finance": pending_finance,
        "pending_executive": pending_executive,
        "approved_awaiting_signature": awaiting_sig,
    }
