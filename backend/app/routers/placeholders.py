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
from ..models import Contract, DemoSettings, Event
from ..ai.classifier import FLOWDOWN_ELIGIBLE
from ..services.deadlines import (
    build_deadlines_for_contract,
    deadline_summary,
    list_deadlines_for_contract,
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
# TODO(F3 — payment milestones engine):
# Read extractions.value_json where field_name='payment_milestones', insert
# rows into `payment_milestones` (status starts 'blocked'; preconditions is
# the jsonb list of strings), flip status blocked→claimable when linked events
# arrive. Replace static JSON with real DB reads.
# =====================================================================
@router.get("/contracts/{contract_id}/milestones")
def milestones_placeholder(contract_id: _uuid.UUID, response: Response):
    _ph(response)
    return [
        {"id": "00000000-0000-0000-0000-000000000011", "seq": 1, "label": "الدفعة المقدمة", "amount_sar": 1200000, "preconditions": ["خطاب ضمان الدفعة المقدمة"], "status": "paid", "source_clause_id": None},
        {"id": "00000000-0000-0000-0000-000000000012", "seq": 2, "label": "إنجاز الهيكل الإنشائي", "amount_sar": 3600000, "preconditions": ["اعتماد المهندس", "شهادة فحص"], "status": "claimable", "source_clause_id": None},
        {"id": "00000000-0000-0000-0000-000000000013", "seq": 3, "label": "التشطيبات", "amount_sar": 4800000, "preconditions": ["اعتماد المهندس"], "status": "blocked", "source_clause_id": None},
    ]


class MilestonePatch(BaseModel):
    status: str  # blocked | claimable | paid


# TODO(F3): persist to payment_milestones table, validate transitions.
@router.patch("/milestones/{milestone_id}")
def patch_milestone_placeholder(milestone_id: str, body: MilestonePatch, response: Response):
    _ph(response)
    return {"id": milestone_id, "status": body.status}


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
# TODO(F4 — flow-down comparison):
# Body: {main_contract_id, subcontract_id}. Compare main-contract obligations/
# penalties (clauses + extractions of BOTH contracts are already in the DB,
# every one with verified quotes) and write `flowdown_findings`
# (mirrored/partial/missing + risk_note + severity). The demo subcontract
# deliberately has NO back-to-back LD clause — your engine must flag it.
# =====================================================================
class FlowdownIn(BaseModel):
    main_contract_id: _uuid.UUID
    subcontract_id: _uuid.UUID


@router.post("/flowdown")
def flowdown_placeholder(body: FlowdownIn, response: Response, db: Session = Depends(get_db)):
    _ph(response)
    main = db.get(Contract, body.main_contract_id)
    sub = db.get(Contract, body.subcontract_id)
    if main is None or sub is None:
        raise HTTPException(404, detail={"error": "not_found"})
    for c, label in ((main, "main_contract_id"), (sub, "subcontract_id")):
        if c.contract_category not in FLOWDOWN_ELIGIBLE:
            raise HTTPException(
                422,
                detail={
                    "error": "flowdown_ineligible_category",
                    "field": label,
                    "contract_category": c.contract_category,
                },
            )
    return {
        "main_contract_id": str(body.main_contract_id),
        "subcontract_id": str(body.subcontract_id),
        "findings": [
            {"obligation_summary": "غرامة تأخير ٢٠٬٠٠٠ ريال/يوم في العقد الرئيسي", "status": "missing", "risk_note": "لا يوجد بند غرامة تأخير مقابل في عقد الباطن — مخاطرة غير مغطاة", "severity": "high"},
            {"obligation_summary": "التأمين الشامل", "status": "mirrored", "risk_note": None, "severity": "low"},
        ],
    }


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
