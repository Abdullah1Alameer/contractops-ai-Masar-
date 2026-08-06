"""Configurable approval routes and reusable route templates.

Before this, `start_workflow()` always built the same hardcoded
business_owner -> legal -> finance -> executive sequence — the
`approver_names` parameter it accepted was validated but never actually
used to change which roles or how many steps were created. This module
replaces that: a contract's approval route is configured explicitly
(`configure_contract_route`) before a workflow is ever started, optionally
copied from a reusable, org-scoped saved template (`ApprovalRoute`), and
only then snapshotted into real `ApprovalStep` rows by
`approvals.start_workflow()`.

See docs/configurable-approval-routes-report.md.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..deps import ALLOWED_DEMO_ROLES
from ..models import (
    ApprovalRoute,
    ApprovalRouteStep,
    ApprovalWorkflow,
    Contract,
    ContractApprovalRoute,
    ContractApprovalRouteStep,
)
from .approvals import (
    ROUTE_ADMIN_ROLES,
    ApprovalError,
    _lock_contract,
    _locked_active_workflow,
    _locked_current_version,
    _stage,
    ContractStage,
    log_activity,
    normalize_demo_role,
)

# The set of roles a route step may require. This is the same set the demo
# role switcher (X-Demo-Role) can claim — a step assigned to a role can
# only ever be acted on by someone presenting that identity, so the two
# must stay in sync. "sales" and "manager" were added here (and to
# ALLOWED_DEMO_ROLES) specifically to support routes like
# "Sales -> Legal -> Manager" from the spec's examples.
APPROVER_ROLES = ALLOWED_DEMO_ROLES


def _raise(status_code: int, code: str, **payload) -> None:
    raise ApprovalError(status_code, code, **payload)


def _require_route_admin(role: str) -> str:
    acting_role = normalize_demo_role(role)
    if acting_role not in ROUTE_ADMIN_ROLES:
        _raise(403, "approval_route_role_required", required_roles=sorted(ROUTE_ADMIN_ROLES))
    return acting_role


def _validate_steps(steps: list[dict]) -> list[dict]:
    if not steps:
        _raise(422, "approval_steps_required")
    seen: set[tuple[str, str | None]] = set()
    clean = []
    for raw in steps:
        role = (raw.get("role") or "").strip()
        if role not in APPROVER_ROLES:
            _raise(422, "invalid_approver", role=role)
        approver_name = (raw.get("approver_name") or "").strip() or None
        # Two steps requiring the *same* role are only distinguishable (and
        # therefore only allowed) if they're pinned to different named
        # approvers — otherwise the same acting identity would be asked to
        # approve its own earlier step, which is never a meaningful route.
        key = (role, approver_name)
        if key in seen:
            _raise(422, "duplicate_approver", role=role, approver_name=approver_name)
        seen.add(key)
        clean.append(
            {
                "role": role,
                "approver_name": approver_name,
                "required": bool(raw.get("required", True)),
            }
        )
    return clean


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


# --- Reusable saved route templates -----------------------------------


def serialize_route_step(s: ApprovalRouteStep) -> dict:
    return {
        "id": str(s.id),
        "step_order": s.step_order,
        "role": s.role,
        "approver_name": s.approver_name,
        "required": s.required,
    }


def serialize_route(route: ApprovalRoute, db: Session) -> dict:
    steps = (
        db.query(ApprovalRouteStep)
        .filter_by(route_id=route.id)
        .order_by(ApprovalRouteStep.step_order.asc())
        .all()
    )
    return {
        "id": str(route.id),
        "name": route.name,
        "scope": route.scope,
        "active": route.active,
        "created_by": route.created_by,
        "created_at": _iso(route.created_at),
        "updated_at": _iso(route.updated_at),
        "steps": [serialize_route_step(s) for s in steps],
        "step_count": len(steps),
    }


def list_routes(db: Session, *, include_inactive: bool = False) -> list[dict]:
    query = db.query(ApprovalRoute)
    if not include_inactive:
        query = query.filter_by(active=True)
    routes = query.order_by(ApprovalRoute.name.asc()).all()
    return [serialize_route(r, db) for r in routes]


def get_route_or_404(route_id, db: Session) -> ApprovalRoute:
    route = db.get(ApprovalRoute, route_id)
    if route is None:
        _raise(404, "approval_route_not_found")
    return route


def create_route(db: Session, *, name: str, steps: list[dict], role: str, actor: str = "demo") -> dict:
    acting_role = _require_route_admin(role)
    clean_name = (name or "").strip()
    if not clean_name:
        _raise(422, "approval_route_required")
    clean_steps = _validate_steps(steps)
    try:
        route = ApprovalRoute(id=uuid.uuid4(), name=clean_name, active=True, created_by=actor)
        db.add(route)
        db.flush()
        for order, step in enumerate(clean_steps, start=1):
            db.add(
                ApprovalRouteStep(
                    id=uuid.uuid4(),
                    route_id=route.id,
                    step_order=order,
                    role=step["role"],
                    approver_name=step["approver_name"],
                    required=step["required"],
                )
            )
        db.commit()
        db.refresh(route)
    except Exception:
        db.rollback()
        raise
    return serialize_route(route, db)


def update_route(
    route_id, db: Session, *, name: str | None, steps: list[dict] | None, role: str, actor: str = "demo"
) -> dict:
    """Edits only this template. Any contract-specific copy already made
    from it (draft, started, or historical) is a separate row and is never
    touched here — that is the whole point of copying instead of
    referencing."""
    _require_route_admin(role)
    route = get_route_or_404(route_id, db)
    try:
        if name is not None:
            clean_name = name.strip()
            if not clean_name:
                _raise(422, "approval_route_required")
            route.name = clean_name
        if steps is not None:
            clean_steps = _validate_steps(steps)
            db.query(ApprovalRouteStep).filter_by(route_id=route.id).delete()
            for order, step in enumerate(clean_steps, start=1):
                db.add(
                    ApprovalRouteStep(
                        id=uuid.uuid4(),
                        route_id=route.id,
                        step_order=order,
                        role=step["role"],
                        approver_name=step["approver_name"],
                        required=step["required"],
                    )
                )
        route.updated_at = _utcnow()
        db.commit()
        db.refresh(route)
    except Exception:
        db.rollback()
        raise
    return serialize_route(route, db)


def archive_route(route_id, db: Session, *, role: str, actor: str = "demo") -> dict:
    _require_route_admin(role)
    route = get_route_or_404(route_id, db)
    try:
        route.active = False
        route.updated_at = _utcnow()
        db.commit()
        db.refresh(route)
    except Exception:
        db.rollback()
        raise
    return serialize_route(route, db)


# --- Contract-specific configured route --------------------------------


def serialize_contract_route_step(s: ContractApprovalRouteStep) -> dict:
    return {
        "id": str(s.id),
        "step_order": s.step_order,
        "role": s.role,
        "approver_name": s.approver_name,
        "required": s.required,
    }


def serialize_contract_route(route: ContractApprovalRoute, db: Session) -> dict:
    steps = (
        db.query(ContractApprovalRouteStep)
        .filter_by(contract_route_id=route.id)
        .order_by(ContractApprovalRouteStep.step_order.asc())
        .all()
    )
    return {
        "id": str(route.id),
        "contract_id": str(route.contract_id),
        "name": route.name,
        "source_route_id": str(route.source_route_id) if route.source_route_id else None,
        "status": route.status,
        "created_by": route.created_by,
        "created_at": _iso(route.created_at),
        "updated_at": _iso(route.updated_at),
        "steps": [serialize_contract_route_step(s) for s in steps],
        "step_count": len(steps),
        "workflow_type": "sequential",
    }


def get_contract_route(contract_id, db: Session) -> ContractApprovalRoute | None:
    """Latest configured route for the contract, in any status — used by
    the GET endpoint so the frontend can resume the builder, show the
    locked route while a workflow runs, or show the last historical one."""
    return (
        db.query(ContractApprovalRoute)
        .filter_by(contract_id=contract_id)
        .order_by(ContractApprovalRoute.created_at.desc())
        .first()
    )


def get_draft_route_with_steps(contract_id, db: Session):
    route = (
        db.query(ContractApprovalRoute)
        .filter_by(contract_id=contract_id, status="draft")
        .order_by(ContractApprovalRoute.created_at.desc())
        .first()
    )
    if route is None:
        return None
    route_steps = (
        db.query(ContractApprovalRouteStep)
        .filter_by(contract_route_id=route.id)
        .order_by(ContractApprovalRouteStep.step_order.asc())
        .all()
    )
    return route, route_steps


def mark_route_started(route: ContractApprovalRoute, db: Session) -> None:
    route.status = "started"
    route.updated_at = _utcnow()
    db.add(route)


def mark_route_cancelled(route_id, db: Session) -> None:
    route = db.get(ContractApprovalRoute, route_id)
    if route is not None:
        route.status = "cancelled"
        route.updated_at = _utcnow()
        db.add(route)


def configure_contract_route(
    contract_id,
    db: Session,
    *,
    name: str | None,
    steps: list[dict],
    source_route_id=None,
    save_as_route: bool = False,
    save_as_route_name: str | None = None,
    role: str,
    actor: str = "demo",
) -> dict:
    """Validates and persists the draft route for a contract. Callable
    repeatedly before a workflow starts — each call replaces the contract's
    current draft (this is the "route may be edited... before any step is
    completed" requirement). Once a workflow is active, this raises
    approval_route_locked; the caller must cancel it first."""
    acting_role = _require_route_admin(role)
    clean_steps = _validate_steps(steps)

    try:
        contract = _lock_contract(contract_id, db)
        if _stage(contract) is not ContractStage.INTERNAL_REVIEW:
            _raise(409, "invalid_stage_transition", current_stage=contract.stage)
        if _locked_active_workflow(contract_id, db) is not None:
            _raise(409, "approval_route_locked")

        current_version = _locked_current_version(contract_id, db)

        # Replace any prior draft in place (delete + recreate) rather than
        # accumulating rows — a started or cancelled route from an earlier
        # attempt is left untouched, since it belongs to a real (even if
        # closed) workflow's history.
        existing_draft = (
            db.query(ContractApprovalRoute)
            .filter_by(contract_id=contract_id, status="draft")
            .first()
        )
        if existing_draft is not None:
            db.delete(existing_draft)
            db.flush()

        route = ContractApprovalRoute(
            id=uuid.uuid4(),
            contract_id=contract_id,
            version_id=current_version.id if current_version else None,
            name=(name or "").strip() or None,
            source_route_id=source_route_id,
            status="draft",
            created_by=actor,
        )
        db.add(route)
        db.flush()
        for order, step in enumerate(clean_steps, start=1):
            db.add(
                ContractApprovalRouteStep(
                    id=uuid.uuid4(),
                    contract_route_id=route.id,
                    step_order=order,
                    role=step["role"],
                    approver_name=step["approver_name"],
                    required=step["required"],
                )
            )

        saved_template = None
        if save_as_route:
            template_name = (save_as_route_name or name or "").strip()
            if not template_name:
                _raise(422, "approval_route_required")
            saved = ApprovalRoute(id=uuid.uuid4(), name=template_name, active=True, created_by=actor)
            db.add(saved)
            db.flush()
            for order, step in enumerate(clean_steps, start=1):
                db.add(
                    ApprovalRouteStep(
                        id=uuid.uuid4(),
                        route_id=saved.id,
                        step_order=order,
                        role=step["role"],
                        approver_name=step["approver_name"],
                        required=step["required"],
                    )
                )
            saved_template = saved

        log_activity(
            db,
            contract_id,
            "approval_route_configured",
            actor=actor,
            role=acting_role,
            metadata={
                "route_id": str(route.id),
                "route_name": route.name,
                "step_count": len(clean_steps),
                "roles": [s["role"] for s in clean_steps],
                "source_route_id": str(source_route_id) if source_route_id else None,
                "saved_as_route": save_as_route,
                "saved_route_id": str(saved_template.id) if saved_template else None,
            },
        )
        db.commit()
        db.refresh(route)
    except Exception:
        db.rollback()
        raise
    return serialize_contract_route(route, db)
