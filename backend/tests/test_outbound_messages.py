"""Persisted tests for safe outbound delivery attempts."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError

from app.db import SessionLocal, engine
from app.models import Contract, OutboundMessage
from app.services.email_delivery import EmailDeliveryError, EmailDeliveryResult
from app.services.outbound_messages import (
    create_pending_attempt,
    deliver_pending_attempt,
    enforce_resend_cooldown,
    latest_delivery,
    record_delivery_result,
    serialize_delivery,
)


@pytest.fixture
def persisted_contract():
    db = SessionLocal()
    contract = Contract(
        id=uuid4(),
        title="Outbound test",
        status="ready",
        stage="internal_review",
        file_url="test.pdf",
    )
    db.add(contract)
    db.commit()
    try:
        yield db, contract
    finally:
        db.query(OutboundMessage).filter_by(contract_id=contract.id).delete()
        db.query(Contract).filter_by(id=contract.id).delete()
        db.commit()
        db.close()


def _pending(db, contract, *, subject="Contract review"):
    return create_pending_attempt(
        db,
        message_type="review_invitation",
        recipient="client@example.com",
        subject=subject,
        contract_id=contract.id,
    )


def test_create_pending_attempt_is_persisted_by_caller(persisted_contract):
    db, contract = persisted_contract

    attempt = _pending(db, contract)

    assert attempt.status == "pending"
    assert attempt.attempt_count == 0
    assert db.get(OutboundMessage, attempt.id) is attempt
    db.commit()
    verify = SessionLocal()
    try:
        assert verify.get(OutboundMessage, attempt.id).status == "pending"
    finally:
        verify.close()


@pytest.mark.parametrize(
    ("result", "expected_status", "timestamp_field"),
    [
        (
            EmailDeliveryResult(
                status="sent",
                provider_message_id="provider-123",
                safe_error_code=None,
                sent_at=datetime.now(timezone.utc),
            ),
            "sent",
            "sent_at",
        ),
        (
            EmailDeliveryResult(
                status="failed",
                provider_message_id=None,
                safe_error_code="smtp_send_failed",
                sent_at=None,
            ),
            "failed",
            "failed_at",
        ),
    ],
)
def test_record_delivery_result_persists_terminal_state(
    persisted_contract, result, expected_status, timestamp_field
):
    db, contract = persisted_contract
    attempt = _pending(db, contract)
    db.commit()

    recorded = record_delivery_result(attempt.id, result, db)

    assert recorded.status == expected_status
    assert recorded.attempt_count == 1
    assert getattr(recorded, timestamp_field) is not None
    assert recorded.safe_error_code == result.safe_error_code
    assert recorded.provider_message_id == result.provider_message_id


def test_record_delivery_result_uses_row_lock(persisted_contract):
    db, contract = persisted_contract
    attempt = _pending(db, contract)
    db.commit()
    locker = SessionLocal()
    contender = SessionLocal()
    try:
        locker.query(OutboundMessage).filter_by(id=attempt.id).with_for_update().one()
        contender.execute(text("SET LOCAL lock_timeout = '100ms'"))
        with pytest.raises(OperationalError):
            record_delivery_result(
                attempt.id,
                EmailDeliveryResult("failed", None, "smtp_send_failed", None),
                contender,
            )
    finally:
        contender.rollback()
        locker.rollback()
        contender.close()
        locker.close()


def test_delivery_commits_sending_before_smtp(persisted_contract, monkeypatch):
    db, contract = persisted_contract
    attempt = _pending(db, contract)
    db.commit()
    observed = {}

    def fake_send_email(**_kwargs):
        observed["transaction_open"] = db.in_transaction()
        verify = SessionLocal()
        try:
            current = verify.get(OutboundMessage, attempt.id)
            observed["status"] = current.status
            observed["attempt_count"] = current.attempt_count
        finally:
            verify.close()
        return EmailDeliveryResult(
            "sent",
            "provider-456",
            None,
            datetime.now(timezone.utc),
        )

    monkeypatch.setattr(
        "app.services.outbound_messages.send_email",
        fake_send_email,
    )

    delivered = deliver_pending_attempt(
        attempt.id,
        db,
        recipient="client@example.com",
        subject="Contract review",
        text_body="Use the secure review link.",
        html_body="<p>Use the secure review link.</p>",
    )

    assert observed == {
        "status": "sending",
        "attempt_count": 1,
        "transaction_open": False,
    }
    assert delivered.status == "sent"


def test_latest_delivery_is_workflow_scoped(persisted_contract):
    db, contract = persisted_contract
    first = _pending(db, contract, subject="First")
    db.commit()
    second = _pending(db, contract, subject="Second")
    db.commit()

    latest = latest_delivery(db, contract_id=contract.id, message_type="review_invitation")

    assert latest.id == second.id
    assert latest.id != first.id
    assert latest_delivery(db, contract_id=uuid4(), message_type="review_invitation") is None


def test_failed_delivery_does_not_start_resend_cooldown(persisted_contract):
    db, contract = persisted_contract
    attempt = _pending(db, contract)
    db.commit()
    record_delivery_result(
        attempt.id,
        EmailDeliveryResult("failed", None, "smtp_send_failed", None),
        db,
    )

    enforce_resend_cooldown(
        db,
        contract_id=contract.id,
        message_type="review_invitation",
    )


def test_cooldown_rejects_recent_resend(persisted_contract):
    db, contract = persisted_contract
    _pending(db, contract)
    db.commit()

    with pytest.raises(EmailDeliveryError) as caught:
        enforce_resend_cooldown(
            db,
            contract_id=contract.id,
            message_type="review_invitation",
            cooldown_seconds=60,
        )

    assert caught.value.status_code == 429
    assert caught.value.code == "email_resend_cooldown"


def test_cooldown_allows_old_attempt(persisted_contract):
    db, contract = persisted_contract
    attempt = _pending(db, contract)
    db.commit()
    db.execute(
        text("UPDATE outbound_messages SET created_at = :created_at WHERE id = :id"),
        {
            "created_at": datetime.now(timezone.utc) - timedelta(minutes=2),
            "id": attempt.id,
        },
    )
    db.commit()

    enforce_resend_cooldown(
        db,
        contract_id=contract.id,
        message_type="review_invitation",
        cooldown_seconds=60,
    )


def test_schema_and_serialization_exclude_sensitive_payloads(persisted_contract):
    db, contract = persisted_contract
    attempt = _pending(db, contract)
    db.commit()

    column_names = {column["name"] for column in inspect(engine).get_columns("outbound_messages")}
    forbidden_columns = {
        "body",
        "text_body",
        "html_body",
        "token",
        "token_hash",
        "credentials",
        "contract_content",
        "signature_data",
    }
    assert column_names.isdisjoint(forbidden_columns)

    serialized = serialize_delivery(attempt)
    assert serialized["recipient"] == "client@example.com"
    assert serialized["status"] == "pending"
    assert not any(key in serialized for key in forbidden_columns)
