"""Public review portal — token auth only, no bearer token."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..services.lifecycle import LifecycleError
from ..services.reviews import (
    ReviewError,
    add_comment,
    build_public_payload,
    get_request_by_token,
    record_decision,
    serialize_review_request,
)

router = APIRouter(tags=["review-public"])


class RejectBody(BaseModel):
    reason: str = Field(max_length=4000)


class RequestChangesBody(BaseModel):
    general_comment: str | None = Field(default=None, max_length=4000)


class CommentBody(BaseModel):
    comment: str = Field(min_length=1, max_length=4000)
    clause_ref: str | None = None
    page: int | None = None


def _load(token: str, db: Session):
    req = get_request_by_token(token, db)
    if req is None:
        raise HTTPException(404, detail={"error": "review_not_found"})
    return req


def _review_http_error(error: Exception):
    if isinstance(error, (ReviewError, LifecycleError)):
        raise HTTPException(error.status_code, detail=error.payload)
    raise error


def _decision_result(req, db: Session) -> dict:
    serialized = serialize_review_request(req, db)
    return {
        "status": serialized["status"],
        "contract_stage": serialized["contract_stage"],
        "actionable": serialized["actionable"],
        "is_stale": serialized["is_stale"],
        "terminal_decision": serialized["terminal_decision"],
        "next_allowed_actions": serialized["next_allowed_actions"],
    }


@router.get("/review/{token}")
def get_review(token: str, db: Session = Depends(get_db)):
    req = _load(token, db)
    try:
        return build_public_payload(req, db)
    except (ReviewError, LifecycleError) as error:
        _review_http_error(error)


@router.post("/review/{token}/approve")
def approve_review(token: str, db: Session = Depends(get_db)):
    req = _load(token, db)
    try:
        record_decision(req, db, "approve", actor="client")
    except (ReviewError, LifecycleError) as error:
        _review_http_error(error)
    return _decision_result(req, db)


@router.post("/review/{token}/reject")
def reject_review(token: str, body: RejectBody, db: Session = Depends(get_db)):
    req = _load(token, db)
    try:
        record_decision(req, db, "reject", body.reason, actor="client")
    except (ReviewError, LifecycleError) as error:
        _review_http_error(error)
    return _decision_result(req, db)


@router.post("/review/{token}/request-changes")
def request_changes(token: str, body: RequestChangesBody, db: Session = Depends(get_db)):
    req = _load(token, db)
    try:
        record_decision(req, db, "changes_requested", body.general_comment, actor="client")
    except (ReviewError, LifecycleError) as error:
        _review_http_error(error)
    return _decision_result(req, db)


@router.post("/review/{token}/comment")
def post_comment(token: str, body: CommentBody, db: Session = Depends(get_db)):
    req = _load(token, db)
    try:
        cm = add_comment(req, db, body.comment, body.clause_ref, body.page)
    except (ReviewError, LifecycleError) as error:
        _review_http_error(error)
    return {
        "id": str(cm.id),
        "clause_ref": cm.clause_ref,
        "page": cm.page,
        "comment": cm.comment,
    }
