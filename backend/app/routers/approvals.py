"""Feature 8 — Internal Legal Approval API (protected + demo role header)."""
import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import demo_role
from ..models import ApprovalStep, Contract
from ..services.approvals import (
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

router = APIRouter(tags=["approvals"])


class StartApprovalBody(BaseModel):
    approver_names: dict[str, str] | None = None
    force: bool = False


class PatchStepBody(BaseModel):
    status: str = Field(pattern="^(approved|rejected|changes_requested)$")
    comment: str | None = None


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
        wf = start_workflow(
            contract_id,
            db,
            approver_names=body.approver_names,
            actor=role,
            force=body.force,
        )
    except ValueError as e:
        code = str(e)
        if code == "unresolved_negotiations":
            raise HTTPException(
                409,
                detail={"error": code, "unresolved": unresolved_negotiations(contract_id, db)},
            )
        if code == "workflow_already_active":
            raise HTTPException(409, detail={"error": code})
        if code == "contract_not_eligible":
            raise HTTPException(422, detail={"error": code})
        raise HTTPException(400, detail={"error": code})
    return wf


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
        raise HTTPException(404, detail={"error": "not_found"})
    try:
        return act_on_step(step_id, db, decision=body.status, comment=body.comment, demo_role=role, actor=role)
    except ValueError as e:
        code = str(e)
        if code == "wrong_role":
            raise HTTPException(403, detail={"error": code})
        if code in ("out_of_order", "workflow_completed"):
            raise HTTPException(409, detail={"error": code})
        if code == "comment_required":
            raise HTTPException(422, detail={"error": code})
        raise HTTPException(400, detail={"error": code})


@router.post("/contracts/{contract_id}/approvals/cancel")
def approvals_cancel(contract_id: _uuid.UUID, db: Session = Depends(get_db), role: str = Depends(demo_role)):
    try:
        return cancel_workflow(contract_id, db, actor=role)
    except ValueError as e:
        if str(e) == "no_active_workflow":
            raise HTTPException(404, detail={"error": str(e)})
        raise HTTPException(400, detail={"error": str(e)})


@router.get("/contracts/{contract_id}/activity")
def contract_activity(contract_id: _uuid.UUID, db: Session = Depends(get_db)):
    if db.get(Contract, contract_id) is None:
        raise HTTPException(404, detail={"error": "not_found"})
    return {"events": list_activity(contract_id, db)}


@router.get("/approvals/summary")
def approvals_dashboard_summary(db: Session = Depends(get_db)):
    return approval_summary(db)
