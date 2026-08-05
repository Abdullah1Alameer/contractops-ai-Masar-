"""Feature 9 — Digital signature workflow."""
from __future__ import annotations

import base64
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ..config import REVIEW_BASE_URL
from ..models import ApprovalWorkflow, Contract, ContractVersion, OutboundMessage, SignatureEvent, SignatureRequest, SignatureSigner
from .approvals import log_activity
from .lifecycle import (
    LifecycleEvent,
    LifecycleService,
)
from .outbound_messages import (
    TokenMaterial,
    create_token_material,
    create_pending_attempt,
    deliver_pending_attempt,
    enforce_resend_cooldown,
    hash_public_token,
    public_token_from_nonce,
    serialize_delivery,
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
SIGNATURE_INVITATION_MESSAGE_TYPE = "signature_invitation"
ACTIVATION_ROLES = frozenset({"legal", "executive"})


class SignatureError(ValueError):
    """Stable service error contract for protected and public signature APIs."""

    def __init__(self, status_code: int, code: str, **payload):
        self.status_code = status_code
        self.code = code
        self.payload = {"error": code, **payload}
        super().__init__(code)


def _raise(status_code: int, code: str, **payload) -> None:
    raise SignatureError(status_code, code, **payload)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def _commit(db: Session, *rows) -> None:
    try:
        db.commit()
        for row in rows:
            db.refresh(row)
    except Exception:
        db.rollback()
        raise


def _lock_contract(contract_id, db: Session) -> Contract:
    contract = db.query(Contract).filter(Contract.id == contract_id).with_for_update().one_or_none()
    if contract is None:
        _raise(404, "not_found")
    return contract


def _lock_request(request_id, db: Session) -> SignatureRequest:
    req = (
        db.query(SignatureRequest)
        .filter(SignatureRequest.id == request_id)
        .with_for_update()
        .one_or_none()
    )
    if req is None:
        _raise(404, "not_found")
    return req


def _locked_current_version(contract_id, db: Session) -> ContractVersion | None:
    return (
        db.query(ContractVersion)
        .filter_by(contract_id=contract_id, is_current=True)
        .with_for_update()
        .order_by(ContractVersion.version_number.desc())
        .first()
    )


def _is_stale(req: SignatureRequest, version: ContractVersion | None) -> bool:
    return version is None or req.version_id is None or req.version_id != version.id


def _active_approved_workflow(contract_id, version_id, db: Session) -> bool:
    return (
        db.query(ApprovalWorkflow)
        .filter_by(contract_id=contract_id, version_id=version_id, status="approved")
        .first()
        is not None
    )


def _transition(
    db: Session,
    contract: Contract,
    req: SignatureRequest,
    version: ContractVersion,
    event: LifecycleEvent,
    *,
    actor: str,
    metadata: dict | None = None,
):
    transition = LifecycleService.transition(
        contract,
        event,
        actor,
        metadata={
            "request_id": str(req.id),
            "version_id": str(version.id),
            "current_version": True,
            **(metadata or {}),
        },
    )
    if transition.changed:
        log_activity(
            db,
            contract.id,
            transition.activity_event.value,
            actor=actor,
            metadata=transition.activity_metadata,
        )
    return transition


def hash_token(raw: str) -> str:
    return hash_public_token(raw)


def new_signer_token() -> str:
    return secrets.token_urlsafe(32)


def generate_token_material() -> TokenMaterial:
    return create_token_material()


def public_token_for_signer(signer: SignatureSigner) -> str:
    if not signer.token_nonce:
        raise ValueError("signer_token_not_reproducible")
    return public_token_from_nonce(signer.token_nonce)


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


def _create_invitation_attempts(db, contract, req, signers, *, actor):
    pending = []
    for signer in signers:
        link = signer_link(public_token_for_signer(signer))
        email = build_invitation_email(contract, req, signer, link)
        row = create_pending_attempt(
            db,
            message_type=SIGNATURE_INVITATION_MESSAGE_TYPE,
            recipient=signer.email,
            subject=email["subject_en"],
            contract_id=contract.id,
            signature_request_id=req.id,
            signer_id=signer.id,
        )
        log_sig_event(db, req.id, "signer_invited", signer_id=signer.id, actor=actor,
                      metadata={"order": signer.signer_order})
        pending.append((row, signer))
    return pending


def _deliver_invitation(attempt_id, contract, req, signer, db):
    email = build_invitation_email(contract, req, signer, signer_link(public_token_for_signer(signer)))
    return deliver_pending_attempt(
        attempt_id, db, recipient=signer.email, subject=email["subject_en"],
        text_body=email["body_en"], html_body=email["html_en"],
    )


def _expire_locked(req, contract, version, db) -> bool:
    expires_at = req.expires_at
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if req.status not in TERMINAL_REQUEST_STATUSES and expires_at and expires_at <= _utcnow():
        req.status, req.updated_at = "expired", _utcnow()
        _transition(db, contract, req, version, LifecycleEvent.SIGNATURE_EXPIRED, actor="system")
        log_activity(db, contract.id, "signature_request_expired", actor="system",
                     metadata={"request_id": str(req.id)})
        log_sig_event(db, req.id, "request_expired", actor="system")
        _commit(db, req, contract)
        return True
    return False


def expire_if_needed(req: SignatureRequest, db: Session) -> SignatureRequest:
    if req.status in TERMINAL_REQUEST_STATUSES:
        return req
    try:
        locked = _lock_request(req.id, db)
        contract = _lock_contract(locked.contract_id, db)
        version = _locked_current_version(contract.id, db)
        if _is_stale(locked, version):
            _raise(409, "workflow_stale")
        _expire_locked(locked, contract, version, db)
        return locked
    except Exception:
        db.rollback()
        raise


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
    saved_keys: list[str] = []
    try:
        contract = _lock_contract(contract_id, db)
        version = _locked_current_version(contract.id, db)
        if version is None:
            _raise(409, "current_version_required")
        if contract.stage != "ready_to_sign":
            _raise(409, "invalid_stage_transition")
        if version.status != "approved":
            _raise(409, "version_not_approved")
        if not _active_approved_workflow(contract.id, version.id, db):
            _raise(409, "approval_not_complete")
        if get_active_request(contract_id, db):
            _raise(409, "active_request_exists")
    except Exception:
        db.rollback()
        raise
    if expires_at <= _utcnow():
        _raise(422, "expires_must_be_future")
    _validate_signers_body(signers, allow_duplicate_emails=allow_duplicate_emails)
    try:
        orig = original_bytes(contract)
        orig_hash = sha256_hex(orig)
        orig_key = storage.save(orig, f"sig_orig_{contract_id}.pdf")
        saved_keys.append(orig_key)
        req = SignatureRequest(
            id=uuid.uuid4(), contract_id=contract_id, version_id=version.id,
            provider="simulated", status="draft", created_by=actor, subject=subject.strip(),
            message=message, signing_order_enabled=signing_order_enabled, expires_at=expires_at,
            original_file_url=orig_key, original_hash=orig_hash,
        )
        db.add(req)
        db.flush()
        signer_rows, tokens_out = [], []
        for s in sorted(signers, key=lambda x: x["order"]):
            material = generate_token_material()
            row = SignatureSigner(
                id=uuid.uuid4(), signature_request_id=req.id, signer_order=int(s["order"]),
                name=s["name"].strip(), email=s["email"].strip(), role=s.get("role", "other"),
                token_hash=material.token_hash, token_nonce=material.nonce, status="waiting",
            )
            db.add(row)
            signer_rows.append(row)
            tokens_out.append({"signer_id": str(row.id), "order": row.signer_order, "name": row.name,
                               "email": row.email, "signer_link": signer_link(material.public_token),
                               "token": material.public_token})
        transition = _transition(db, contract, req, version, LifecycleEvent.SIGNATURE_REQUEST_CREATED, actor=actor)
        log_activity(db, contract_id, "signature_request_created", actor=actor,
                     metadata={"request_id": str(req.id), "version_id": str(version.id)})
        log_sig_event(db, req.id, "request_created", actor=actor, metadata={"provider": req.provider})
        _commit(db, req)
    except Exception:
        db.rollback()
        for key in saved_keys:
            storage.delete(key)
        raise

    emails = [build_invitation_email(contract, req, sr, t["signer_link"]) for sr, t in zip(signer_rows, tokens_out)]
    return {
        "request": serialize_request(req, db),
        "signers": [serialize_signer_internal(s) for s in signer_rows],
        "signer_links": tokens_out,
        "email_templates": emails,
    }


def send_request(request_id, db: Session, *, actor: str = "demo") -> dict:
    try:
        req = _lock_request(request_id, db)
        contract = _lock_contract(req.contract_id, db)
        version = _locked_current_version(contract.id, db)
        if _is_stale(req, version):
            _raise(409, "workflow_stale")
        _expire_locked(req, contract, version, db)
        if req.status in TERMINAL_REQUEST_STATUSES:
            _raise(409, "request_closed")
        if req.status not in ("draft", "created"):
            _raise(409, "invalid_transition")
        signers = _signers_for(req.id, db)
        invitees = signers[:1] if req.signing_order_enabled else signers
        now = _utcnow()
        req.status, req.sent_at, req.updated_at = "sent", now, now
        for signer in invitees:
            signer.status = "invited"
        _transition(db, contract, req, version, LifecycleEvent.SIGNATURE_SENT, actor=actor)
        log_activity(db, req.contract_id, "signature_request_sent", actor=actor, metadata={"request_id": str(req.id)})
        log_sig_event(db, req.id, "request_sent", actor=actor)
        pending = _create_invitation_attempts(db, contract, req, invitees, actor=actor)
        _commit(db, req)
    except Exception:
        db.rollback()
        raise
    deliveries = [_deliver_invitation(row.id, contract, req, signer, db) for row, signer in pending]
    return {**serialize_request_bundle(req, db), "deliveries": [serialize_delivery(row) for row in deliveries]}


def cancel_request(request_id, db: Session, *, actor: str = "demo", reason: str | None = None) -> dict:
    if not (reason or "").strip():
        _raise(422, "signature_reason_required")
    try:
        req = _lock_request(request_id, db)
        contract = _lock_contract(req.contract_id, db)
        version = _locked_current_version(contract.id, db)
        if _is_stale(req, version):
            _raise(409, "workflow_stale")
        if req.status in TERMINAL_REQUEST_STATUSES:
            _raise(409, "request_closed")
        req.status, req.updated_at = "cancelled", _utcnow()
        _transition(db, contract, req, version, LifecycleEvent.SIGNATURE_CANCELLED, actor=actor)
        log_activity(db, req.contract_id, "signature_request_cancelled", actor=actor,
                     metadata={"request_id": str(req.id), "reason_present": True})
        log_sig_event(db, req.id, "request_cancelled", actor=actor, metadata={"reason_present": True})
        _commit(db, req, contract)
    except Exception:
        db.rollback()
        raise
    return serialize_request_bundle(req, db)


def resend_signer(request_id, signer_id, db: Session, *, actor: str = "demo") -> dict:
    try:
        req = _lock_request(request_id, db)
        contract = _lock_contract(req.contract_id, db)
        version = _locked_current_version(contract.id, db)
        signer = (
            db.query(SignatureSigner).filter_by(id=signer_id).with_for_update().one_or_none()
        )
        if signer is None or signer.signature_request_id != req.id:
            _raise(404, "not_found")
        if _is_stale(req, version):
            _raise(409, "workflow_stale")
        if req.status in TERMINAL_REQUEST_STATUSES or signer.status not in ("invited", "opened"):
            _raise(409, "not_active_signer")
        enforce_resend_cooldown(
            db, contract_id=contract.id, message_type=SIGNATURE_INVITATION_MESSAGE_TYPE,
            signature_request_id=req.id, signer_id=signer.id,
        )
        raw = public_token_for_signer(signer)
        email = build_invitation_email(contract, req, signer, signer_link(raw))
        pending = _create_invitation_attempts(db, contract, req, [signer], actor=actor)
        log_sig_event(db, req.id, "signer_resent", signer_id=signer.id, actor=actor)
        _commit(db, req)
    except Exception:
        db.rollback()
        raise
    delivery = _deliver_invitation(pending[0][0].id, contract, req, signer, db)
    return {"signer_link": signer_link(raw), "token": raw, "email": email, "delivery": serialize_delivery(delivery)}


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
    saved_keys: list[str] = []
    try:
        unlocked_signer = get_signer_by_token(raw_token, db)
        if unlocked_signer is None:
            _raise(404, "not_found")
        req = _lock_request(unlocked_signer.signature_request_id, db)
        contract = _lock_contract(req.contract_id, db)
        version = _locked_current_version(contract.id, db)
        signer = db.query(SignatureSigner).filter_by(id=unlocked_signer.id).with_for_update().one()
        if _is_stale(req, version):
            _raise(409, "workflow_stale")
        if _expire_locked(req, contract, version, db):
            _raise(410, "expired")
        if req.status in TERMINAL_REQUEST_STATUSES:
            _raise(409, "request_closed")
        signers = _signers_for(req.id, db)
        if signer.status == "signed":
            _raise(409, "signer_closed")
        if not _signer_can_act(signer, req, signers):
            _raise(409, "not_active_signer")
        if signer.name.strip().lower() != signer_name_confirmation.strip().lower():
            _raise(422, "name_mismatch")
        data = _decode_signature_value(signature_type, signature_value)
        if signature_type in ("drawn", "uploaded") and len(data) > MAX_UPLOAD_BYTES:
            _raise(422, "file_too_large")
        ext = "png" if signature_type == "drawn" else "txt"
        key = storage.save(data, f"sig_{signer.id}.{ext}")
        saved_keys.append(key)
        now = _utcnow()
        signer.status, signer.signed_at, signer.signature_type = "signed", now, signature_type
        signer.signature_value_url, signer.consent_text = key, CONSENT_EN
        signer.ip_address, signer.user_agent = ip, (user_agent or "")[:500] or None
        log_activity(db, req.contract_id, "signer_signed", actor=signer.email,
                     metadata={"order": signer.signer_order, "request_id": str(req.id)})
        log_sig_event(db, req.id, "signer_signed", signer_id=signer.id, actor=signer.email,
                      metadata={"signature_type": signature_type, "provider": req.provider})
        signed_count = sum(1 for s in signers if s.status == "signed")
        pending = []
        if signed_count < len(signers):
            req.status, req.updated_at = "partially_signed", now
            _transition(db, contract, req, version, LifecycleEvent.SIGNATURE_PARTIALLY_SIGNED, actor=signer.email)
            invitees = [
                s for s in signers if s.status == "waiting"
                and (not req.signing_order_enabled or all(x.status == "signed" for x in signers if x.signer_order < s.signer_order))
            ]
            for invitee in invitees:
                invitee.status = "invited"
            pending = _create_invitation_attempts(db, contract, req, invitees, actor="system")
        else:
            _finalize_request(req, contract, version, signers, db, actor=signer.email, saved_keys=saved_keys)
        _commit(db, req, contract)
    except Exception:
        db.rollback()
        for key in saved_keys:
            storage.delete(key)
        raise
    for attempt, invitee in pending:
        _deliver_invitation(attempt.id, contract, req, invitee, db)
    return build_public_payload(raw_token, db)


def _finalize_request(req: SignatureRequest, contract: Contract, version: ContractVersion, signers: list[SignatureSigner], db: Session, *, actor: str, saved_keys: list[str]):
    signed_pdf = build_signed_pdf(contract, req, signers)
    req.signed_hash = sha256_hex(signed_pdf)
    signed_key = storage.save(signed_pdf, f"signed_{req.id}.pdf")
    saved_keys.append(signed_key)
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
    saved_keys.append(cert_key)
    req.certificate_file_url = cert_key

    now = _utcnow()
    req.status = "completed"
    req.completed_at = now
    req.updated_at = now

    log_activity(db, req.contract_id, "signature_request_completed", actor=actor)
    log_activity(db, req.contract_id, "signed_document_generated", actor=actor)
    log_activity(db, req.contract_id, "signature_certificate_generated", actor=actor)
    log_sig_event(db, req.id, "request_completed", actor=actor)
    log_sig_event(db, req.id, "signed_document_generated", actor=actor)
    log_sig_event(db, req.id, "certificate_generated", actor=actor)

    _transition(db, contract, req, version, LifecycleEvent.SIGNATURE_COMPLETED, actor=actor,
                metadata={"signature_complete": True})
    from .versions import mark_version_signed
    mark_version_signed(req.contract_id, req.id, db, commit=False)
    log_activity(db, req.contract_id, "version_signed", actor=actor)


def decline_signature(raw_token: str, db: Session, *, reason: str, ip: str | None, user_agent: str | None) -> dict:
    if not (reason or "").strip():
        _raise(422, "reason_required")
    try:
        unlocked_signer = get_signer_by_token(raw_token, db)
        if unlocked_signer is None:
            _raise(404, "not_found")
        req = _lock_request(unlocked_signer.signature_request_id, db)
        contract = _lock_contract(req.contract_id, db)
        version = _locked_current_version(contract.id, db)
        signer = db.query(SignatureSigner).filter_by(id=unlocked_signer.id).with_for_update().one()
        if _is_stale(req, version):
            _raise(409, "workflow_stale")
        if req.status in TERMINAL_REQUEST_STATUSES:
            _raise(409, "request_closed")
        signers = _signers_for(req.id, db)
        if not _signer_can_act(signer, req, signers):
            _raise(409, "not_active_signer")
        now = _utcnow()
        signer.status, signer.declined_at, signer.decline_reason = "declined", now, reason.strip()
        signer.ip_address, signer.user_agent = ip, (user_agent or "")[:500] or None
        req.status, req.declined_at, req.decline_reason = "declined", now, reason.strip()
        _transition(db, contract, req, version, LifecycleEvent.SIGNATURE_DECLINED, actor=signer.email,
                    metadata={"reason": reason.strip()})
        log_activity(db, req.contract_id, "signer_declined", actor=signer.email,
                     metadata={"request_id": str(req.id), "reason_present": True})
        log_sig_event(db, req.id, "signer_declined", signer_id=signer.id, actor=signer.email,
                      metadata={"reason_present": True})
        _commit(db, req, contract)
    except Exception:
        db.rollback()
        raise
    return build_public_payload(raw_token, db)


def activate_contract(request_id, db: Session, *, actor: str, reason: str | None, evidence: str | None) -> dict:
    if actor not in ACTIVATION_ROLES:
        _raise(403, "signature_activation_forbidden")
    if not (reason or "").strip() or not (evidence or "").strip():
        _raise(422, "activation_reason_evidence_required")
    try:
        req = _lock_request(request_id, db)
        contract = _lock_contract(req.contract_id, db)
        version = _locked_current_version(contract.id, db)
        if _is_stale(req, version):
            _raise(409, "workflow_stale")
        if req.status != "completed" or version.status != "signed":
            _raise(409, "activation_not_ready")
        _transition(db, contract, req, version, LifecycleEvent.CONTRACT_ACTIVATED, actor=actor,
                    metadata={"activation_ready": True, "reason": reason.strip(), "evidence": evidence.strip()})
        log_activity(db, contract.id, "contract_activated", actor=actor,
                     metadata={"request_id": str(req.id), "reason_present": True, "evidence_present": True})
        _commit(db, contract)
    except Exception:
        db.rollback()
        raise
    return serialize_request_bundle(req, db)


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
