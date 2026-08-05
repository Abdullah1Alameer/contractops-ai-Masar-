from uuid import UUID, uuid4

import pytest

from app.db import SessionLocal
from app.models import (
    ActivityEvent,
    Contract,
    ContractVersion,
    NegotiationAttachment,
    NegotiationEmail,
    NegotiationReviewPackage,
    NegotiationRound,
)
from app.services.negotiation_monitor import service as monitor_service


@pytest.fixture
def monitor_db():
    db = SessionLocal()
    contract = Contract(
        id=uuid4(),
        title="Synthetic Monitor Agreement",
        status="ready",
        stage="negotiation",
        supported=True,
        file_url="synthetic/monitor-v1.txt",
    )
    version = ContractVersion(
        id=uuid4(),
        contract_id=contract.id,
        version_number=1,
        version_label="v1",
        source="initial_upload",
        status="ready",
        file_path=contract.file_url,
        hash_sha256="synthetic-original-hash",
        is_current=True,
        created_by="synthetic-test",
    )
    db.add_all([contract, version])
    db.commit()
    thread = monitor_service.create_thread(
        db,
        {
            "contract_id": str(contract.id),
            "counterparty_name": "Synthetic Counterparty",
            "counterparty_email": "counterparty@example.invalid",
            "subject": "Synthetic Monitor Agreement",
            "monitoring_enabled": True,
        },
        actor="legal",
    )
    yield db, contract, version, thread
    db.rollback()
    stored = db.get(Contract, contract.id)
    if stored is not None:
        db.delete(stored)
        db.commit()
    db.close()


def _manual_payload():
    return {
        "provider": "manual",
        "manual": {
            "external_message_id": "synthetic-monitor-message-1",
            "sender_name": "Synthetic Counterparty",
            "sender_email": "counterparty@example.invalid",
            "subject": "Re: Synthetic Monitor Agreement",
            "body_text": "Please review the attached synthetic revision.",
            "attachments": [
                {
                    "filename": "synthetic-monitor-revision.txt",
                    "mime_type": "text/plain",
                    "content": (
                        "SYNTHETIC MONITOR AGREEMENT\n"
                        "This synthetic contract revision changes payment timing."
                    ),
                }
            ],
        },
    }


def test_monitor_import_dedupes_email_attachment_version_and_round(monitor_db):
    db, contract, _, thread_payload = monitor_db
    thread_id = UUID(thread_payload["id"])

    first = monitor_service.import_email_to_thread(
        thread_id,
        db,
        payload=_manual_payload(),
        actor="legal",
    )
    second = monitor_service.import_email_to_thread(
        thread_id,
        db,
        payload=_manual_payload(),
        actor="legal",
    )

    assert first["round_id"] == second["round_id"]
    assert second["deduplicated"] is True
    assert db.query(NegotiationEmail).filter_by(thread_id=thread_id).count() == 1
    assert (
        db.query(NegotiationAttachment)
        .join(NegotiationEmail)
        .filter(NegotiationEmail.thread_id == thread_id)
        .count()
        == 1
    )
    assert db.query(NegotiationRound).filter_by(thread_id=thread_id).count() == 1
    assert db.query(ContractVersion).filter_by(contract_id=contract.id).count() == 2


def test_monitor_analysis_never_auto_sends(monitor_db):
    db, _, _, thread_payload = monitor_db
    thread_id = UUID(thread_payload["id"])
    imported = monitor_service.import_email_to_thread(
        thread_id,
        db,
        payload=_manual_payload(),
        actor="legal",
    )

    package = monitor_service.analyze_thread(
        thread_id,
        db,
        email_id=UUID(imported["email"]["id"]),
        actor="legal",
    )

    assert package["status"] == "ready"
    assert (
        db.query(NegotiationEmail)
        .filter_by(thread_id=thread_id, direction="outbound")
        .count()
        == 0
    )
    assert (
        db.query(NegotiationReviewPackage)
        .filter_by(thread_id=thread_id)
        .count()
        == 1
    )


def test_monitor_acceptance_uses_canonical_lifecycle(monitor_db):
    db, contract, _, thread_payload = monitor_db

    result = monitor_service.record_thread_response(
        UUID(thread_payload["id"]),
        db,
        decision="accept",
        actor="legal",
    )

    assert result["contract_stage"] == "internal_review"
    db.expire_all()
    assert db.get(Contract, contract.id).stage == "internal_review"
    events = [
        row.event_type
        for row in db.query(ActivityEvent).filter_by(contract_id=contract.id).all()
    ]
    assert "negotiation_accepted" in events
    assert "contract_entered_internal_review" in events


def test_monitor_rejection_uses_canonical_lifecycle(monitor_db):
    db, contract, _, thread_payload = monitor_db

    result = monitor_service.record_thread_response(
        UUID(thread_payload["id"]),
        db,
        decision="reject",
        actor="legal",
        reason="Synthetic definitive response",
    )

    assert result["contract_stage"] == "rejected"
    db.expire_all()
    assert db.get(Contract, contract.id).stage == "rejected"
