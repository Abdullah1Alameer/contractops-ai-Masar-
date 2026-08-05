"""Feature 8 — Internal Legal Approval Workflow."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models import ActivityEvent, ApprovalStep, ApprovalWorkflow, Contract, Negotiation, ReviewRequest, ReviewResponse
from .lifecycle import can_start_approval, set_stage

DEFAULT_ROLES = ["business_owner", "legal", "finance", "executive"]
ALLOWED_DEMO_ROLES = frozenset(DEFAULT_ROLES)
ACTIVE_WORKFLOW = frozenset({"in_progress"})
TERMINAL_WORKFLOW = frozenset({"approved", "rejected", "changes_requested", "cancelled"})
RESOLVED_NEGOTIATION = frozenset({"accepted", "closed"})


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


def unresolved_negotiations(contract_id, db: Session) -> list[dict]:
    rows = db.query(Negotiation).filter_by(contract_id=contract_id).all()
    out = []
    for n in rows:
        ws = n.workflow_status or "pending_analysis"
        if ws not in RESOLVED_NEGOTIATION:
            out.append({"id": str(n.id), "clause_ref": n.clause_ref, "workflow_status": ws})
    return out


def get_active_workflow(contract_id, db: Session) -> ApprovalWorkflow | None:
    return (
        db.query(ApprovalWorkflow)
        .filter_by(contract_id=contract_id, status="in_progress")
        .first()
    )


def get_latest_workflow(contract_id, db: Session) -> ApprovalWorkflow | None:
    return (
        db.query(ApprovalWorkflow)
        .filter_by(contract_id=contract_id)
        .order_by(ApprovalWorkflow.created_at.desc())
        .first()
    )


def _steps_for_workflow(workflow_id, db: Session) -> list[ApprovalStep]:
    return (
        db.query(ApprovalStep)
        .filter_by(workflow_id=workflow_id)
        .order_by(ApprovalStep.step_order.asc())
        .all()
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
    remaining = sum(1 for s in steps if s.status in ("pending", "locked"))
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
        "allowed_actions": allowed_actions_for_role(w, steps, demo_role),
        "approved_count": approved,
        "remaining_count": remaining,
        "is_stale": is_stale_workflow(w, w.contract_id, db),
        "version_id": str(w.version_id) if getattr(w, "version_id", None) else None,
    }


def start_workflow(
    contract_id,
    db: Session,
    *,
    approver_names: dict | None = None,
    actor: str = "demo",
    force: bool = False,
) -> dict:
    contract = db.get(Contract, contract_id)
    if contract is None:
        raise ValueError("not_found")
    if not can_start_approval(contract):
        raise ValueError("contract_not_eligible")
    if get_active_workflow(contract_id, db):
        raise ValueError("workflow_already_active")

    unresolved = unresolved_negotiations(contract_id, db)
    metadata = None
    if unresolved and not force:
        raise ValueError("unresolved_negotiations")
    if unresolved and force:
        metadata = {"unresolved_negotiation_ids": [u["id"] for u in unresolved], "forced": True}

    names = approver_names or {}
    w = ApprovalWorkflow(
        id=uuid.uuid4(),
        contract_id=contract_id,
        status="in_progress",
        current_step_order=1,
        started_by=actor,
    )
    from .versions import current_version

    cur = current_version(contract_id, db)
    if cur:
        w.version_id = cur.id
    db.add(w)
    db.flush()

    for i, role in enumerate(DEFAULT_ROLES, start=1):
        st = ApprovalStep(
            id=uuid.uuid4(),
            workflow_id=w.id,
            contract_id=contract_id,
            step_order=i,
            role=role,
            approver_name=names.get(role),
            status="pending" if i == 1 else "locked",
        )
        db.add(st)

    set_stage(contract, "internal_review", db)
    log_activity(
        db,
        contract_id,
        "approval_workflow_started",
        actor=actor,
        role=normalize_demo_role(actor),
        step_order=1,
        metadata=metadata,
    )
    if cur:
        log_activity(db, contract_id, "version_sent_for_approval", actor=actor, metadata={"version_number": cur.version_number})
    db.commit()
    db.refresh(w)
    return serialize_workflow(w, db, normalize_demo_role(actor))


def act_on_step(
    step_id,
    db: Session,
    *,
    decision: str,
    comment: str | None,
    demo_role: str,
    actor: str = "demo",
) -> dict:
    step = db.get(ApprovalStep, step_id)
    if step is None:
        raise ValueError("not_found")
    w = db.get(ApprovalWorkflow, step.workflow_id)
    if w is None or w.status not in ACTIVE_WORKFLOW:
        raise ValueError("workflow_completed")

    role = normalize_demo_role(demo_role)
    if step.role != role:
        raise ValueError("wrong_role")
    if step.step_order != w.current_step_order or step.status != "pending":
        raise ValueError("out_of_order")

    if decision not in ("approved", "rejected", "changes_requested"):
        raise ValueError("invalid_decision")
    if decision in ("rejected", "changes_requested") and not (comment or "").strip():
        raise ValueError("comment_required")

    contract = db.get(Contract, w.contract_id)
    now = _utcnow()
    step.status = decision
    step.comment = comment
    step.acted_at = now
    step.acted_by = actor

    if decision == "approved":
        log_activity(
            db,
            w.contract_id,
            "approval_step_approved",
            actor=actor,
            role=role,
            step_order=step.step_order,
            comment=comment,
        )
        if step.step_order >= len(DEFAULT_ROLES):
            w.status = "approved"
            w.completed_at = now
            if contract:
                set_stage(contract, "approved", db)
            log_activity(db, w.contract_id, "approval_workflow_completed", actor=actor, role=role)
            from .versions import mark_version_approved

            mark_version_approved(w.contract_id, w.id, db)
        else:
            w.current_step_order = step.step_order + 1
            next_step = (
                db.query(ApprovalStep)
                .filter_by(workflow_id=w.id, step_order=w.current_step_order)
                .first()
            )
            if next_step:
                next_step.status = "pending"
    else:
        w.status = "rejected" if decision == "rejected" else "changes_requested"
        w.completed_at = now
        if contract:
            set_stage(contract, "negotiation", db)
        log_activity(
            db,
            w.contract_id,
            "approval_step_rejected" if decision == "rejected" else "approval_changes_requested",
            actor=actor,
            role=role,
            step_order=step.step_order,
            comment=comment,
        )
        log_activity(db, w.contract_id, "contract_returned_to_negotiation", actor=actor, role=role, comment=comment)

    w.updated_at = now
    db.commit()
    db.refresh(w)
    return serialize_workflow(w, db, role)


def cancel_workflow(contract_id, db: Session, *, actor: str = "demo") -> dict:
    w = get_active_workflow(contract_id, db)
    if w is None:
        raise ValueError("no_active_workflow")
    contract = db.get(Contract, contract_id)
    w.status = "cancelled"
    w.completed_at = _utcnow()
    if contract:
        set_stage(contract, "negotiation", db)
    log_activity(db, contract_id, "approval_workflow_cancelled", actor=actor)
    db.commit()
    db.refresh(w)
    return serialize_workflow(w, db, "legal")


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
    internal_review = sum(1 for c in contracts if c.stage == "internal_review")
    awaiting_sig = sum(1 for c in contracts if c.stage == "approved")
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
