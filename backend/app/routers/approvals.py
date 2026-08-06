"""Feature 8 — Internal Legal Approval API (protected + demo role header)."""
import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import demo_role
from ..models import ApprovalStep, Contract
from ..services.approval_routes import (
    APPROVER_ROLES,
    archive_route,
    configure_contract_route,
    create_route,
    get_contract_route,
    get_route_or_404,
    list_routes,
    serialize_contract_route,
    serialize_route,
    update_route,
)
from ..services.approvals import (
    ApprovalError,
    act_on_step,
    approval_summary,
    cancel_workflow,
    get_active_workflow,
    get_latest_workflow,
    list_activity,
    serialize_workflow,
    start_workflow,
    unresolved_negotiations,
)
from ..services.lifecycle import LifecycleError

router = APIRouter(tags=["approvals"])


class ApprovalOverrideBody(BaseModel):
    reason: str | None = None
    negotiation_ids: list[str] = Field(default_factory=list)
    rules: list[str] = Field(default_factory=list)


class StartApprovalBody(BaseModel):
    override: ApprovalOverrideBody | None = None
    force: bool = False


class RouteStepBody(BaseModel):
    role: str
    approver_name: str | None = None
    required: bool = True


class ConfigureRouteBody(BaseModel):
    name: str | None = None
    steps: list[RouteStepBody] = Field(min_length=1)
    source_route_id: str | None = None
    save_as_route: bool = False
    save_as_route_name: str | None = None


class SavedRouteBody(BaseModel):
    name: str
    steps: list[RouteStepBody] = Field(min_length=1)


class UpdateSavedRouteBody(BaseModel):
    name: str | None = None
    steps: list[RouteStepBody] | None = None


class PatchStepBody(BaseModel):
    status: str = Field(pattern="^(approved|rejected|changes_requested)$")
    comment: str | None = None


class CancelApprovalBody(BaseModel):
    reason: str | None = None


def _fail(error: ApprovalError | LifecycleError) -> HTTPException:
    return HTTPException(error.status_code, detail=error.payload)


@router.post("/contracts/{contract_id}/approvals/start")
def approvals_start(
    contract_id: _uuid.UUID,
    body: StartApprovalBody,
    db: Session = Depends(get_db),
    role: str = Depends(demo_role),
):
    if db.get(Contract, contract_id) is None:
        raise HTTPException(404, detail={"error": "not_found"})
    try:
        return start_workflow(
            contract_id,
            db,
            actor=role,
            role=role,
            override=body.override.model_dump() if body.override else None,
            force=body.force,
        )
    except (ApprovalError, LifecycleError) as e:
        raise _fail(e)


@router.get("/contracts/{contract_id}/approval-route")
def get_contract_route_route(contract_id: _uuid.UUID, db: Session = Depends(get_db), role: str = Depends(demo_role)):
    if db.get(Contract, contract_id) is None:
        raise HTTPException(404, detail={"error": "not_found"})
    route = get_contract_route(contract_id, db)
    return {"route": serialize_contract_route(route, db) if route else None}


@router.put("/contracts/{contract_id}/approval-route")
def configure_contract_route_route(
    contract_id: _uuid.UUID,
    body: ConfigureRouteBody,
    db: Session = Depends(get_db),
    role: str = Depends(demo_role),
):
    if db.get(Contract, contract_id) is None:
        raise HTTPException(404, detail={"error": "not_found"})
    try:
        return configure_contract_route(
            contract_id,
            db,
            name=body.name,
            steps=[s.model_dump() for s in body.steps],
            source_route_id=body.source_route_id,
            save_as_route=body.save_as_route,
            save_as_route_name=body.save_as_route_name,
            role=role,
            actor=role,
        )
    except ApprovalError as e:
        raise _fail(e)


@router.get("/approval-routes")
def list_saved_routes(include_inactive: bool = False, db: Session = Depends(get_db)):
    return {"routes": list_routes(db, include_inactive=include_inactive), "available_roles": sorted(APPROVER_ROLES)}


@router.post("/approval-routes", status_code=201)
def create_saved_route(body: SavedRouteBody, db: Session = Depends(get_db), role: str = Depends(demo_role)):
    try:
        return create_route(db, name=body.name, steps=[s.model_dump() for s in body.steps], role=role, actor=role)
    except ApprovalError as e:
        raise _fail(e)


@router.get("/approval-routes/{route_id}")
def get_saved_route(route_id: _uuid.UUID, db: Session = Depends(get_db)):
    try:
        return serialize_route(get_route_or_404(route_id, db), db)
    except ApprovalError as e:
        raise _fail(e)


@router.put("/approval-routes/{route_id}")
def update_saved_route(
    route_id: _uuid.UUID,
    body: UpdateSavedRouteBody,
    db: Session = Depends(get_db),
    role: str = Depends(demo_role),
):
    try:
        return update_route(
            route_id,
            db,
            name=body.name,
            steps=[s.model_dump() for s in body.steps] if body.steps is not None else None,
            role=role,
            actor=role,
        )
    except ApprovalError as e:
        raise _fail(e)


@router.post("/approval-routes/{route_id}/archive")
def archive_saved_route(route_id: _uuid.UUID, db: Session = Depends(get_db), role: str = Depends(demo_role)):
    try:
        return archive_route(route_id, db, role=role, actor=role)
    except ApprovalError as e:
        raise _fail(e)


@router.get("/contracts/{contract_id}/approvals")
def approvals_get(contract_id: _uuid.UUID, db: Session = Depends(get_db), role: str = Depends(demo_role)):
    if db.get(Contract, contract_id) is None:
        raise HTTPException(404, detail={"error": "not_found"})
    w = get_active_workflow(contract_id, db) or get_latest_workflow(contract_id, db)
    return {
        "workflow": serialize_workflow(w, db, role) if w else None,
        "unresolved_negotiations": unresolved_negotiations(contract_id, db),
    }


@router.patch("/approvals/{step_id}")
def approvals_patch_step(
    step_id: _uuid.UUID,
    body: PatchStepBody,
    db: Session = Depends(get_db),
    role: str = Depends(demo_role),
):
    if db.get(ApprovalStep, step_id) is None:
        raise HTTPException(404, detail={"error": "approval_step_not_found"})
    try:
        return act_on_step(step_id, db, decision=body.status, comment=body.comment, demo_role=role, actor=role)
    except (ApprovalError, LifecycleError) as e:
        raise _fail(e)


@router.post("/contracts/{contract_id}/approvals/cancel")
def approvals_cancel(
    contract_id: _uuid.UUID,
    body: CancelApprovalBody,
    db: Session = Depends(get_db),
    role: str = Depends(demo_role),
):
    if db.get(Contract, contract_id) is None:
        raise HTTPException(404, detail={"error": "not_found"})
    try:
        return cancel_workflow(contract_id, db, actor=role, role=role, reason=body.reason)
    except (ApprovalError, LifecycleError) as e:
        raise _fail(e)


@router.get("/contracts/{contract_id}/activity")
def contract_activity(contract_id: _uuid.UUID, db: Session = Depends(get_db)):
    if db.get(Contract, contract_id) is None:
        raise HTTPException(404, detail={"error": "not_found"})
    return {"events": list_activity(contract_id, db)}


@router.get("/approvals/summary")
def approvals_dashboard_summary(db: Session = Depends(get_db)):
    return approval_summary(db)
