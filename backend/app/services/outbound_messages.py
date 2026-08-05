"""Safe outbound-attempt persistence and reproducible portal tokens."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ..config import get_email_delivery_settings
from ..models import (
    OutboundMessage,
    ReviewRequest,
    SignatureRequest,
    SignatureSigner,
)
from .email_delivery import (
    EmailDeliveryError,
    EmailDeliveryResult,
    send_email,
    validate_recipient,
)


DEFAULT_RESEND_COOLDOWN_SECONDS = 60
_TERMINAL_STATUSES = frozenset({"sent", "failed", "cancelled"})


@dataclass(frozen=True)
class TokenMaterial:
    nonce: str = field(repr=False)
    public_token: str = field(repr=False)
    token_hash: str = field(repr=False)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def hash_public_token(public_token: str) -> str:
    return hashlib.sha256(public_token.encode("utf-8")).hexdigest()


def public_token_from_nonce(nonce: str) -> str:
    secret = get_email_delivery_settings().portal_token_secret
    if not secret:
        raise EmailDeliveryError(500, "portal_token_secret_missing")
    digest = hmac.new(
        secret.encode("utf-8"),
        nonce.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def create_token_material() -> TokenMaterial:
    nonce = secrets.token_urlsafe(32)
    public_token = public_token_from_nonce(nonce)
    return TokenMaterial(
        nonce=nonce,
        public_token=public_token,
        token_hash=hash_public_token(public_token),
    )


def _validate_subject(subject: str) -> str:
    if (
        not isinstance(subject, str)
        or not subject.strip()
        or "\r" in subject
        or "\n" in subject
    ):
        raise EmailDeliveryError(422, "invalid_email_content")
    return subject.strip()


def _validate_workflow_scope(
    db: Session,
    *,
    contract_id,
    review_request_id=None,
    signature_request_id=None,
    signer_id=None,
) -> None:
    if review_request_id is not None:
        review = db.get(ReviewRequest, review_request_id)
        if review is None or review.contract_id != contract_id:
            raise EmailDeliveryError(422, "invalid_outbound_scope")
    if signature_request_id is not None:
        request = db.get(SignatureRequest, signature_request_id)
        if request is None or request.contract_id != contract_id:
            raise EmailDeliveryError(422, "invalid_outbound_scope")
    if signer_id is not None:
        signer = db.get(SignatureSigner, signer_id)
        if (
            signer is None
            or signature_request_id is None
            or signer.signature_request_id != signature_request_id
        ):
            raise EmailDeliveryError(422, "invalid_outbound_scope")
    if review_request_id is not None and (
        signature_request_id is not None or signer_id is not None
    ):
        raise EmailDeliveryError(422, "invalid_outbound_scope")


def create_pending_attempt(
    db: Session,
    *,
    message_type: str,
    recipient: str,
    subject: str,
    contract_id,
    review_request_id=None,
    signature_request_id=None,
    signer_id=None,
) -> OutboundMessage:
    """Flush one pending row; the caller owns the workflow transaction."""
    if not isinstance(message_type, str) or not message_type.strip():
        raise EmailDeliveryError(422, "invalid_outbound_type")
    recipient = validate_recipient(recipient)
    subject = _validate_subject(subject)
    _validate_workflow_scope(
        db,
        contract_id=contract_id,
        review_request_id=review_request_id,
        signature_request_id=signature_request_id,
        signer_id=signer_id,
    )
    row = OutboundMessage(
        id=uuid.uuid4(),
        message_type=message_type.strip(),
        recipient=recipient,
        subject=subject,
        contract_id=contract_id,
        review_request_id=review_request_id,
        signature_request_id=signature_request_id,
        signer_id=signer_id,
        status="pending",
        attempt_count=0,
    )
    db.add(row)
    db.flush()
    return row


def _lock_attempt(attempt_id, db: Session) -> OutboundMessage:
    row = (
        db.query(OutboundMessage)
        .filter(OutboundMessage.id == attempt_id)
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    if row is None:
        raise EmailDeliveryError(404, "outbound_attempt_not_found")
    return row


def record_delivery_result(
    attempt_id,
    result: EmailDeliveryResult,
    db: Session,
) -> OutboundMessage:
    """Persist a safe result with locked sending and terminal transitions."""
    if result.status not in {"sent", "failed"}:
        raise EmailDeliveryError(422, "invalid_delivery_result")

    try:
        row = _lock_attempt(attempt_id, db)
        if row.status in _TERMINAL_STATUSES:
            raise EmailDeliveryError(409, "outbound_attempt_closed")
        if row.status == "pending":
            row.status = "sending"
            row.attempt_count += 1
            db.commit()

        row = _lock_attempt(attempt_id, db)
        now = _utcnow()
        row.status = result.status
        row.provider_message_id = result.provider_message_id
        row.safe_error_code = result.safe_error_code
        if result.status == "sent":
            row.sent_at = result.sent_at or now
            row.failed_at = None
        else:
            row.sent_at = None
            row.failed_at = now
        db.commit()
        db.refresh(row)
        return row
    except Exception:
        db.rollback()
        raise


def deliver_pending_attempt(
    attempt_id,
    db: Session,
    *,
    recipient: str,
    subject: str,
    text_body: str,
    html_body: str,
) -> OutboundMessage:
    """Commit `sending`, invoke SMTP, then persist only safe result metadata."""
    try:
        row = _lock_attempt(attempt_id, db)
        if row.status != "pending":
            raise EmailDeliveryError(409, "outbound_attempt_closed")
        if recipient != row.recipient or subject.strip() != row.subject:
            raise EmailDeliveryError(422, "invalid_outbound_scope")
        delivery_recipient = row.recipient
        delivery_subject = row.subject
        row.status = "sending"
        row.attempt_count += 1
        db.commit()
    except Exception:
        db.rollback()
        raise

    try:
        result = send_email(
            recipient=delivery_recipient,
            subject=delivery_subject,
            text_body=text_body,
            html_body=html_body,
        )
    except EmailDeliveryError as error:
        result = EmailDeliveryResult("failed", None, error.code, None)
    except Exception:
        result = EmailDeliveryResult("failed", None, "smtp_send_failed", None)
    return record_delivery_result(attempt_id, result, db)


def latest_delivery(
    db: Session,
    *,
    contract_id,
    message_type: str,
    review_request_id=None,
    signature_request_id=None,
    signer_id=None,
) -> OutboundMessage | None:
    query = db.query(OutboundMessage).filter(
        OutboundMessage.contract_id == contract_id,
        OutboundMessage.message_type == message_type,
    )
    if review_request_id is not None:
        query = query.filter(OutboundMessage.review_request_id == review_request_id)
    if signature_request_id is not None:
        query = query.filter(
            OutboundMessage.signature_request_id == signature_request_id
        )
    if signer_id is not None:
        query = query.filter(OutboundMessage.signer_id == signer_id)
    return query.order_by(
        OutboundMessage.created_at.desc(),
        OutboundMessage.id.desc(),
    ).first()


def enforce_resend_cooldown(
    db: Session,
    *,
    contract_id,
    message_type: str,
    review_request_id=None,
    signature_request_id=None,
    signer_id=None,
    cooldown_seconds: int = DEFAULT_RESEND_COOLDOWN_SECONDS,
) -> None:
    latest = latest_delivery(
        db,
        contract_id=contract_id,
        message_type=message_type,
        review_request_id=review_request_id,
        signature_request_id=signature_request_id,
        signer_id=signer_id,
    )
    if latest is None or latest.created_at is None:
        return
    created_at = latest.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if created_at > _utcnow() - timedelta(seconds=max(0, cooldown_seconds)):
        raise EmailDeliveryError(429, "email_resend_cooldown")


def serialize_delivery(row: OutboundMessage | None) -> dict | None:
    if row is None:
        return None
    return {
        "id": str(row.id),
        "message_type": row.message_type,
        "recipient": row.recipient,
        "subject": row.subject,
        "contract_id": str(row.contract_id),
        "review_request_id": (
            str(row.review_request_id) if row.review_request_id else None
        ),
        "signature_request_id": (
            str(row.signature_request_id) if row.signature_request_id else None
        ),
        "signer_id": str(row.signer_id) if row.signer_id else None,
        "status": row.status,
        "attempt_count": row.attempt_count,
        "provider_message_id": row.provider_message_id,
        "safe_error_code": row.safe_error_code,
        "created_at": _iso(row.created_at),
        "sent_at": _iso(row.sent_at),
        "failed_at": _iso(row.failed_at),
    }
