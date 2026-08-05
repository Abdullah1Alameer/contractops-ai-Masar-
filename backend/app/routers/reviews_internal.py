"""Protected review endpoints (demo bearer token)."""
import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import demo_role
from ..models import Contract, ReviewRequest
from ..services.email_delivery import EmailDeliveryError
from ..services.lifecycle import LifecycleError
from ..services.reviews import (
    ReviewError,
    cancel_review,
    create_review_email,
    list_reviews_for_contract,
    resend_review_email,
    reviews_dashboard_summary,
    serialize_review_request,
)

router = APIRouter(tags=["reviews"])


class SendReviewBody(BaseModel):
    recipient_name: str = Field(min_length=1, max_length=200)
    recipient_email: str = Field(min_length=3, max_length=320)
    message: str | None = None
    sender_name: str | None = None
    sender_email: str | None = None
    expires_in_days: int = Field(default=14, ge=1, le=90)


class CancelReviewBody(BaseModel):
    reason: str


def _review_http_error(error: Exception):
    if isinstance(error, (ReviewError, LifecycleError)):
        raise HTTPException(error.status_code, detail=error.payload)
    if isinstance(error, EmailDeliveryError):
        raise HTTPException(error.status_code, detail={"error": error.code})
    raise error


@router.post("/contracts/{contract_id}/review/send")
def send_for_review(
    contract_id: _uuid.UUID,
    body: SendReviewBody,
    db: Session = Depends(get_db),
    actor: str = Depends(demo_role),
):
    contract = db.get(Contract, contract_id)
    if contract is None:
        raise HTTPException(404, detail={"error": "review_not_found"})
    try:
        return create_review_email(
            contract,
            db,
            actor=actor,
            recipient_name=body.recipient_name,
            recipient_email=body.recipient_email,
            message=body.message,
            sender_name=body.sender_name,
            sender_email=body.sender_email,
            expires_in_days=body.expires_in_days,
        )
    except (ReviewError, LifecycleError, EmailDeliveryError) as error:
        _review_http_error(error)


@router.post("/contracts/{contract_id}/reviews/{review_id}/resend")
def resend_contract_review_email(
    contract_id: _uuid.UUID,
    review_id: _uuid.UUID,
    db: Session = Depends(get_db),
    _actor: str = Depends(demo_role),
):
    req = db.get(ReviewRequest, review_id)
    if req is None or req.contract_id != contract_id:
        raise HTTPException(404, detail={"error": "review_not_found"})
    try:
        return resend_review_email(review_id, db)
    except (ReviewError, LifecycleError, EmailDeliveryError) as error:
        _review_http_error(error)


@router.post("/contracts/{contract_id}/reviews/{review_id}/cancel")
def cancel_contract_review(
    contract_id: _uuid.UUID,
    review_id: _uuid.UUID,
    body: CancelReviewBody,
    db: Session = Depends(get_db),
    actor: str = Depends(demo_role),
):
    req = db.get(ReviewRequest, review_id)
    if req is None or req.contract_id != contract_id:
        raise HTTPException(404, detail={"error": "review_not_found"})
    try:
        cancel_review(req, db, actor=actor, reason=body.reason)
    except (ReviewError, LifecycleError) as error:
        _review_http_error(error)
    return serialize_review_request(req, db)


@router.get("/contracts/{contract_id}/reviews")
def contract_review_history(contract_id: _uuid.UUID, db: Session = Depends(get_db)):
    if db.get(Contract, contract_id) is None:
        raise HTTPException(404, detail={"error": "review_not_found"})
    return list_reviews_for_contract(contract_id, db)


@router.get("/reviews/summary")
def review_summary_dashboard(db: Session = Depends(get_db)):
    return {"items": reviews_dashboard_summary(db)}
