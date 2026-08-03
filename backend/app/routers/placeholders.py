"""Placeholder endpoints for F2/F3/F4/F5 — return realistic static seed JSON
with header "X-Placeholder: true" so the frontend can already render the shape.

EXCEPTION: /demo/today is implemented FOR REAL (demo clock) — F2/F5 need it.

Each block below documents exactly what the owning teammate must implement.
"""
import uuid as _uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Clause, Contract, DemoSettings, Event, Extraction, PaymentMilestone
from ..services.deadlines import (
    build_deadlines_for_contract,
    deadline_summary,
    list_deadlines_for_contract,
)
from ..services.payments import (
    _extr_milestones_by_seq,
    apply_milestone_patch,
    build_payment_milestones_for_contract,
    get_demo_today as payments_demo_today,
    list_payment_milestones_for_contract,
    payments_summary,
    serialize_milestone,
)
from ..services.flowdown import (
    list_flowdown_contracts,
    list_flowdown_for_pair,
    run_flowdown,
)

router = APIRouter(tags=["placeholders"])


def _ph(response: Response):
    response.headers["X-Placeholder"] = "true"


# =====================================================================
# F2 — Time-Bar Guardian (real)
# =====================================================================
_READY = frozenset({"ready", "needs_review"})


def _require_contract_ready(contract: Contract | None):
    if contract is None:
        raise HTTPException(404, detail={"error": "not_found"})
    if contract.status not in _READY:
        raise HTTPException(409, detail={"error": "extraction_not_complete", "status": contract.status})


@router.get("/contracts/{contract_id}/deadlines")
def get_contract_deadlines(contract_id: _uuid.UUID, db: Session = Depends(get_db)):
    contract = db.get(Contract, contract_id)
    _require_contract_ready(contract)
    try:
        items = list_deadlines_for_contract(contract_id, db)
    except ValueError:
        raise HTTPException(404, detail={"error": "not_found"})
    return {"deadlines": items, "summary": deadline_summary(items)}


@router.post("/contracts/{contract_id}/deadlines/rebuild")
def rebuild_contract_deadlines(contract_id: _uuid.UUID, db: Session = Depends(get_db)):
    contract = db.get(Contract, contract_id)
    _require_contract_ready(contract)
    try:
        build_deadlines_for_contract(contract_id, db)
        db.commit()
        items = list_deadlines_for_contract(contract_id, db)
    except ValueError:
        raise HTTPException(404, detail={"error": "not_found"})
    return {"deadlines": items, "summary": deadline_summary(items)}


# =====================================================================
# F3 — Payment Conditions Tracker (real)
# =====================================================================
@router.get("/contracts/{contract_id}/milestones")
def get_contract_milestones(contract_id: _uuid.UUID, db: Session = Depends(get_db)):
    contract = db.get(Contract, contract_id)
    _require_contract_ready(contract)
    try:
        items = list_payment_milestones_for_contract(contract_id, db)
    except ValueError:
        raise HTTPException(404, detail={"error": "not_found"})
    return {"milestones": items, "summary": payments_summary(items, contract)}


@router.post("/contracts/{contract_id}/milestones/rebuild")
def rebuild_contract_milestones(contract_id: _uuid.UUID, db: Session = Depends(get_db)):
    contract = db.get(Contract, contract_id)
    _require_contract_ready(contract)
    try:
        build_payment_milestones_for_contract(contract_id, db)
        db.commit()
        items = list_payment_milestones_for_contract(contract_id, db)
    except ValueError:
        raise HTTPException(404, detail={"error": "not_found"})
    return {"milestones": items, "summary": payments_summary(items, contract)}


class MilestonePatch(BaseModel):
    paid: bool | None = None
    precondition_id: str | None = None
    completed: bool | None = None
    preconditions: list | None = None


@router.patch("/milestones/{milestone_id}")
def patch_milestone(milestone_id: _uuid.UUID, body: MilestonePatch, db: Session = Depends(get_db)):
    milestone = db.get(PaymentMilestone, milestone_id)
    if milestone is None:
        raise HTTPException(404, detail={"error": "not_found"})
    contract = db.get(Contract, milestone.contract_id)
    _require_contract_ready(contract)

    payload = body.model_dump(exclude_unset=True)
    if not payload:
        raise HTTPException(400, detail={"error": "invalid_patch"})

    today = payments_demo_today(db)
    try:
        apply_milestone_patch(milestone, payload, today)
    except ValueError as e:
        code = str(e)
        if code == "invalid_precondition_id":
            raise HTTPException(400, detail={"error": "invalid_precondition_id"})
        raise HTTPException(400, detail={"error": "invalid_patch"})

    db.commit()
    db.refresh(milestone)

    extractions = db.query(Extraction).filter_by(contract_id=milestone.contract_id).all()
    by_seq = _extr_milestones_by_seq(extractions)
    extr_item = by_seq.get(milestone.seq)
    clause = db.get(Clause, milestone.source_clause_id) if milestone.source_clause_id else None
    return serialize_milestone(milestone, today, extr_item, clause)


# =====================================================================
# TODO(F2): insert into `events` table, then re-evaluate triggered deadlines
# (e.g. event 'delay_notice' opens a notice_window deadline of N days from
# event_date using notice_periods extracted by F1).
# =====================================================================
class EventIn(BaseModel):
    type: str
    description: str | None = None
    event_date: date


@router.post("/contracts/{contract_id}/events", status_code=201)
def post_contract_event(contract_id: _uuid.UUID, body: EventIn, db: Session = Depends(get_db)):
    contract = db.get(Contract, contract_id)
    _require_contract_ready(contract)
    ev = Event(
        id=_uuid.uuid4(),
        contract_id=contract_id,
        type=body.type,
        description=body.description,
        event_date=body.event_date,
    )
    db.add(ev)
    db.flush()
    build_deadlines_for_contract(contract_id, db)
    db.commit()
    items = list_deadlines_for_contract(contract_id, db)
    return {
        "event": {
            "id": str(ev.id),
            "contract_id": str(contract_id),
            "type": ev.type,
            "description": ev.description,
            "event_date": ev.event_date.isoformat(),
        },
        "deadlines": items,
        "summary": deadline_summary(items),
    }


# =====================================================================
# F4 — Flow-Down X-Ray (real)
# =====================================================================
@router.get("/flowdown/contracts")
def get_flowdown_contracts(db: Session = Depends(get_db)):
    return list_flowdown_contracts(db)


@router.get("/flowdown")
def get_flowdown_pair(main_id: _uuid.UUID, sub_id: _uuid.UUID, db: Session = Depends(get_db)):
    result = list_flowdown_for_pair(main_id, sub_id, db)
    if result is None:
        main = db.get(Contract, main_id)
        sub = db.get(Contract, sub_id)
        if main is None or sub is None:
            raise HTTPException(404, detail={"error": "not_found"})
        return {
            "main": {"id": str(main_id), "title": main.title},
            "sub": {"id": str(sub_id), "title": sub.title},
            "findings": [],
            "summary": {
                "overall_risk_score": 0,
                "critical_count": 0,
                "missing_count": 0,
                "conflict_count": 0,
                "coverage_pct": 0,
                "total": 0,
            },
        }
    return result


class FlowdownIn(BaseModel):
    main_contract_id: _uuid.UUID
    subcontract_id: _uuid.UUID


@router.post("/flowdown")
def post_flowdown(body: FlowdownIn, db: Session = Depends(get_db)):
    try:
        return run_flowdown(body.main_contract_id, body.subcontract_id, db)
    except ValueError as e:
        code = str(e)
        if code == "not_found":
            raise HTTPException(404, detail={"error": "not_found"})
        if code == "extraction_not_complete":
            raise HTTPException(409, detail={"error": "extraction_not_complete"})
        if code == "flowdown_wrong_pair":
            raise HTTPException(422, detail={"error": "flowdown_wrong_pair"})
        if code in ("flowdown_ineligible_main", "flowdown_ineligible_sub"):
            field = "main_contract_id" if code == "flowdown_ineligible_main" else "subcontract_id"
            c = db.get(Contract, body.main_contract_id if field == "main_contract_id" else body.subcontract_id)
            raise HTTPException(
                422,
                detail={
                    "error": "flowdown_ineligible_category",
                    "field": field,
                    "contract_category": c.contract_category if c else None,
                },
            )
        if code == "ai_failed":
            raise HTTPException(500, detail={"error": "ai_failed"})
        raise HTTPException(400, detail={"error": code})


# =====================================================================
# TODO(F5 — dashboard):
# Aggregate real numbers: contracts by status, deadlines within 30 days of
# the demo clock, overdue obligations, claimable milestones total.
# =====================================================================
@router.get("/dashboard")
def dashboard_placeholder(response: Response):
    _ph(response)
    return {
        "contracts": {"total": 2, "ready": 2, "needs_review": 0, "processing": 0, "failed": 0},
        "deadlines_next_30_days": 3,
        "overdue_obligations": 1,
        "claimable_milestones_sar": 3600000,
    }


# =====================================================================
# REAL implementation — demo clock (trivial, teammates depend on it).
# =====================================================================
class TodayIn(BaseModel):
    today: date


@router.get("/demo/today")
def get_demo_today(db: Session = Depends(get_db)):
    row = db.get(DemoSettings, 1)
    if row is None:
        row = DemoSettings(id=1, today=date.today())
        db.add(row)
        db.commit()
    return {"today": row.today.isoformat()}


@router.post("/demo/today")
def set_demo_today(body: TodayIn, db: Session = Depends(get_db)):
    row = db.get(DemoSettings, 1)
    if row is None:
        row = DemoSettings(id=1, today=body.today)
        db.add(row)
    else:
        row.today = body.today
    db.commit()
    return {"today": row.today.isoformat()}
