"""Feature 16 — Negotiation Monitor API."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import demo_role
from ..services.negotiation_monitor import service as mon_svc
from ..services.negotiation_monitor import outbound as outbound_svc
from ..services.negotiation_monitor.memory import get_counterparty_memory

router = APIRouter(prefix="/negotiation-monitor", tags=["negotiation-monitor"])


class ThreadCreate(BaseModel):
    contract_id: str
    counterparty_name: str | None = None
    counterparty_email: str | None = None
    subject: str | None = None
    monitoring_enabled: bool = True
    standard_template_version_id: str | None = None
    playbook_id: str | None = None
    external_thread_id: str | None = None
    assigned_lawyer: str | None = None


class ThreadPatch(BaseModel):
    status: str | None = None
    assigned_lawyer: str | None = None
    monitoring_enabled: bool | None = None
    subject: str | None = None
    counterparty_name: str | None = None


class ImportEmailBody(BaseModel):
    simulated_message_id: str | None = None
    manual: dict | None = None
    provider: str | None = None


class LinkContractBody(BaseModel):
    thread_id: str


class PackagePatch(BaseModel):
    lawyer_edited_json: dict | None = None
    draft_email_body_en: str | None = None
    draft_email_body_ar: str | None = None
    draft_email_subject_en: str | None = None
    draft_email_subject_ar: str | None = None
    status: str | None = None


class ApproveResponseBody(BaseModel):
    edited: dict | None = None


class SendResponseBody(BaseModel):
    override_reason: str | None = None


def _err(code: str, status: int = 400):
    raise HTTPException(status_code=status, detail={"code": code})


@router.post("/threads")
def create_thread(body: ThreadCreate, db: Session = Depends(get_db), actor: str = Depends(demo_role)):
    try:
        return mon_svc.service.create_thread(db, body.model_dump(), actor=actor)
    except ValueError as e:
        _err(str(e))


@router.get("/threads")
def list_threads(
    status: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return {"threads": mon_svc.service.list_threads(db, status=status)}


@router.get("/threads/{thread_id}")
def get_thread(thread_id: uuid.UUID, db: Session = Depends(get_db)):
    try:
        return mon_svc.service.get_thread_detail(thread_id, db)
    except ValueError as e:
        if str(e) == "not_found":
            _err("not_found", 404)
        _err(str(e))


@router.patch("/threads/{thread_id}")
def patch_thread(thread_id: uuid.UUID, body: ThreadPatch, db: Session = Depends(get_db)):
    try:
        return mon_svc.service.patch_thread(thread_id, db, body.model_dump(exclude_unset=True))
    except ValueError as e:
        _err(str(e), 404 if str(e) == "not_found" else 400)


@router.get("/inbox/simulated")
def simulated_inbox(db: Session = Depends(get_db)):
    return {"messages": mon_svc.service.list_simulated_inbox(db)}


@router.post("/threads/{thread_id}/emails/import")
def import_email(
    thread_id: uuid.UUID,
    body: ImportEmailBody,
    db: Session = Depends(get_db),
    actor: str = Depends(demo_role),
):
    try:
        return mon_svc.service.import_email_to_thread(thread_id, db, payload=body.model_dump(), actor=actor)
    except ValueError as e:
        _err(str(e))


@router.post("/threads/{thread_id}/analyze")
def analyze_thread(
    thread_id: uuid.UUID,
    email_id: uuid.UUID | None = Query(None),
    db: Session = Depends(get_db),
    actor: str = Depends(demo_role),
):
    try:
        return mon_svc.service.analyze_thread(thread_id, db, email_id=email_id, actor=actor)
    except ValueError as e:
        _err(str(e))


@router.post("/emails/{email_id}/link-contract")
def link_contract(email_id: uuid.UUID, body: LinkContractBody, db: Session = Depends(get_db)):
    try:
        return mon_svc.service.link_email_contract(email_id, db, thread_id=uuid.UUID(body.thread_id))
    except ValueError as e:
        _err(str(e), 404 if str(e) == "not_found" else 400)


@router.post("/emails/{email_id}/attachments/{attachment_id}/create-version")
def create_version(email_id: uuid.UUID, attachment_id: uuid.UUID, db: Session = Depends(get_db), actor: str = Depends(demo_role)):
    try:
        return mon_svc.service.create_version_from_attachment(email_id, attachment_id, db, actor=actor)
    except ValueError as e:
        _err(str(e))


@router.get("/threads/{thread_id}/rounds")
def list_rounds(thread_id: uuid.UUID, db: Session = Depends(get_db)):
    try:
        detail = mon_svc.service.get_thread_detail(thread_id, db)
        return {"rounds": detail.get("rounds") or []}
    except ValueError as e:
        _err(str(e), 404)


@router.get("/packages/{package_id}")
def get_package(package_id: uuid.UUID, db: Session = Depends(get_db)):
    from ..models import NegotiationReviewPackage

    pkg = db.get(NegotiationReviewPackage, package_id)
    if pkg is None:
        _err("not_found", 404)
    return mon_svc.service.serialize_package(pkg)


@router.patch("/packages/{package_id}")
def patch_package(package_id: uuid.UUID, body: PackagePatch, db: Session = Depends(get_db), actor: str = Depends(demo_role)):
    from ..models import NegotiationReviewPackage

    pkg = db.get(NegotiationReviewPackage, package_id)
    if pkg is None:
        _err("not_found", 404)
    data = body.model_dump(exclude_unset=True)
    if data.get("lawyer_edited_json"):
        pkg.lawyer_edited_json = data["lawyer_edited_json"]
    for k in ("draft_email_body_en", "draft_email_body_ar", "draft_email_subject_en", "draft_email_subject_ar", "status"):
        if k in data and data[k] is not None:
            setattr(pkg, k, data[k])
    if data.get("status") == "edited":
        pkg.status = "edited"
    db.commit()
    db.refresh(pkg)
    return mon_svc.service.serialize_package(pkg)


@router.post("/packages/{package_id}/approve-response")
def approve_package(package_id: uuid.UUID, body: ApproveResponseBody, db: Session = Depends(get_db), actor: str = Depends(demo_role)):
    from ..models import NegotiationReviewPackage

    pkg = db.get(NegotiationReviewPackage, package_id)
    if pkg is None:
        _err("not_found", 404)
    return mon_svc.service.serialize_package(
        outbound_svc.approve_response(db, pkg, actor=actor, edited=body.edited)
    )


@router.post("/packages/{package_id}/send-response")
def send_package(package_id: uuid.UUID, body: SendResponseBody, db: Session = Depends(get_db), actor: str = Depends(demo_role)):
    from ..models import NegotiationReviewPackage

    pkg = db.get(NegotiationReviewPackage, package_id)
    if pkg is None:
        _err("not_found", 404)
    try:
        outbound = outbound_svc.send_approved_response(
            db, pkg, actor=actor, override_reason=body.override_reason
        )
        return {"email": mon_svc.service.serialize_email(outbound)}
    except ValueError as e:
        _err(str(e))
