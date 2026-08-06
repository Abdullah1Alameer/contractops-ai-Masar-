"""Public review portal — token auth only, no bearer token."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Contract
from ..services.lifecycle import LifecycleError
from ..services.negotiation import NegotiationError
from ..services.reviews import (
    ReviewError,
    add_comment,
    build_public_payload,
    expire_if_needed,
    get_request_by_token,
    hash_token,
    record_decision,
    serialize_review_request,
)
from ..services.signature_pdf import original_bytes
from ..services.rate_limit import check_rate_limit

router = APIRouter(tags=["review-public"])


class RejectBody(BaseModel):
    reason: str = Field(max_length=4000)


class RequestChangesBody(BaseModel):
    general_comment: str | None = Field(default=None, max_length=4000)


class CommentBody(BaseModel):
    comment: str = Field(min_length=1, max_length=4000)
    clause_ref: str | None = None
    page: int | None = None


def _rate(request: Request, token: str) -> None:
    ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(f"review-ip:{ip}"):
        raise HTTPException(429, detail={"error": "rate_limited"})
    token_digest = hash_token(token)
    if not check_rate_limit(f"review-token:{ip}:{token_digest}"):
        raise HTTPException(429, detail={"error": "rate_limited"})


def _load(token: str, db: Session):
    req = get_request_by_token(token, db)
    if req is None:
        raise HTTPException(404, detail={"error": "review_not_found"})
    return req


def _review_http_error(error: Exception):
    if isinstance(error, (ReviewError, LifecycleError, NegotiationError)):
        raise HTTPException(error.status_code, detail=error.payload)
    raise error


def _decision_result(req, db: Session) -> dict:
    serialized = serialize_review_request(req, db)
    result = {
        "status": serialized["status"],
        "contract_stage": serialized["contract_stage"],
        "actionable": serialized["actionable"],
        "is_stale": serialized["is_stale"],
        "terminal_decision": serialized["terminal_decision"],
        "next_allowed_actions": serialized["next_allowed_actions"],
    }
    negotiation_result = getattr(req, "_negotiation_result", None)
    if negotiation_result is not None:
        result["negotiation"] = negotiation_result
    return result


@router.get("/review/{token}")
def get_review(token: str, request: Request, db: Session = Depends(get_db)):
    _rate(request, token)
    req = _load(token, db)
    try:
        return build_public_payload(req, db)
    except (ReviewError, LifecycleError, NegotiationError) as error:
        _review_http_error(error)


@router.get("/review/{token}/document")
def get_review_document(token: str, request: Request, db: Session = Depends(get_db)):
    """The contract itself, as a guaranteed-renderable PDF — the same
    single source of truth (services/signature_pdf.py::original_bytes)
    already used by the signature flow: the real uploaded file when it is
    actually a PDF, otherwise a PDF generated from the extracted text.
    Gated by the same token validity/expiry check as every other route
    here — this is the actual (and only) authorization boundary for the
    public review portal; see docs/review-portal-document-access-redesign.md."""
    _rate(request, token)
    req = _load(token, db)
    try:
        expire_if_needed(req, db)
    except (ReviewError, LifecycleError, NegotiationError) as error:
        _review_http_error(error)
    contract = db.get(Contract, req.contract_id)
    if contract is None:
        raise HTTPException(404, detail={"error": "not_found"})
    data = original_bytes(contract)
    return Response(content=data, media_type="application/pdf")


@router.post("/review/{token}/approve")
def approve_review(token: str, request: Request, db: Session = Depends(get_db)):
    _rate(request, token)
    req = _load(token, db)
    try:
        record_decision(req, db, "approve", actor="client")
    except (ReviewError, LifecycleError, NegotiationError) as error:
        _review_http_error(error)
    return _decision_result(req, db)


@router.post("/review/{token}/reject")
def reject_review(
    token: str,
    body: RejectBody,
    request: Request,
    db: Session = Depends(get_db),
):
    _rate(request, token)
    req = _load(token, db)
    try:
        record_decision(req, db, "reject", body.reason, actor="client")
    except (ReviewError, LifecycleError, NegotiationError) as error:
        _review_http_error(error)
    return _decision_result(req, db)


@router.post("/review/{token}/request-changes")
def request_changes(
    token: str,
    body: RequestChangesBody,
    request: Request,
    db: Session = Depends(get_db),
):
    _rate(request, token)
    req = _load(token, db)
    try:
        record_decision(req, db, "changes_requested", body.general_comment, actor="client")
    except (ReviewError, LifecycleError, NegotiationError) as error:
        _review_http_error(error)
    return _decision_result(req, db)


@router.post("/review/{token}/comment")
def post_comment(
    token: str,
    body: CommentBody,
    request: Request,
    db: Session = Depends(get_db),
):
    _rate(request, token)
    req = _load(token, db)
    try:
        cm = add_comment(req, db, body.comment, body.clause_ref, body.page)
    except (ReviewError, LifecycleError, NegotiationError) as error:
        _review_http_error(error)
    return {
        "id": str(cm.id),
        "clause_ref": cm.clause_ref,
        "page": cm.page,
        "comment": cm.comment,
    }
