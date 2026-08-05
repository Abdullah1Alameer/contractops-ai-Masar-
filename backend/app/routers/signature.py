"""Protected signature APIs."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import demo_role
from ..services import signature as sig_svc
from ..services.email_delivery import EmailDeliveryError
from ..services.lifecycle import LifecycleError
from ..services.storage import storage

router = APIRouter(tags=["signature"])


class SignerInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    role: str = "other"
    order: int = Field(ge=1, le=20)


class CreateSignatureBody(BaseModel):
    subject: str = Field(min_length=1, max_length=500)
    message: str | None = None
    expires_at: datetime
    signing_order_enabled: bool = True
    signers: list[SignerInput] = Field(min_length=1)

class CancelSignatureBody(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class ActivateSignatureBody(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)
    evidence: str = Field(min_length=1, max_length=4000)


def _map_err(e: Exception) -> HTTPException:
    if isinstance(e, sig_svc.SignatureError):
        return HTTPException(e.status_code, detail=e.payload)
    if isinstance(e, LifecycleError):
        return HTTPException(e.status_code, detail=e.payload)
    if isinstance(e, EmailDeliveryError):
        return HTTPException(e.status_code, detail={"error": e.code})
    code = str(e)
    if code in ("contract_not_approved", "active_request_exists", "invalid_transition", "request_closed"):
        return HTTPException(409, detail={"error": code})
    if code == "not_found":
        return HTTPException(404, detail={"error": code})
    return HTTPException(400, detail={"error": code})


@router.post("/contracts/{contract_id}/signature-request")
def create_signature_request(
    contract_id: uuid.UUID,
    body: CreateSignatureBody,
    db: Session = Depends(get_db),
    role: str = Depends(demo_role),
):
    try:
        return sig_svc.create_request(
            contract_id,
            db,
            subject=body.subject,
            message=body.message,
            expires_at=body.expires_at,
            signing_order_enabled=body.signing_order_enabled,
            signers=[s.model_dump() for s in body.signers],
            actor=role,
        )
    except (ValueError, EmailDeliveryError, LifecycleError) as e:
        raise _map_err(e)


@router.get("/contracts/{contract_id}/signature-request")
def get_signature_request(contract_id: uuid.UUID, db: Session = Depends(get_db)):
    return sig_svc.get_contract_signature_bundle(contract_id, db)


@router.post("/signature-requests/{request_id}/send")
def send_signature_request(
    request_id: uuid.UUID,
    db: Session = Depends(get_db),
    role: str = Depends(demo_role),
):
    try:
        return sig_svc.send_request(request_id, db, actor=role)
    except (ValueError, EmailDeliveryError, LifecycleError) as e:
        raise _map_err(e)


@router.post("/signature-requests/{request_id}/cancel")
def cancel_signature_request(
    request_id: uuid.UUID,
    body: CancelSignatureBody,
    db: Session = Depends(get_db),
    role: str = Depends(demo_role),
):
    try:
        return sig_svc.cancel_request(request_id, db, actor=role, reason=body.reason)
    except (ValueError, EmailDeliveryError, LifecycleError) as e:
        raise _map_err(e)

@router.post("/signature-requests/{request_id}/activate")
def activate_signature_request(
    request_id: uuid.UUID,
    body: ActivateSignatureBody,
    db: Session = Depends(get_db),
    role: str = Depends(demo_role),
):
    try:
        return sig_svc.activate_contract(
            request_id, db, actor=role, reason=body.reason, evidence=body.evidence
        )
    except (ValueError, EmailDeliveryError, LifecycleError) as e:
        raise _map_err(e)


@router.post("/signature-requests/{request_id}/resend/{signer_id}")
def resend_signature(
    request_id: uuid.UUID,
    signer_id: uuid.UUID,
    db: Session = Depends(get_db),
    role: str = Depends(demo_role),
):
    try:
        return sig_svc.resend_signer(request_id, signer_id, db, actor=role)
    except (ValueError, EmailDeliveryError, LifecycleError) as e:
        raise _map_err(e)


@router.get("/signature-requests/{request_id}/certificate")
def download_certificate(request_id: uuid.UUID, db: Session = Depends(get_db)):
    req = sig_svc.get_request_by_id(request_id, db)
    if req is None or not req.certificate_file_url:
        raise HTTPException(404, detail={"error": "not_found"})
    data = storage.get(req.certificate_file_url)
    return Response(content=data, media_type="application/pdf")


@router.get("/signature-requests/{request_id}/signed-document")
def download_signed_document(request_id: uuid.UUID, db: Session = Depends(get_db)):
    req = sig_svc.get_request_by_id(request_id, db)
    if req is None or not req.signed_file_url:
        raise HTTPException(404, detail={"error": "not_found"})
    data = storage.get(req.signed_file_url)
    return Response(content=data, media_type="application/pdf")


@router.get("/signature/summary")
def signature_summary(db: Session = Depends(get_db)):
    return sig_svc.signature_summary(db)
