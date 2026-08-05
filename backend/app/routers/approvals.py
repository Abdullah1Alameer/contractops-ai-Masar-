"""Feature 8 — Internal Legal Approval API (protected + demo role header)."""
import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import demo_role
from ..models import ApprovalStep, Contract
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
    approver_names: dict[str, str] | None = None
    override: ApprovalOverrideBody | None = None
    force: bool = False


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
            approver_names=body.approver_names,
            actor=role,
            role=role,
            override=body.override.model_dump() if body.override else None,
            force=body.force,
        )
    except (ApprovalError, LifecycleError) as e:
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
