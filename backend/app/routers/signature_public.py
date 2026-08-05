"""Public signer portal — token only, no bearer."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..services import signature as sig_svc
from ..services.email_delivery import EmailDeliveryError
from ..services.lifecycle import LifecycleError
from ..services.rate_limit import check_rate_limit

router = APIRouter(tags=["signature-public"])


class SubmitBody(BaseModel):
    signature_type: str
    signature_value: str = Field(min_length=1)
    consent_accepted: bool
    signer_name_confirmation: str = Field(min_length=1, max_length=200)


class DeclineBody(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


def _rate(request: Request, token: str) -> None:
    ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(f"sign:{ip}:{token[:8]}"):
        raise HTTPException(429, detail={"error": "rate_limited"})


def _public_err(e: Exception) -> HTTPException:
    if isinstance(e, sig_svc.SignatureError):
        return HTTPException(e.status_code, detail=e.payload)
    if isinstance(e, LifecycleError):
        return HTTPException(e.status_code, detail=e.payload)
    if isinstance(e, EmailDeliveryError):
        return HTTPException(e.status_code, detail={"error": e.code})
    code = str(e)
    if code == "expired":
        return HTTPException(410, detail={"error": code})
    if code in ("not_active_signer", "request_closed"):
        return HTTPException(409, detail={"error": code})
    if code == "not_found":
        return HTTPException(404, detail={"error": code})
    return HTTPException(400, detail={"error": code})


@router.get("/public/sign/{token}")
def get_signer_bundle(token: str, request: Request, db: Session = Depends(get_db)):
    _rate(request, token)
    try:
        return sig_svc.build_public_payload(token, db)
    except (ValueError, EmailDeliveryError, LifecycleError) as e:
        raise _public_err(e)


@router.post("/public/sign/{token}/open")
def open_signer(token: str, request: Request, db: Session = Depends(get_db)):
    _rate(request, token)
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    try:
        return sig_svc.open_signer(token, db, ip=ip, user_agent=ua)
    except (ValueError, EmailDeliveryError, LifecycleError) as e:
        raise _public_err(e)


@router.post("/public/sign/{token}/submit")
def submit_signer(token: str, body: SubmitBody, request: Request, db: Session = Depends(get_db)):
    _rate(request, token)
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    try:
        return sig_svc.submit_signature(
            token,
            db,
            signature_type=body.signature_type,
            signature_value=body.signature_value,
            consent_accepted=body.consent_accepted,
            signer_name_confirmation=body.signer_name_confirmation,
            ip=ip,
            user_agent=ua,
        )
    except (ValueError, EmailDeliveryError, LifecycleError) as e:
        raise _public_err(e)


@router.post("/public/sign/{token}/decline")
def decline_signer(token: str, body: DeclineBody, request: Request, db: Session = Depends(get_db)):
    _rate(request, token)
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    try:
        return sig_svc.decline_signature(token, db, reason=body.reason, ip=ip, user_agent=ua)
    except (ValueError, EmailDeliveryError, LifecycleError) as e:
        raise _public_err(e)


@router.get("/public/sign/{token}/document")
def signer_document(token: str, request: Request, db: Session = Depends(get_db)):
    _rate(request, token)
    try:
        data = sig_svc.get_document_bytes(token, db)
    except (ValueError, EmailDeliveryError, LifecycleError) as e:
        raise _public_err(e)
    return Response(content=data, media_type="application/pdf")
