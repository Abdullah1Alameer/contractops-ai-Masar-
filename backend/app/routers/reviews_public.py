"""Public review portal — token auth only, no bearer token."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..services.reviews import (
    add_comment,
    build_public_payload,
    get_request_by_token,
    record_decision,
)

router = APIRouter(tags=["review-public"])


class RejectBody(BaseModel):
    reason: str = Field(min_length=1, max_length=4000)


class RequestChangesBody(BaseModel):
    general_comment: str = Field(min_length=1, max_length=4000)


class CommentBody(BaseModel):
    comment: str = Field(min_length=1, max_length=4000)
    clause_ref: str | None = None
    page: int | None = None


def _load(token: str, db: Session):
    req = get_request_by_token(token, db)
    if req is None:
        raise HTTPException(404, detail={"error": "not_found"})
    return req


def _closed_error(req, code: str = "review_closed"):
    if req.status == "expired":
        raise HTTPException(403, detail={"error": "review_expired", "read_only": True})
    raise HTTPException(403, detail={"error": code, "read_only": True})


@router.get("/review/{token}")
def get_review(token: str, db: Session = Depends(get_db)):
    req = _load(token, db)
    try:
        return build_public_payload(req, db)
    except ValueError as e:
        if str(e) == "not_found":
            raise HTTPException(404, detail={"error": "not_found"})
        raise


@router.post("/review/{token}/approve")
def approve_review(token: str, db: Session = Depends(get_db)):
    req = _load(token, db)
    try:
        record_decision(req, db, "approve")
    except ValueError as e:
        _closed_error(req, str(e))
    return {"status": req.status}


@router.post("/review/{token}/reject")
def reject_review(token: str, body: RejectBody, db: Session = Depends(get_db)):
    req = _load(token, db)
    try:
        record_decision(req, db, "reject", body.reason)
    except ValueError as e:
        _closed_error(req, str(e))
    return {"status": req.status}


@router.post("/review/{token}/request-changes")
def request_changes(token: str, body: RequestChangesBody, db: Session = Depends(get_db)):
    req = _load(token, db)
    try:
        record_decision(req, db, "changes_requested", body.general_comment)
    except ValueError as e:
        _closed_error(req, str(e))
    return {"status": req.status}


@router.post("/review/{token}/comment")
def post_comment(token: str, body: CommentBody, db: Session = Depends(get_db)):
    req = _load(token, db)
    try:
        cm = add_comment(req, db, body.comment, body.clause_ref, body.page)
    except ValueError as e:
        _closed_error(req, str(e))
    return {
        "id": str(cm.id),
        "clause_ref": cm.clause_ref,
        "page": cm.page,
        "comment": cm.comment,
    }
