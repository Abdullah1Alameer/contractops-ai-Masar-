from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import (
    ActivityEvent,
    Contract,
    ContractVersion,
    Negotiation,
    ReviewRequest,
    ReviewResponse,
)
from app.services import reviews as review_service


AUTH = {
    "Authorization": "Bearer demo-secret-token",
    "X-Demo-Role": "legal",
}


@pytest.fixture(autouse=True)
def portal_token_secret(monkeypatch):
    monkeypatch.setenv("PORTAL_TOKEN_SECRET", "review-integration-secret")


@pytest.fixture
def review_db():
    db = SessionLocal()
    contract_ids = []

    def create_contract(
        *,
        stage: str = "ready_for_client",
        status: str = "ready",
        with_version: bool = True,
    ) -> tuple[Contract, ContractVersion | None]:
        contract = Contract(
            id=uuid4(),
            title="Synthetic lifecycle review",
            status=status,
            stage=stage,
            supported=True,
            file_url="synthetic/review-lifecycle.pdf",
        )
        db.add(contract)
        version = None
        if with_version:
            version = ContractVersion(
                id=uuid4(),
                contract_id=contract.id,
                version_number=1,
                version_label="v1",
                source="initial_upload",
                status="ready",
                file_path=contract.file_url,
                is_current=True,
                created_by="synthetic-test",
            )
            db.add(version)
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


def _send(client: TestClient, contract_id) -> dict:
    response = client.post(
        f"/api/contracts/{contract_id}/review/send",
        headers=AUTH,
        json={
            "recipient_name": "Synthetic Reviewer",
            "recipient_email": "reviewer@example.invalid",
            "sender_name": "Synthetic Sender",
            "sender_email": "sender@example.invalid",
            "expires_in_days": 7,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _events(db, contract_id) -> list[ActivityEvent]:
    db.expire_all()
    return (
        db.query(ActivityEvent)
        .filter_by(contract_id=contract_id)
        .order_by(ActivityEvent.created_at.asc(), ActivityEvent.id.asc())
        .all()
    )


def _event_names(db, contract_id) -> list[str]:
    return [event.event_type for event in _events(db, contract_id)]


def test_create_review_transitions_and_persists_both_events(review_db):
    db, create_contract = review_db
    contract, version = create_contract()
    payload = _send(TestClient(app), contract.id)

    db.refresh(contract)
    request = db.get(ReviewRequest, payload["request"]["id"])
    public_token = payload["request"]["token"]
    expected_link = f"http://localhost:3000/review/{public_token}"

    assert request is not None
    assert request.token is None
    assert request.token_hash == review_service.hash_token(public_token)
    assert payload["review_link"] == expected_link
    assert payload["request"]["review_link"] == expected_link
    assert expected_link in payload["email"]["body"]
    assert "/review/None" not in str(payload)
    assert request.status == "sent"
    assert request.version_id == version.id
    assert contract.stage == "client_review"
    assert "review_sent" in _event_names(db, contract.id)
    assert "contract_entered_client_review" in _event_names(db, contract.id)
    review_event = next(event for event in _events(db, contract.id) if event.event_type == "review_sent")
    assert review_event.event_metadata["review_id"] == str(request.id)
    assert review_event.event_metadata["version_id"] == str(version.id)
    assert review_event.event_metadata["actor_type"] == "internal"
    assert "token" not in review_event.event_metadata


def test_create_review_from_invalid_stage_rolls_back(review_db):
    db, create_contract = review_db
    contract, _ = create_contract(stage="draft")

    response = TestClient(app).post(
        f"/api/contracts/{contract.id}/review/send",
        headers=AUTH,
        json={
            "recipient_name": "Synthetic Reviewer",
            "recipient_email": "reviewer@example.invalid",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "invalid_stage_transition"
    db.expire_all()
    assert db.get(Contract, contract.id).stage == "draft"
    assert db.query(ReviewRequest).filter_by(contract_id=contract.id).count() == 0


def test_create_review_requires_usable_contract_and_current_version(review_db):
    db, create_contract = review_db
    processing, _ = create_contract(status="processing")
    missing_version, _ = create_contract(with_version=False)
    client = TestClient(app)
    body = {
        "recipient_name": "Synthetic Reviewer",
        "recipient_email": "reviewer@example.invalid",
    }

    processing_response = client.post(
        f"/api/contracts/{processing.id}/review/send",
        headers=AUTH,
        json=body,
    )
    version_response = client.post(
        f"/api/contracts/{missing_version.id}/review/send",
        headers=AUTH,
        json=body,
    )

    assert processing_response.status_code == 409
    assert processing_response.json()["detail"]["error"] == "contract_not_ready"
    assert version_response.status_code == 409
    assert version_response.json()["detail"]["error"] == "contract_not_ready"
    assert db.query(ReviewRequest).filter(
        ReviewRequest.contract_id.in_([processing.id, missing_version.id])
    ).count() == 0


def test_only_one_actionable_review_is_allowed_per_current_version(review_db):
    db, create_contract = review_db
    contract, _ = create_contract()
    client = TestClient(app)
    _send(client, contract.id)

    response = client.post(
        f"/api/contracts/{contract.id}/review/send",
        headers=AUTH,
        json={
            "recipient_name": "Second Synthetic Reviewer",
            "recipient_email": "second@example.invalid",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "review_already_active"
    assert db.query(ReviewRequest).filter_by(contract_id=contract.id).count() == 1


def test_open_review_is_atomic_and_idempotent(review_db):
    db, create_contract = review_db
    contract, _ = create_contract()
    sent = _send(TestClient(app), contract.id)
    token = sent["request"]["token"]
    client = TestClient(app)

    first = client.get(f"/api/review/{token}")
    second = client.get(f"/api/review/{token}")

    assert first.status_code == 200
    assert second.status_code == 200
    db.expire_all()
    request = db.get(ReviewRequest, sent["request"]["id"])
    assert request.status == "opened"
    assert db.get(Contract, contract.id).stage == "client_review"
    assert _event_names(db, contract.id).count("review_opened") == 1
    assert _event_names(db, contract.id).count("contract_entered_client_review") == 1


def test_approve_persists_response_stage_and_events(review_db):
    db, create_contract = review_db
    contract, _ = create_contract()
    sent = _send(TestClient(app), contract.id)

    response = TestClient(app).post(f"/api/review/{sent['request']['token']}/approve")

    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert response.json()["contract_stage"] == "internal_review"
    db.expire_all()
    request = db.get(ReviewRequest, sent["request"]["id"])
    stored_response = db.query(ReviewResponse).filter_by(review_request_id=request.id).one()
    assert request.status == "approved"
    assert stored_response.decision == "approve"
    assert db.get(Contract, contract.id).stage == "internal_review"
    assert "review_approved" in _event_names(db, contract.id)
    assert "contract_entered_internal_review" in _event_names(db, contract.id)


def test_request_changes_creates_one_pending_negotiation_seed(review_db):
    db, create_contract = review_db
    contract, version = create_contract()
    sent = _send(TestClient(app), contract.id)
    client = TestClient(app)

    first = client.post(
        f"/api/review/{sent['request']['token']}/request-changes",
        json={"general_comment": "Please revise the limitation language."},
    )
    second = client.post(
        f"/api/review/{sent['request']['token']}/request-changes",
        json={"general_comment": "Retry must not duplicate."},
    )

    assert first.status_code == 200
    assert first.json()["contract_stage"] == "negotiation"
    assert second.status_code == 409
    assert second.json()["detail"]["error"] == "review_closed"
    db.expire_all()
    request = db.get(ReviewRequest, sent["request"]["id"])
    seeds = db.query(Negotiation).filter_by(review_request_id=request.id).all()
    assert request.status == "changes_requested"
    assert db.get(Contract, contract.id).stage == "negotiation"
    assert len(seeds) == 1
    assert seeds[0].version_id == version.id
    assert seeds[0].workflow_status == "pending_analysis"
    assert "review_changes_requested" in _event_names(db, contract.id)
    assert "contract_entered_negotiation" in _event_names(db, contract.id)
    assert "negotiation_analysis_requested" in _event_names(db, contract.id)


def test_change_request_requires_reason_or_existing_clause_comment(review_db):
    db, create_contract = review_db
    contract, _ = create_contract()
    sent = _send(TestClient(app), contract.id)

    response = TestClient(app).post(
        f"/api/review/{sent['request']['token']}/request-changes",
        json={"general_comment": ""},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "change_request_required"
    db.expire_all()
    assert db.get(ReviewRequest, sent["request"]["id"]).status == "sent"
    assert db.get(Contract, contract.id).stage == "client_review"


def test_existing_clause_comment_can_support_change_request(review_db):
    db, create_contract = review_db
    contract, _ = create_contract()
    sent = _send(TestClient(app), contract.id)
    client = TestClient(app)
    comment = client.post(
        f"/api/review/{sent['request']['token']}/comment",
        json={
            "comment": "Please narrow this clause.",
            "clause_ref": "7.2",
        },
    )

    response = client.post(
        f"/api/review/{sent['request']['token']}/request-changes",
        json={"general_comment": None},
    )

    assert comment.status_code == 200
    assert response.status_code == 200
    db.expire_all()
    seed = db.query(Negotiation).filter_by(review_request_id=sent["request"]["id"]).one()
    assert seed.reviewer_comment == "Please narrow this clause."
    assert seed.workflow_status == "pending_analysis"


def test_reject_is_terminal_and_does_not_create_negotiation(review_db):
    db, create_contract = review_db
    contract, _ = create_contract()
    sent = _send(TestClient(app), contract.id)

    response = TestClient(app).post(
        f"/api/review/{sent['request']['token']}/reject",
        json={"reason": "Commercial terms are not acceptable."},
    )

    assert response.status_code == 200
    assert response.json()["contract_stage"] == "rejected"
    db.expire_all()
    assert db.get(ReviewRequest, sent["request"]["id"]).status == "rejected"
    assert db.get(Contract, contract.id).stage == "rejected"
    assert db.query(Negotiation).filter_by(contract_id=contract.id).count() == 0
    assert "review_rejected" in _event_names(db, contract.id)
    assert "contract_rejected" in _event_names(db, contract.id)


def test_expiry_transitions_current_review_once(review_db):
    db, create_contract = review_db
    contract, _ = create_contract()
    sent = _send(TestClient(app), contract.id)
    request = db.get(ReviewRequest, sent["request"]["id"])
    request.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    client = TestClient(app)
    public_token = sent["request"]["token"]

    first = client.get(f"/api/review/{public_token}")
    second = client.get(f"/api/review/{public_token}")

    assert first.status_code == 200
    assert first.json()["status"] == "expired"
    assert first.json()["read_only"] is True
    assert second.status_code == 200
    db.expire_all()
    assert db.get(ReviewRequest, request.id).status == "expired"
    assert db.get(Contract, contract.id).stage == "ready_for_client"
    assert _event_names(db, contract.id).count("review_expired") == 1
    assert _event_names(db, contract.id).count("contract_ready_for_client") == 1


def test_cancel_review_requires_reason_and_is_atomic(review_db):
    db, create_contract = review_db
    contract, _ = create_contract()
    sent = _send(TestClient(app), contract.id)
    client = TestClient(app)
    path = f"/api/contracts/{contract.id}/reviews/{sent['request']['id']}/cancel"

    missing = client.post(path, headers=AUTH, json={"reason": ""})
    cancelled = client.post(path, headers=AUTH, json={"reason": "Recipient changed."})

    assert missing.status_code == 422
    assert missing.json()["detail"]["error"] == "review_reason_required"
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["contract_stage"] == "ready_for_client"
    db.expire_all()
    assert db.get(ReviewRequest, sent["request"]["id"]).status == "cancelled"
    assert db.get(Contract, contract.id).stage == "ready_for_client"
    assert "review_cancelled" in _event_names(db, contract.id)
    assert "contract_ready_for_client" in _event_names(db, contract.id)


def test_stale_review_cannot_mutate_any_state(review_db):
    db, create_contract = review_db
    contract, first_version = create_contract()
    sent = _send(TestClient(app), contract.id)
    first_version.is_current = False
    second_version = ContractVersion(
        id=uuid4(),
        contract_id=contract.id,
        version_number=2,
        version_label="v2",
        source="manual_upload",
        status="ready",
        file_path="synthetic/review-lifecycle-v2.pdf",
        is_current=True,
        created_by="synthetic-test",
    )
    db.add(second_version)
    db.commit()
    event_count = len(_events(db, contract.id))

    response = TestClient(app).post(f"/api/review/{sent['request']['token']}/approve")

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "workflow_stale"
    db.expire_all()
    assert db.get(ReviewRequest, sent["request"]["id"]).status == "sent"
    assert db.query(ReviewResponse).filter_by(review_request_id=sent["request"]["id"]).count() == 0
    assert db.query(Negotiation).filter_by(review_request_id=sent["request"]["id"]).count() == 0
    assert db.get(Contract, contract.id).stage == "client_review"
    assert len(_events(db, contract.id)) == event_count


def test_duplicate_terminal_decision_returns_conflict(review_db):
    db, create_contract = review_db
    contract, _ = create_contract()
    sent = _send(TestClient(app), contract.id)
    client = TestClient(app)
    assert client.post(f"/api/review/{sent['request']['token']}/approve").status_code == 200

    duplicate = client.post(f"/api/review/{sent['request']['token']}/approve")

    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["error"] == "review_closed"
    assert db.query(ReviewResponse).filter_by(review_request_id=sent["request"]["id"]).count() == 1


def test_activity_failure_rolls_back_response_status_and_stage(review_db):
    db, create_contract = review_db
    contract, _ = create_contract()
    sent = _send(TestClient(app), contract.id)
    request = db.get(ReviewRequest, sent["request"]["id"])

    with patch("app.services.approvals.log_activity", side_effect=RuntimeError("synthetic activity failure")):
        with pytest.raises(RuntimeError, match="synthetic activity failure"):
            review_service.record_decision(request, db, "approve", actor="client")

    verify = SessionLocal()
    try:
        persisted_request = verify.get(ReviewRequest, request.id)
        persisted_contract = verify.get(Contract, contract.id)
        assert persisted_request.status == "sent"
        assert persisted_contract.stage == "client_review"
        assert verify.query(ReviewResponse).filter_by(review_request_id=request.id).count() == 0
    finally:
        verify.close()


def test_review_serialization_and_workflow_summary_read_back(review_db):
    db, create_contract = review_db
    contract, _ = create_contract()
    sent = _send(TestClient(app), contract.id)
    request_payload = sent["request"]

    assert request_payload["status"] == "sent"
    assert request_payload["contract_stage"] == "client_review"
    assert request_payload["actionable"] is True
    assert request_payload["is_stale"] is False
    assert request_payload["terminal_decision"] is None
    assert "approve" in request_payload["next_allowed_actions"]

    contract_response = TestClient(app).get(
        "/api/contracts?include=workflow_summary",
        headers=AUTH,
    )
    assert contract_response.status_code == 200
    row = next(item for item in contract_response.json() if item["id"] == str(contract.id))
    assert row["stage"] == "client_review"
    assert row["workflow_summary"]["review_status"] == "sent"

    portal_response = TestClient(app).get(f"/api/review/{request_payload['token']}")
    assert portal_response.status_code == 200
    portal = portal_response.json()
    assert portal["contract_stage"] == "client_review"
    assert portal["actionable"] is True
    assert portal["is_stale"] is False
    assert "token" not in portal
