"""Persisted PostgreSQL proof for the canonical signature lifecycle."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
import fitz
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import (
    ActivityEvent,
    ApprovalWorkflow,
    Contract,
    ContractVersion,
    Negotiation,
    OutboundMessage,
    SignatureRequest,
    SignatureSigner,
    SignatureEvent,
)
from app.services import signature as signature_service
from app.services.email_delivery import EmailDeliveryResult
from app.services.signature import SignatureError
from app.services.storage import storage


AUTH = {"Authorization": "Bearer demo-secret-token", "X-Demo-Role": "legal"}


def _pdf_bytes():
    document = fitz.open()
    document.new_page().insert_text((72, 72), "Synthetic signature lifecycle")
    data = document.tobytes()
    document.close()
    return data


@pytest.fixture(autouse=True)
def portal_token_secret(monkeypatch):
    monkeypatch.setenv("PORTAL_TOKEN_SECRET", "signature-integration-secret")


@pytest.fixture
def signature_db():
    db = SessionLocal()
    contract_ids = []

    def create_contract(
        *,
        stage="ready_to_sign",
        version_status="approved",
        with_approved_workflow=True,
    ):
        file_key = storage.save(_pdf_bytes(), "signature-lifecycle.pdf")
        contract = Contract(
            id=uuid4(),
            title="Synthetic signature lifecycle",
            status="ready",
            stage=stage,
            supported=True,
            file_url=file_key,
        )
        version = ContractVersion(
            id=uuid4(),
            contract_id=contract.id,
            version_number=1,
            version_label="v1",
            source="initial_upload",
            status=version_status,
            file_path=contract.file_url,
            is_current=True,
            created_by="synthetic-test",
        )
        db.add_all([contract, version])
        db.flush()
        if with_approved_workflow:
            db.add(
                ApprovalWorkflow(
                    id=uuid4(),
                    contract_id=contract.id,
                    version_id=version.id,
                    status="approved",
                )
            )
        db.commit()
        contract_ids.append(contract.id)
        return contract, version

    yield db, create_contract

    db.rollback()
    for contract_id in contract_ids:
        contract = db.get(Contract, contract_id)
        if contract is not None:
            db.delete(contract)
    db.commit()
    db.close()


def _place_fields(client, request_id, signer_ids, *, page_number=1):
    response = client.put(
        f"/api/signature-requests/{request_id}/fields",
        headers=AUTH,
        json={
            "fields": [
                {
                    "signer_id": sid,
                    "page_number": page_number,
                    "x": 0.08,
                    "y": 0.1 + index * 0.15,
                    "width": 0.36,
                    "height": 0.06,
                    "field_type": "signature",
                    "required": True,
                }
                for index, sid in enumerate(signer_ids)
            ]
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["fields"]


def _create(client, contract_id, *, place_fields=True):
    response = client.post(
        f"/api/contracts/{contract_id}/signature-request",
        headers=AUTH,
        json={
            "subject": "Please sign",
            "message": "Synthetic signing invitation",
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "signing_order_enabled": True,
            "signers": [
                {
                    "name": "Signer One",
                    "email": "one@example.invalid",
                    "role": "company_signatory",
                    "order": 1,
                },
                {
                    "name": "Signer Two",
                    "email": "two@example.invalid",
                    "role": "client_signatory",
                    "order": 2,
                },
            ],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    if place_fields:
        signer_ids = [s["id"] for s in body["signers"]]
        _place_fields(client, body["request"]["id"], signer_ids)
    return body


def _send(client, request_id):
    response = client.post(f"/api/signature-requests/{request_id}/send", headers=AUTH)
    assert response.status_code == 200, response.text
    return response.json()


def _sign(client, token, name):
    return client.post(
        f"/api/public/sign/{token}/submit",
        json={
            "signature_type": "typed",
            "signature_value": name,
            "consent_accepted": True,
            "signer_name_confirmation": name,
        },
    )


def _events(db, contract_id):
    db.expire_all()
    return (
        db.query(ActivityEvent)
        .filter_by(contract_id=contract_id)
        .order_by(ActivityEvent.created_at.asc(), ActivityEvent.id.asc())
        .all()
    )


def test_creation_is_eligible_draft_and_sends_nothing(signature_db):
    db, create_contract = signature_db
    contract, version = create_contract()

    payload = _create(TestClient(app), contract.id)

    request = db.get(SignatureRequest, payload["request"]["id"])
    signers = (
        db.query(SignatureSigner)
        .filter_by(signature_request_id=request.id)
        .order_by(SignatureSigner.signer_order)
        .all()
    )
    assert request.status == "draft"
    assert request.version_id == version.id
    assert db.get(Contract, contract.id).stage == "ready_to_sign"
    assert [row.status for row in signers] == ["waiting", "waiting"]
    assert db.query(OutboundMessage).filter_by(signature_request_id=request.id).count() == 0
    assert all("token" not in str(event.event_metadata).lower() for event in _events(db, contract.id))


@pytest.mark.parametrize(
    ("stage", "version_status", "workflow", "expected"),
    [
        ("internal_review", "approved", True, "invalid_stage_transition"),
        ("ready_to_sign", "ready", True, "version_not_approved"),
        ("ready_to_sign", "approved", False, "approval_not_complete"),
    ],
)
def test_creation_requires_ready_current_approved_version_and_completed_approval(
    signature_db, stage, version_status, workflow, expected
):
    _db, create_contract = signature_db
    contract, _version = create_contract(
        stage=stage, version_status=version_status, with_approved_workflow=workflow
    )
    response = TestClient(app).post(
        f"/api/contracts/{contract.id}/signature-request",
        headers=AUTH,
        json={
            "subject": "Please sign",
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "signers": [{"name": "A", "email": "a@example.invalid", "order": 1}],
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == expected


def test_creation_rejects_unresolved_current_version_negotiation_without_mutation(signature_db):
    db, create_contract = signature_db
    contract, version = create_contract()
    db.add(Negotiation(
        id=uuid4(), contract_id=contract.id, version_id=version.id, clause_ref="7.1",
        reviewer_comment="Unresolved", reviewer_decision="changes_requested",
        status="draft", workflow_status="pending_analysis",
    ))
    db.commit()

    response = TestClient(app).post(
        f"/api/contracts/{contract.id}/signature-request", headers=AUTH,
        json={
            "subject": "Please sign",
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "signers": [{"name": "A", "email": "a@example.invalid", "order": 1}],
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "unresolved_negotiations"
    assert db.query(SignatureRequest).filter_by(contract_id=contract.id).count() == 0
    assert db.get(Contract, contract.id).stage == "ready_to_sign"


def test_failed_delivery_preserves_request_link_and_retry_reuses_it(signature_db, monkeypatch):
    db, create_contract = signature_db
    contract, _ = create_contract()
    created = _create(TestClient(app), contract.id)
    request_id = created["request"]["id"]
    first_token = created["signer_links"][0]["token"]
    monkeypatch.setattr(
        "app.services.outbound_messages.send_email",
        lambda **_kwargs: EmailDeliveryResult("failed", None, "smtp_connection_failed", None),
    )

    sent = _send(TestClient(app), request_id)

    request = db.get(SignatureRequest, request_id)
    signer = db.query(SignatureSigner).filter_by(signature_request_id=request.id, signer_order=1).one()
    attempt = db.query(OutboundMessage).filter_by(signer_id=signer.id).one()
    assert request.status == "sent"
    assert signer.status == "invited"
    assert attempt.status == "failed"
    assert first_token not in str(attempt.__dict__)

    attempt.created_at = datetime.now(timezone.utc) - timedelta(minutes=2)
    db.commit()
    retried = TestClient(app).post(
        f"/api/signature-requests/{request_id}/resend/{signer.id}", headers=AUTH
    )
    assert retried.status_code == 200, retried.text
    assert retried.json()["signer_link"].endswith(first_token)
    assert db.query(OutboundMessage).filter_by(signer_id=signer.id).count() == 2


def test_bundle_exposes_persisted_signer_delivery_only_for_eligible_signer(
    signature_db, monkeypatch
):
    db, create_contract = signature_db
    contract, _ = create_contract()
    monkeypatch.setattr(
        "app.services.outbound_messages.send_email",
        lambda **_kwargs: EmailDeliveryResult("sent", "message-id", None, datetime.now(timezone.utc)),
    )
    client = TestClient(app)
    created = _create(client, contract.id)
    request_id = created["request"]["id"]
    first_token, second_token = [row["token"] for row in created["signer_links"]]
    _send(client, request_id)

    bundle = client.get(f"/api/contracts/{contract.id}/signature-request", headers=AUTH).json()
    first, second = bundle["request"]["signers"]

    assert first["status"] == "invited"
    assert first["eligible"] is True
    assert first["delivery"]["status"] == "sent"
    assert first["delivery"]["attempt_count"] == 1
    assert first["delivery"]["sent_at"] is not None
    assert first["signer_link"] is not None and first["signer_link"].endswith(first_token)

    assert second["status"] == "waiting"
    assert second["eligible"] is False
    assert second["delivery"] is None
    assert second["signer_link"] is None
    assert second_token not in str(bundle)

    assert _sign(client, first_token, "Signer One").status_code == 200

    refreshed = client.get(f"/api/contracts/{contract.id}/signature-request", headers=AUTH).json()
    first_after, second_after = refreshed["request"]["signers"]
    assert first_after["status"] == "signed"
    assert first_after["eligible"] is False
    assert first_after["signer_link"] is None
    assert first_after["delivery"]["status"] == "sent"
    assert second_after["status"] == "invited"
    assert second_after["eligible"] is True
    assert second_after["delivery"]["status"] == "sent"
    assert second_after["signer_link"] is not None and second_after["signer_link"].endswith(second_token)


def test_bundle_marks_signer_ineligible_and_hides_link_once_request_is_stale(
    signature_db, monkeypatch
):
    """A stale request (superseded contract version) must never advertise a
    resend/copy-link action that `resend_signer` would itself reject."""
    db, create_contract = signature_db
    contract, version = create_contract()
    monkeypatch.setattr(
        "app.services.outbound_messages.send_email",
        lambda **_kwargs: EmailDeliveryResult("sent", "message-id", None, datetime.now(timezone.utc)),
    )
    client = TestClient(app)
    created = _create(client, contract.id)
    request_id = created["request"]["id"]
    first_signer_id = created["request"]["signers"][0]["id"]
    _send(client, request_id)

    version.is_current = False
    db.add(
        ContractVersion(
            id=uuid4(), contract_id=contract.id, version_number=2, version_label="v2",
            source="manual_upload", status="ready", file_path=contract.file_url,
            is_current=True, created_by="synthetic-test",
        )
    )
    db.commit()

    bundle = client.get(f"/api/contracts/{contract.id}/signature-request", headers=AUTH).json()
    first, second = bundle["request"]["signers"]
    assert bundle["request"]["is_stale"] is True
    assert first["status"] == "invited"
    assert first["eligible"] is False
    assert first["signer_link"] is None
    assert second["eligible"] is False
    assert second["signer_link"] is None

    resend = client.post(
        f"/api/signature-requests/{request_id}/resend/{first_signer_id}", headers=AUTH
    )
    assert resend.status_code == 409
    assert resend.json()["detail"]["error"] == "workflow_stale"


def test_ordered_signing_persists_partial_then_signed_without_auto_activation(
    signature_db, monkeypatch
):
    db, create_contract = signature_db
    contract, version = create_contract()
    monkeypatch.setattr(
        "app.services.outbound_messages.send_email",
        lambda **_kwargs: EmailDeliveryResult("sent", "message-id", None, datetime.now(timezone.utc)),
    )
    client = TestClient(app)
    created = _create(client, contract.id)
    request_id = created["request"]["id"]
    first_token, second_token = [row["token"] for row in created["signer_links"]]
    _send(client, request_id)

    first = _sign(client, first_token, "Signer One")
    assert first.status_code == 200, first.text
    db.expire_all()
    request = db.get(SignatureRequest, request_id)
    signers = (
        db.query(SignatureSigner).filter_by(signature_request_id=request.id).order_by(SignatureSigner.signer_order).all()
    )
    assert request.status == "partially_signed"
    assert db.get(Contract, contract.id).stage == "partially_signed"
    assert [row.status for row in signers] == ["signed", "invited"]
    assert db.query(OutboundMessage).filter_by(signer_id=signers[1].id).count() == 1

    final = _sign(client, second_token, "Signer Two")
    assert final.status_code == 200, final.text
    db.expire_all()
    request = db.get(SignatureRequest, request_id)
    assert request.status == "completed"
    assert request.signed_file_url and request.certificate_file_url
    assert db.get(Contract, contract.id).stage == "signed"
    assert db.get(ContractVersion, version.id).status == "signed"
    raw_tokens = {first_token, second_token}
    event_payloads = [
        str(row.event_metadata)
        for row in db.query(ActivityEvent).filter_by(contract_id=contract.id).all()
    ] + [
        str(row.event_metadata)
        for row in db.query(SignatureEvent).filter_by(signature_request_id=request.id).all()
    ]
    outbound_rows = db.query(OutboundMessage).filter_by(signature_request_id=request.id).all()
    for raw_token in raw_tokens:
        assert all(raw_token not in payload for payload in event_payloads)
        assert all(raw_token not in str(row.__dict__) for row in outbound_rows)


def test_duplicate_out_of_order_and_stale_actions_do_not_mutate(signature_db):
    db, create_contract = signature_db
    contract, version = create_contract()
    client = TestClient(app)
    created = _create(client, contract.id)
    _send(client, created["request"]["id"])
    second_token = created["signer_links"][1]["token"]

    out_of_order = _sign(client, second_token, "Signer Two")
    assert out_of_order.status_code == 409
    assert out_of_order.json()["detail"]["error"] == "not_active_signer"

    version.is_current = False
    db.add(
        ContractVersion(
            id=uuid4(), contract_id=contract.id, version_number=2, version_label="v2",
            source="manual_upload", status="ready", file_path=contract.file_url,
            is_current=True, created_by="synthetic-test",
        )
    )
    db.commit()
    stale = _sign(client, created["signer_links"][0]["token"], "Signer One")
    assert stale.status_code == 409
    assert stale.json()["detail"]["error"] == "workflow_stale"
    request = db.get(SignatureRequest, created["request"]["id"])
    assert request.status == "sent"
    assert db.get(Contract, contract.id).stage == "ready_to_sign"


def test_decline_cancel_expiry_and_manual_activation_use_canonical_transitions(signature_db):
    db, create_contract = signature_db
    contract, _ = create_contract()
    client = TestClient(app)
    created = _create(client, contract.id)
    _send(client, created["request"]["id"])

    declined = client.post(
        f"/api/public/sign/{created['signer_links'][0]['token']}/decline",
        json={"reason": "Authority changed."},
    )
    assert declined.status_code == 200, declined.text
    db.expire_all()
    assert db.get(Contract, contract.id).stage == "internal_review"

    second_contract, _ = create_contract()
    request_id = _create(client, second_contract.id)["request"]["id"]
    cancelled = client.post(
        f"/api/signature-requests/{request_id}/cancel",
        headers=AUTH,
        json={"reason": "Signer package replaced."},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert db.get(Contract, second_contract.id).stage == "ready_to_sign"

    signed_contract, _ = create_contract(stage="signed")
    activated = client.post(
        f"/api/signature-requests/{uuid4()}/activate",
        headers=AUTH,
        json={"reason": "Effective date verified.", "evidence": "synthetic-evidence"},
    )
    assert activated.status_code == 404
    assert db.get(Contract, signed_contract.id).stage == "signed"


def test_final_artifact_failure_rolls_back_completion_and_removes_orphan_signature(signature_db, monkeypatch):
    db, create_contract = signature_db
    contract, _ = create_contract()
    client = TestClient(app)
    created = _create(client, contract.id)
    _send(client, created["request"]["id"])
    assert _sign(client, created["signer_links"][0]["token"], "Signer One").status_code == 200

    saved_keys = []
    real_save = signature_service.storage.save

    def save_then_fail(data, filename):
        if filename.startswith("cert_"):
            raise RuntimeError("synthetic certificate failure")
        key = real_save(data, filename)
        saved_keys.append(key)
        return key

    monkeypatch.setattr(signature_service.storage, "save", save_then_fail)
    with pytest.raises(RuntimeError, match="synthetic certificate failure"):
        _sign(client, created["signer_links"][1]["token"], "Signer Two")

    verify = SessionLocal()
    try:
        request = verify.get(SignatureRequest, created["request"]["id"])
        assert request.status == "partially_signed"
        assert request.signed_file_url is None
        assert verify.get(Contract, contract.id).stage == "partially_signed"
    finally:
        verify.close()
    for key in saved_keys:
        assert not (signature_service.storage.base_dir and key and __import__("os").path.exists(
            __import__("os").path.join(signature_service.storage.base_dir, key)
        ))


def test_open_is_locked_current_and_emits_viewed_transition(signature_db):
    db, create_contract = signature_db
    contract, _ = create_contract()
    client = TestClient(app)
    created = _create(client, contract.id)
    _send(client, created["request"]["id"])

    opened = client.post(f"/api/public/sign/{created['signer_links'][0]['token']}/open")

    assert opened.status_code == 200, opened.text
    db.expire_all()
    request = db.get(SignatureRequest, created["request"]["id"])
    signer = db.query(SignatureSigner).filter_by(signature_request_id=request.id, signer_order=1).one()
    assert request.status == "viewed"
    assert signer.status == "opened"
    assert "signature_viewed" in [event.event_type for event in _events(db, contract.id)]


def test_second_signer_opens_after_partial_signature_once(signature_db):
    db, create_contract = signature_db
    contract, _ = create_contract()
    client = TestClient(app)
    created = _create(client, contract.id)
    _send(client, created["request"]["id"])
    assert _sign(client, created["signer_links"][0]["token"], "Signer One").status_code == 200

    first = client.post(f"/api/public/sign/{created['signer_links'][1]['token']}/open")
    second = client.post(f"/api/public/sign/{created['signer_links'][1]['token']}/open")

    assert first.status_code == second.status_code == 200
    db.expire_all()
    request = db.get(SignatureRequest, created["request"]["id"])
    signer = db.query(SignatureSigner).filter_by(signature_request_id=request.id, signer_order=2).one()
    assert request.status == "partially_signed"
    assert signer.status == "opened" and signer.opened_at is not None
    event_names = [event.event_type for event in _events(db, contract.id)]
    assert event_names.count("signature_viewed") == 1
    assert event_names.count("signature_link_opened") == 1


def test_expiry_closes_request_and_returns_stage_once(signature_db):
    db, create_contract = signature_db
    contract, _ = create_contract()
    client = TestClient(app)
    created = _create(client, contract.id)
    _send(client, created["request"]["id"])
    request = db.get(SignatureRequest, created["request"]["id"])
    request.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()

    first = client.get(f"/api/public/sign/{created['signer_links'][0]['token']}")
    second = client.get(f"/api/public/sign/{created['signer_links'][0]['token']}")

    assert first.status_code == second.status_code == 410
    db.expire_all()
    assert db.get(SignatureRequest, request.id).status == "expired"
    assert db.get(Contract, contract.id).stage == "ready_to_sign"
    assert [event.event_type for event in _events(db, contract.id)].count("signature_request_expired") == 1


def test_manual_activation_requires_authorized_evidence_and_moves_signed_contract(signature_db):
    db, create_contract = signature_db
    contract, version = create_contract(stage="signed", version_status="signed")
    request = SignatureRequest(
        id=uuid4(), contract_id=contract.id, version_id=version.id, provider="simulated",
        status="completed", subject="Executed", expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db.add(request)
    db.commit()
    client = TestClient(app)

    missing = client.post(f"/api/signature-requests/{request.id}/activate", headers=AUTH, json={"reason": " ", "evidence": " "})
    forbidden = client.post(
        f"/api/signature-requests/{request.id}/activate",
        headers={**AUTH, "X-Demo-Role": "finance"},
        json={"reason": "Effective", "evidence": "Record"},
    )
    activated = client.post(
        f"/api/signature-requests/{request.id}/activate",
        headers=AUTH,
        json={"reason": "Effective", "evidence": "Record"},
    )

    assert missing.status_code == 422
    assert missing.json()["detail"]["error"] == "activation_reason_evidence_required"
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"]["error"] == "signature_activation_forbidden"
    assert activated.status_code == 200, activated.text
    db.expire_all()
    assert db.get(Contract, contract.id).stage == "active"
    event_names = [event.event_type for event in _events(db, contract.id)]
    assert event_names.count("contract_activated") == 1


def _completed_request(db, contract, version, *, status="completed"):
    request = SignatureRequest(
        id=uuid4(), contract_id=contract.id, version_id=version.id, provider="simulated",
        status=status, subject="Executed", expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db.add(request)
    db.commit()
    return request


def test_activation_never_persists_raw_reason_or_evidence(signature_db):
    db, create_contract = signature_db
    contract, version = create_contract(stage="signed", version_status="signed")
    request = _completed_request(db, contract, version)
    client = TestClient(app)
    raw_reason = "Counterparty countersigned on 2026-04-01 per CFO Layla Al-Harbi"
    raw_evidence = "Scanned wet-ink page stored at vault://legal/482-secret"

    activated = client.post(
        f"/api/signature-requests/{request.id}/activate",
        headers=AUTH,
        json={"reason": raw_reason, "evidence": raw_evidence},
    )

    assert activated.status_code == 200, activated.text
    db.expire_all()
    assert db.get(Contract, contract.id).stage == "active"
    activities = _events(db, contract.id)
    payloads = [str(row.event_metadata) for row in activities] + [
        str(row.event_metadata)
        for row in db.query(SignatureEvent).filter_by(signature_request_id=request.id).all()
    ]
    assert payloads, "activation must persist at least one auditable event"
    for payload in payloads:
        assert raw_reason not in payload
        assert raw_evidence not in payload
    activation = [row for row in activities if row.event_type == "contract_activated"]
    assert len(activation) == 1
    metadata = activation[0].event_metadata or {}
    assert metadata.get("reason_present") is True
    assert metadata.get("evidence_present") is True
    assert "reason" not in metadata
    assert "evidence" not in metadata


def test_activation_on_incomplete_request_returns_activation_not_ready_without_mutation(signature_db):
    db, create_contract = signature_db
    contract, version = create_contract(stage="signed", version_status="signed")
    request = _completed_request(db, contract, version, status="sent")
    before = [event.event_type for event in _events(db, contract.id)]
    client = TestClient(app)

    response = client.post(
        f"/api/signature-requests/{request.id}/activate",
        headers=AUTH,
        json={"reason": "Effective date verified.", "evidence": "Countersigned scan"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "activation_not_ready"
    db.expire_all()
    assert db.get(Contract, contract.id).stage == "signed"
    assert db.get(SignatureRequest, request.id).status == "sent"
    assert [event.event_type for event in _events(db, contract.id)] == before


def test_activation_on_stale_request_returns_workflow_stale_without_mutation(signature_db):
    db, create_contract = signature_db
    contract, version = create_contract(stage="signed", version_status="signed")
    request = _completed_request(db, contract, version)
    version.is_current = False
    db.add(
        ContractVersion(
            id=uuid4(), contract_id=contract.id, version_number=2, version_label="v2",
            source="manual_upload", status="ready", file_path=contract.file_url,
            is_current=True, created_by="synthetic-test",
        )
    )
    db.commit()
    before = [event.event_type for event in _events(db, contract.id)]
    client = TestClient(app)

    response = client.post(
        f"/api/signature-requests/{request.id}/activate",
        headers=AUTH,
        json={"reason": "Effective date verified.", "evidence": "Countersigned scan"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "workflow_stale"
    db.expire_all()
    assert db.get(Contract, contract.id).stage == "signed"
    assert db.get(SignatureRequest, request.id).status == "completed"
    assert [event.event_type for event in _events(db, contract.id)] == before
