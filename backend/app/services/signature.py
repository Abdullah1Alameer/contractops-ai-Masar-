"""Feature 9 — Digital signature workflow."""
from __future__ import annotations

import base64
import hashlib
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ..config import REVIEW_BASE_URL
from ..integrations.esign import get_provider
from ..models import Contract, SignatureEvent, SignatureRequest, SignatureSigner
from .approvals import log_activity
from .lifecycle import (
    DECLINE_REVERT_STAGE,
    can_create_signature,
    set_stage,
    transition_stage,
)
from .signature_pdf import build_certificate_pdf, build_signed_pdf, original_bytes, sha256_hex
from .storage import storage

ACTIVE_REQUEST_STATUSES = frozenset({"draft", "created", "sent", "viewed", "partially_signed"})
TERMINAL_REQUEST_STATUSES = frozenset({"completed", "declined", "expired", "cancelled", "error"})
ALLOWED_SIGNER_ROLES = frozenset(
    {
        "company_signatory",
        "client_signatory",
        "witness",
        "reviewer",
        "other",
    }
)
CONSENT_EN = "I agree to sign this document electronically."
CONSENT_AR = "أوافق على توقيع هذا المستند إلكترونيًا"
MAX_UPLOAD_BYTES = 2 * 1024 * 1024


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def new_signer_token() -> str:
    return secrets.token_urlsafe(32)


def signer_link(token: str) -> str:
    base = REVIEW_BASE_URL.rstrip("/")
    return f"{base}/sign/{token}"


def log_sig_event(
    db: Session,
    request_id,
    action: str,
    *,
    signer_id=None,
    actor: str | None = None,
    metadata: dict | None = None,
) -> SignatureEvent:
    ev = SignatureEvent(
        id=uuid.uuid4(),
        signature_request_id=request_id,
        signer_id=signer_id,
        actor=actor,
        action=action,
        event_metadata=metadata,
    )
    db.add(ev)
    return ev


def get_active_request(contract_id, db: Session) -> SignatureRequest | None:
    return (
        db.query(SignatureRequest)
        .filter(SignatureRequest.contract_id == contract_id)
        .filter(SignatureRequest.status.in_(ACTIVE_REQUEST_STATUSES))
        .order_by(SignatureRequest.created_at.desc())
        .first()
    )


def get_request_by_id(request_id, db: Session) -> SignatureRequest | None:
    return db.get(SignatureRequest, request_id)


def _signers_for(request_id, db: Session) -> list[SignatureSigner]:
    return (
        db.query(SignatureSigner)
        .filter_by(signature_request_id=request_id)
        .order_by(SignatureSigner.signer_order.asc())
        .all()
    )


def get_signer_by_token(raw_token: str, db: Session) -> SignatureSigner | None:
    th = hash_token(raw_token)
    return db.query(SignatureSigner).filter_by(token_hash=th).first()


def expire_if_needed(req: SignatureRequest, db: Session) -> SignatureRequest:
    if req.status in TERMINAL_REQUEST_STATUSES:
        return req
    if req.expires_at and req.expires_at <= _utcnow():
        req.status = "expired"
        req.updated_at = _utcnow()
        db.commit()
        db.refresh(req)
    return req


def _validate_signers_body(signers: list[dict], *, allow_duplicate_emails: bool = False) -> None:
    if not signers:
        raise ValueError("signers_required")
    orders = [s.get("order") for s in signers]
    if len(set(orders)) != len(orders):
        raise ValueError("duplicate_signer_order")
    emails = [s.get("email", "").strip().lower() for s in signers]
    if not allow_duplicate_emails and len(set(emails)) != len(emails):
        raise ValueError("duplicate_signer_email")
    for s in signers:
        if not s.get("name", "").strip():
            raise ValueError("signer_name_required")
        email = s.get("email", "").strip()
        if not email or "@" not in email:
            raise ValueError("invalid_email")
        role = s.get("role", "other")
        if role not in ALLOWED_SIGNER_ROLES:
            raise ValueError("invalid_signer_role")


def create_request(
    contract_id,
    db: Session,
    *,
    subject: str,
    message: str | None,
    expires_at: datetime,
    signing_order_enabled: bool,
    signers: list[dict],
    actor: str = "demo",
    allow_duplicate_emails: bool = False,
) -> dict:
    contract = db.get(Contract, contract_id)
    if contract is None:
        raise ValueError("not_found")
    if not can_create_signature(contract):
        raise ValueError("contract_not_approved")
    if get_active_request(contract_id, db):
        raise ValueError("active_request_exists")
    if expires_at <= _utcnow():
        raise ValueError("expires_must_be_future")
    _validate_signers_body(signers, allow_duplicate_emails=allow_duplicate_emails)

    orig = original_bytes(contract)
    orig_hash = sha256_hex(orig)
    orig_key = storage.save(orig, f"sig_orig_{contract_id}.pdf")

    provider = get_provider()
    from .versions import current_version

    cur = current_version(contract_id, db)
    req = SignatureRequest(
        id=uuid.uuid4(),
        contract_id=contract_id,
        version_id=cur.id if cur else None,
        provider=provider.name,
        status="draft",
        created_by=actor,
        subject=subject.strip(),
        message=message,
        signing_order_enabled=signing_order_enabled,
        expires_at=expires_at,
        original_file_url=orig_key,
        original_hash=orig_hash,
    )
    db.add(req)
    db.flush()

    provider.create_request(contract_id=str(contract_id), metadata={"request_id": str(req.id)})

    signer_rows: list[SignatureSigner] = []
    tokens_out: list[dict] = []
    for s in sorted(signers, key=lambda x: x["order"]):
        raw = new_signer_token()
        row = SignatureSigner(
            id=uuid.uuid4(),
            signature_request_id=req.id,
            signer_order=int(s["order"]),
            name=s["name"].strip(),
            email=s["email"].strip(),
            role=s.get("role", "other"),
            token_hash=hash_token(raw),
            status="waiting",
        )
        db.add(row)
        signer_rows.append(row)
        tokens_out.append(
            {
                "signer_id": str(row.id),
                "order": row.signer_order,
                "name": row.name,
                "email": row.email,
                "signer_link": signer_link(raw),
                "token": raw,
            }
        )

    transition_stage(contract, "awaiting_signature", db)
    log_activity(db, contract_id, "signature_request_created", actor=actor, metadata={"request_id": str(req.id)})
    if cur:
        log_activity(db, contract_id, "version_sent_for_signature", actor=actor, metadata={"version_number": cur.version_number})
    log_sig_event(db, req.id, "request_created", actor=actor, metadata={"provider": provider.name})
    db.commit()
    db.refresh(req)

    emails = [build_invitation_email(contract, req, sr, t["signer_link"]) for sr, t in zip(signer_rows, tokens_out)]
    return {
        "request": serialize_request(req, db),
        "signers": [serialize_signer_internal(s) for s in signer_rows],
        "signer_links": tokens_out,
        "email_templates": emails,
    }


def send_request(request_id, db: Session, *, actor: str = "demo") -> dict:
    req = get_request_by_id(request_id, db)
    if req is None:
        raise ValueError("not_found")
    expire_if_needed(req, db)
    if req.status in TERMINAL_REQUEST_STATUSES:
        raise ValueError("request_closed")
    if req.status not in ("draft", "created"):
        raise ValueError("invalid_transition")

    signers = _signers_for(req.id, db)
    now = _utcnow()
    req.status = "sent"
    req.sent_at = now
    req.updated_at = now

    if req.signing_order_enabled:
        signers[0].status = "invited"
        for s in signers[1:]:
            s.status = "waiting"
    else:
        for s in signers:
            s.status = "invited"

    provider = get_provider()
    provider.send_request(external_id=req.external_id, metadata={"request_id": str(req.id)})

    log_activity(db, req.contract_id, "signature_request_sent", actor=actor, metadata={"request_id": str(req.id)})
    log_sig_event(db, req.id, "request_sent", actor=actor)
    for s in signers:
        if s.status == "invited":
            log_sig_event(db, req.id, "signer_invited", signer_id=s.id, actor=actor, metadata={"order": s.signer_order})
    db.commit()
    db.refresh(req)
    return serialize_request_bundle(req, db)


def cancel_request(request_id, db: Session, *, actor: str = "demo") -> dict:
    req = get_request_by_id(request_id, db)
    if req is None:
        raise ValueError("not_found")
    if req.status in TERMINAL_REQUEST_STATUSES:
        raise ValueError("request_closed")
    contract = db.get(Contract, req.contract_id)
    req.status = "cancelled"
    req.updated_at = _utcnow()
    if contract:
        set_stage(contract, "approved", db)
    log_activity(db, req.contract_id, "signature_request_cancelled", actor=actor)
    log_sig_event(db, req.id, "request_cancelled", actor=actor)
    db.commit()
    db.refresh(req)
    return serialize_request_bundle(req, db)


def resend_signer(request_id, signer_id, db: Session, *, actor: str = "demo") -> dict:
    req = get_request_by_id(request_id, db)
    if req is None:
        raise ValueError("not_found")
    signer = db.get(SignatureSigner, signer_id)
    if signer is None or signer.signature_request_id != req.id:
        raise ValueError("not_found")
    raw = new_signer_token()
    signer.token_hash = hash_token(raw)
    link = signer_link(raw)
    contract = db.get(Contract, req.contract_id)
    email = build_invitation_email(contract, req, signer, link) if contract else {}
    log_sig_event(db, req.id, "signer_resent", signer_id=signer.id, actor=actor)
    db.commit()
    return {"signer_link": link, "token": raw, "email": email}


def _signer_can_act(signer: SignatureSigner, req: SignatureRequest, signers: list[SignatureSigner]) -> bool:
    if signer.status in ("signed", "declined", "expired"):
        return False
    if req.signing_order_enabled:
        for s in signers:
            if s.signer_order < signer.signer_order and s.status != "signed":
                return False
    return signer.status in ("invited", "opened", "waiting") and (
        not req.signing_order_enabled or all(
            s.status == "signed" for s in signers if s.signer_order < signer.signer_order
        )
    )


def _waiting_for_prior(signer: SignatureSigner, signers: list[SignatureSigner], order_enabled: bool) -> bool:
    if not order_enabled:
        return False
    for s in signers:
        if s.signer_order < signer.signer_order and s.status != "signed":
            return True
    return False


def build_public_payload(raw_token: str, db: Session) -> dict:
    signer = get_signer_by_token(raw_token, db)
    if signer is None:
        raise ValueError("not_found")
    req = get_request_by_id(signer.signature_request_id, db)
    if req is None:
        raise ValueError("not_found")
    expire_if_needed(req, db)
    if req.status == "expired" or (req.expires_at and req.expires_at <= _utcnow()):
        raise ValueError("expired")
    contract = db.get(Contract, req.contract_id)
    if contract is None:
        raise ValueError("not_found")

    signers = _signers_for(req.id, db)
    completed = sum(1 for s in signers if s.status == "signed")
    waiting = _waiting_for_prior(signer, signers, req.signing_order_enabled)
    read_only = signer.status == "signed" or req.status in TERMINAL_REQUEST_STATUSES

    return {
        "contract_title": contract.title,
        "sender_name": contract.party_a or "ContractOps AI",
        "subject": req.subject,
        "message": req.message,
        "signer": {
            "name": signer.name,
            "role": signer.role,
            "order": signer.signer_order,
            "status": signer.status,
            "opened_at": _iso(signer.opened_at),
            "signed_at": _iso(signer.signed_at),
        },
        "progress": {
            "completed": completed,
            "total": len(signers),
            "order_enabled": req.signing_order_enabled,
        },
        "expires_at": _iso(req.expires_at),
        "consent_text": {"en": CONSENT_EN, "ar": CONSENT_AR},
        "document_url": f"/api/public/sign/{raw_token}/document",
        "provider_label": "demo" if req.provider == "simulated" else req.provider,
        "request_status": req.status,
        "waiting_for_prior": waiting,
        "read_only": read_only or waiting,
        "declined": req.status == "declined" or signer.status == "declined",
    }


def open_signer(raw_token: str, db: Session, *, ip: str | None, user_agent: str | None) -> dict:
    signer = get_signer_by_token(raw_token, db)
    if signer is None:
        raise ValueError("not_found")
    req = get_request_by_id(signer.signature_request_id, db)
    if req is None:
        raise ValueError("not_found")
    expire_if_needed(req, db)
    if req.status == "expired":
        raise ValueError("expired")
    signers = _signers_for(req.id, db)
    if _waiting_for_prior(signer, signers, req.signing_order_enabled):
        raise ValueError("not_active_signer")
    if signer.status == "signed":
        return build_public_payload(raw_token, db)
    if not signer.opened_at:
        signer.opened_at = _utcnow()
        if signer.status == "invited":
            signer.status = "opened"
        if req.status == "sent":
            req.status = "viewed"
        log_activity(db, req.contract_id, "signature_link_opened", actor=signer.email)
        log_sig_event(db, req.id, "signer_opened", signer_id=signer.id, actor=signer.email, metadata={"ip": ip})
    db.commit()
    return build_public_payload(raw_token, db)


def _decode_signature_value(signature_type: str, signature_value: str) -> bytes:
    if signature_type == "typed":
        return signature_value.strip().encode("utf-8")
    if signature_type == "drawn":
        m = re.match(r"^data:image/(png|jpeg);base64,(.+)$", signature_value, re.I | re.S)
        if not m:
            raise ValueError("invalid_signature_data")
        return base64.b64decode(m.group(2))
    if signature_type == "uploaded":
        return _decode_signature_value("drawn", signature_value)
    raise ValueError("invalid_signature_type")


def submit_signature(
    raw_token: str,
    db: Session,
    *,
    signature_type: str,
    signature_value: str,
    consent_accepted: bool,
    signer_name_confirmation: str,
    ip: str | None,
    user_agent: str | None,
) -> dict:
    if signature_type not in ("drawn", "typed", "uploaded"):
        raise ValueError("invalid_signature_type")
    if not consent_accepted:
        raise ValueError("consent_required")
    signer = get_signer_by_token(raw_token, db)
    if signer is None:
        raise ValueError("not_found")
    req = get_request_by_id(signer.signature_request_id, db)
    if req is None:
        raise ValueError("not_found")
    expire_if_needed(req, db)
    if req.status == "expired":
        raise ValueError("expired")
    if req.status in TERMINAL_REQUEST_STATUSES:
        raise ValueError("request_closed")
    signers = _signers_for(req.id, db)
    if signer.status == "signed":
        return build_public_payload(raw_token, db)
    if _waiting_for_prior(signer, signers, req.signing_order_enabled):
        raise ValueError("not_active_signer")
    if not _signer_can_act(signer, req, signers):
        raise ValueError("not_active_signer")
    if signer.name.strip().lower() != signer_name_confirmation.strip().lower():
        raise ValueError("name_mismatch")

    data = _decode_signature_value(signature_type, signature_value)
    if signature_type in ("drawn", "uploaded") and len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("file_too_large")
    ext = "png" if signature_type == "drawn" else "txt"
    if signature_type == "uploaded" and data[:2] == b"\xff\xd8":
        ext = "jpg"
    key = storage.save(data, f"sig_{signer.id}.{ext}")

    now = _utcnow()
    signer.status = "signed"
    signer.signed_at = now
    signer.signature_type = signature_type
    signer.signature_value_url = key
    signer.consent_text = CONSENT_EN
    signer.ip_address = ip
    signer.user_agent = (user_agent or "")[:500] or None

    contract = db.get(Contract, req.contract_id)
    log_activity(db, req.contract_id, "signer_signed", actor=signer.email, metadata={"order": signer.signer_order})
    log_sig_event(
        db,
        req.id,
        "signer_signed",
        signer_id=signer.id,
        actor=signer.email,
        metadata={"signature_type": signature_type, "provider": req.provider},
    )

    signed_count = sum(1 for s in signers if s.status == "signed")
    if signed_count < len(signers):
        req.status = "partially_signed"
        if contract:
            transition_stage(contract, "partially_signed", db)
        for s in signers:
            if s.status == "waiting" and req.signing_order_enabled:
                prior_done = all(x.status == "signed" for x in signers if x.signer_order < s.signer_order)
                if prior_done:
                    s.status = "invited"
                    log_sig_event(db, req.id, "signer_invited", signer_id=s.id, actor="system")
        db.commit()
        return build_public_payload(raw_token, db)

    _finalize_request(req, contract, signers, db, actor=signer.email)
    db.commit()
    return build_public_payload(raw_token, db)


def _finalize_request(req: SignatureRequest, contract: Contract | None, signers: list[SignatureSigner], db: Session, *, actor: str):
    signed_pdf = build_signed_pdf(contract, req, signers)
    req.signed_hash = sha256_hex(signed_pdf)
    signed_key = storage.save(signed_pdf, f"signed_{req.id}.pdf")
    req.signed_file_url = signed_key

    events = db.query(SignatureEvent).filter_by(signature_request_id=req.id).all()
    cert = build_certificate_pdf(
        contract,
        req,
        signers,
        events,
        original_hash=req.original_hash or "",
        signed_hash=req.signed_hash or "",
    )
    cert_key = storage.save(cert, f"cert_{req.id}.pdf")
    req.certificate_file_url = cert_key

    now = _utcnow()
    req.status = "completed"
    req.completed_at = now
    req.updated_at = now

    provider = get_provider()
    provider.sign(metadata={"request_id": str(req.id), "signed_bytes": signed_pdf, "certificate_bytes": cert})

    log_activity(db, req.contract_id, "signature_request_completed", actor=actor)
    log_activity(db, req.contract_id, "signed_document_generated", actor=actor)
    log_activity(db, req.contract_id, "signature_certificate_generated", actor=actor)
    log_sig_event(db, req.id, "request_completed", actor=actor)
    log_sig_event(db, req.id, "signed_document_generated", actor=actor)
    log_sig_event(db, req.id, "certificate_generated", actor=actor)

    if contract:
        transition_stage(contract, "signed", db)
        transition_stage(contract, "active", db)
        log_activity(db, req.contract_id, "contract_activated", actor=actor)
        from .versions import mark_version_signed

        mark_version_signed(req.contract_id, req.id, db)
        log_activity(db, req.contract_id, "version_signed", actor=actor)


def decline_signature(raw_token: str, db: Session, *, reason: str, ip: str | None, user_agent: str | None) -> dict:
    if not (reason or "").strip():
        raise ValueError("reason_required")
    signer = get_signer_by_token(raw_token, db)
    if signer is None:
        raise ValueError("not_found")
    req = get_request_by_id(signer.signature_request_id, db)
    if req is None:
        raise ValueError("not_found")
    if req.status in TERMINAL_REQUEST_STATUSES:
        raise ValueError("request_closed")
    signers = _signers_for(req.id, db)
    if _waiting_for_prior(signer, signers, req.signing_order_enabled):
        raise ValueError("not_active_signer")

    now = _utcnow()
    signer.status = "declined"
    signer.declined_at = now
    signer.decline_reason = reason.strip()
    signer.ip_address = ip
    signer.user_agent = (user_agent or "")[:500] or None
    req.status = "declined"
    req.declined_at = now
    req.decline_reason = reason.strip()

    contract = db.get(Contract, req.contract_id)
    if contract:
        set_stage(contract, DECLINE_REVERT_STAGE, db)
    log_activity(db, req.contract_id, "signer_declined", actor=signer.email, comment=reason.strip())
    log_sig_event(db, req.id, "signer_declined", signer_id=signer.id, actor=signer.email, metadata={"reason": reason.strip()})
    db.commit()
    return build_public_payload(raw_token, db)


def get_document_bytes(raw_token: str, db: Session) -> bytes:
    signer = get_signer_by_token(raw_token, db)
    if signer is None:
        raise ValueError("not_found")
    req = get_request_by_id(signer.signature_request_id, db)
    if req is None:
        raise ValueError("not_found")
    expire_if_needed(req, db)
    if req.status == "expired":
        raise ValueError("expired")
    if req.original_file_url:
        return storage.get(req.original_file_url)
    contract = db.get(Contract, req.contract_id)
    if contract:
        return original_bytes(contract)
    raise ValueError("not_found")


def build_invitation_email(contract: Contract, req: SignatureRequest, signer: SignatureSigner, link: str) -> dict:
    title = contract.title or "Contract"
    subject_ar = f"طلب توقيع: {title}"
    subject_en = f"Signature Request: {title}"
    body_ar = (
        f"مرحبًا {signer.name},\n\n"
        f"تمت دعوتك لتوقيع: {title}\n"
        f"{req.message or ''}\n\n"
        f"رابط التوقيع: {link}\n"
        f"ينتهي في: {req.expires_at}\n"
    )
    body_en = (
        f"Hello {signer.name},\n\n"
        f"You are invited to sign: {title}\n"
        f"{req.message or ''}\n\n"
        f"Sign here: {link}\n"
        f"Expires: {req.expires_at}\n"
    )
    return {
        "subject_ar": subject_ar,
        "subject_en": subject_en,
        "body_ar": body_ar,
        "body_en": body_en,
        "html_ar": f"<p>{body_ar.replace(chr(10), '<br/>')}</p>",
        "html_en": f"<p>{body_en.replace(chr(10), '<br/>')}</p>",
        "signer_link": link,
    }


def serialize_signer_internal(s: SignatureSigner) -> dict:
    return {
        "id": str(s.id),
        "signer_order": s.signer_order,
        "name": s.name,
        "email": s.email,
        "role": s.role,
        "status": s.status,
        "opened_at": _iso(s.opened_at),
        "signed_at": _iso(s.signed_at),
        "declined_at": _iso(s.declined_at),
        "decline_reason": s.decline_reason,
        "signature_type": s.signature_type,
    }


def serialize_request(req: SignatureRequest, db: Session) -> dict:
    from .versions import is_stale_version

    signers = _signers_for(req.id, db)
    completed = sum(1 for s in signers if s.status == "signed")
    return {
        "id": str(req.id),
        "contract_id": str(req.contract_id),
        "provider": req.provider,
        "status": req.status,
        "subject": req.subject,
        "message": req.message,
        "signing_order_enabled": req.signing_order_enabled,
        "expires_at": _iso(req.expires_at),
        "sent_at": _iso(req.sent_at),
        "completed_at": _iso(req.completed_at),
        "declined_at": _iso(req.declined_at),
        "decline_reason": req.decline_reason,
        "signed_file_url": req.signed_file_url,
        "certificate_file_url": req.certificate_file_url,
        "original_hash": req.original_hash,
        "signed_hash": req.signed_hash,
        "signers": [serialize_signer_internal(s) for s in signers],
        "progress": {"completed": completed, "total": len(signers)},
        "is_stale": is_stale_version(req.version_id, req.contract_id, db),
        "version_id": str(req.version_id) if req.version_id else None,
    }


def serialize_request_bundle(req: SignatureRequest, db: Session) -> dict:
    events = (
        db.query(SignatureEvent)
        .filter_by(signature_request_id=req.id)
        .order_by(SignatureEvent.created_at.desc())
        .all()
    )
    return {
        "request": serialize_request(req, db),
        "events": [
            {
                "id": str(e.id),
                "action": e.action,
                "actor": e.actor,
                "signer_id": str(e.signer_id) if e.signer_id else None,
                "metadata": e.event_metadata,
                "created_at": _iso(e.created_at),
            }
            for e in events
        ],
    }


def get_contract_signature_bundle(contract_id, db: Session) -> dict:
    req = (
        db.query(SignatureRequest)
        .filter_by(contract_id=contract_id)
        .order_by(SignatureRequest.created_at.desc())
        .first()
    )
    contract = db.get(Contract, contract_id)
    can_create = bool(can_create_signature(contract) and get_active_request(contract_id, db) is None)
    if req is None:
        return {"request": None, "events": [], "can_create": can_create}
    return {**serialize_request_bundle(req, db), "can_create": can_create}


def signature_summary(db: Session) -> dict:
    reqs = db.query(SignatureRequest).all()
    now = _utcnow()
    expiring = 0
    awaiting = partially = completed = declined = 0
    for r in reqs:
        if r.status in ("sent", "viewed", "created", "draft"):
            awaiting += 1
        elif r.status == "partially_signed":
            partially += 1
        elif r.status == "completed":
            completed += 1
        elif r.status == "declined":
            declined += 1
        if r.expires_at and r.status in ACTIVE_REQUEST_STATUSES and r.expires_at <= now + timedelta(days=7):
            expiring += 1
    contracts_awaiting = db.query(Contract).filter(Contract.stage == "awaiting_signature").count()
    contracts_partial = db.query(Contract).filter(Contract.stage == "partially_signed").count()
    return {
        "awaiting_signature": max(awaiting, contracts_awaiting),
        "partially_signed": max(partially, contracts_partial),
        "completed_signatures": completed,
        "declined_requests": declined,
        "expiring_soon": expiring,
    }
