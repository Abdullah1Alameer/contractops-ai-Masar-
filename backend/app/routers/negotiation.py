"""Feature 7 — Negotiation Assistant API (protected)."""
import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..ai.client import AIError
from ..db import get_db
from ..deps import demo_role
from ..models import Contract, Negotiation
from ..services.lifecycle import LifecycleError
from ..services.negotiation import (
    NegotiationError,
    abandon,
    analyze,
    apply_patch,
    list_negotiation_candidates,
    list_negotiations_for_contract,
    send_updated,
    serialize_negotiation,
)
from ..services.reviews import ReviewError

router = APIRouter(tags=["negotiation"])


class AnalyzeBody(BaseModel):
    review_id: str
    comment_id: str | None = None


class PatchNegotiationBody(BaseModel):
    ai_summary: str | None = None
    business_impact: str | None = None
    legal_impact: str | None = None
    risk_level: str | None = None
    recommendation: str | None = None
    reasoning: str | None = None
    counter_clause: str | None = None
    counter_clause_ar: str | None = None
    lawyer_final_clause: str | None = None
    lawyer_final_clause_ar: str | None = None
    workflow_status: str | None = None
    status: str | None = None


class AbandonNegotiationBody(BaseModel):
    reason: str = Field(default="", max_length=2000)


def _negotiation_http_error(error: Exception) -> None:
    if isinstance(error, (NegotiationError, ReviewError, LifecycleError)):
        raise HTTPException(status_code=error.status_code, detail=error.payload)
    code = str(error)
    raise HTTPException(status_code=400, detail={"error": code})


@router.post("/negotiation/analyze")
def negotiation_analyze(
    body: AnalyzeBody,
    db: Session = Depends(get_db),
    actor: str = Depends(demo_role),
):
    try:
        rid = _uuid.UUID(body.review_id)
        cid = _uuid.UUID(body.comment_id) if body.comment_id else None
        neg = analyze(rid, cid, db, actor=actor)
    except (NegotiationError, ReviewError, LifecycleError) as error:
        _negotiation_http_error(error)
    except ValueError as e:
        code = str(e)
        if code == "invalid_review":
            raise HTTPException(422, detail={"error": code})
        if code == "no_comment_or_reason":
            raise HTTPException(400, detail={"error": code})
        raise HTTPException(400, detail={"error": code})
    except AIError:
        raise HTTPException(502, detail={"error": "ai_failed", "retryable": True})
    return serialize_negotiation(neg, db)


@router.get("/contracts/{contract_id}/negotiations")
def get_contract_negotiations(contract_id: _uuid.UUID, db: Session = Depends(get_db)):
    if db.get(Contract, contract_id) is None:
        raise HTTPException(404, detail={"error": "not_found"})
    return {
        "negotiations": list_negotiations_for_contract(contract_id, db),
        "candidates": list_negotiation_candidates(contract_id, db),
    }


@router.patch("/negotiations/{negotiation_id}")
def patch_negotiation(
    negotiation_id: _uuid.UUID,
    body: PatchNegotiationBody,
    db: Session = Depends(get_db),
    actor: str = Depends(demo_role),
):
    neg = db.get(Negotiation, negotiation_id)
    if neg is None:
        raise HTTPException(404, detail={"error": "negotiation_not_found"})
    try:
        apply_patch(neg, body.model_dump(exclude_unset=True), db, actor=actor)
    except (NegotiationError, ReviewError, LifecycleError) as error:
        _negotiation_http_error(error)
    except ValueError as e:
        code = str(e)
        if code in ("invalid_risk_level", "invalid_recommendation", "invalid_status", "invalid_workflow_status"):
            raise HTTPException(422, detail={"error": code})
        if code == "negotiation_sent":
            raise HTTPException(409, detail={"error": code})
        raise HTTPException(400, detail={"error": code})
    return serialize_negotiation(neg, db)


@router.post("/negotiations/{negotiation_id}/send")
def send_negotiation(
    negotiation_id: _uuid.UUID,
    db: Session = Depends(get_db),
    actor: str = Depends(demo_role),
):
    neg = db.get(Negotiation, negotiation_id)
    if neg is None:
        raise HTTPException(404, detail={"error": "negotiation_not_found"})
    try:
        return send_updated(neg, db, actor=actor)
    except (NegotiationError, ReviewError, LifecycleError) as error:
        _negotiation_http_error(error)
    except ValueError as e:
        if str(e) == "negotiation_sent":
            raise HTTPException(409, detail={"error": str(e)})
        raise HTTPException(400, detail={"error": str(e)})


@router.post("/negotiations/{negotiation_id}/abandon")
def abandon_negotiation(
    negotiation_id: _uuid.UUID,
    body: AbandonNegotiationBody,
    db: Session = Depends(get_db),
    actor: str = Depends(demo_role),
):
    neg = db.get(Negotiation, negotiation_id)
    if neg is None:
        raise HTTPException(404, detail={"error": "negotiation_not_found"})
    try:
        return abandon(neg, db, actor=actor, reason=body.reason)
    except (NegotiationError, ReviewError, LifecycleError) as error:
        _negotiation_http_error(error)
