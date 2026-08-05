"""Protected review endpoints (demo bearer token)."""
import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Contract
from ..services.reviews import (
    build_email_template,
    create_review_request,
    list_reviews_for_contract,
    review_link,
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


@router.post("/contracts/{contract_id}/review/send")
def send_for_review(contract_id: _uuid.UUID, body: SendReviewBody, db: Session = Depends(get_db)):
    contract = db.get(Contract, contract_id)
    if contract is None:
        raise HTTPException(404, detail={"error": "not_found"})
    try:
        req = create_review_request(
            contract,
            db,
            recipient_name=body.recipient_name,
            recipient_email=body.recipient_email,
            message=body.message,
            sender_name=body.sender_name,
            sender_email=body.sender_email,
            expires_in_days=body.expires_in_days,
        )
    except ValueError as e:
        code = str(e)
        if code == "extraction_not_complete":
            raise HTTPException(409, detail={"error": code})
        if code == "contract_not_supported":
            raise HTTPException(422, detail={"error": code})
        raise HTTPException(400, detail={"error": code})

    link = review_link(req.token)
    email = build_email_template(req, contract, link)
    return {
        "review_link": link,
        "email": email,
        "request": serialize_review_request(req, db, include_token=True),
    }


@router.get("/contracts/{contract_id}/reviews")
def contract_review_history(contract_id: _uuid.UUID, db: Session = Depends(get_db)):
    if db.get(Contract, contract_id) is None:
        raise HTTPException(404, detail={"error": "not_found"})
    return list_reviews_for_contract(contract_id, db)


@router.get("/reviews/summary")
def review_summary_dashboard(db: Session = Depends(get_db)):
    return {"items": reviews_dashboard_summary(db)}
