import json
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
from app.services import negotiation as negotiation_service


AUTH = {
    "Authorization": "Bearer demo-secret-token",
    "X-Demo-Role": "legal",
}
AI_RESULT = {
    "summary": "Synthetic advisory summary",
    "business_impact": "Synthetic business impact",
    "legal_impact": "Synthetic legal impact",
    "risk_level": "medium",
    "recommendation": "negotiate",
    "reasoning": "Synthetic source-based reasoning",
    "counter_clause": "Synthetic counterproposal",
    "arabic_counter_clause": "صياغة اصطناعية",
    "pros": ["Synthetic benefit"],
    "cons": ["Synthetic tradeoff"],
}


@pytest.fixture(autouse=True)
def portal_token_secret(monkeypatch):
    monkeypatch.setenv("PORTAL_TOKEN_SECRET", "negotiation-integration-secret")


@pytest.fixture
def negotiation_db():
    db = SessionLocal()
    contract_ids = []

    def create_case(*, item_count: int = 1):
        contract = Contract(
            id=uuid4(),
            title="Synthetic negotiation lifecycle",
            status="ready",
            stage="negotiation",
            supported=True,
            file_url="synthetic/negotiation.pdf",
        )
        version = ContractVersion(
            id=uuid4(),
            contract_id=contract.id,
            version_number=1,
            version_label="v1",
            source="initial_upload",
            status="ready",
            file_path=contract.file_url,
            extracted_json={"synthetic": True},
            is_current=True,
            created_by="synthetic-test",
        )
        review = ReviewRequest(
            id=uuid4(),
            contract_id=contract.id,
            version_id=version.id,
            token=f"source-{uuid4()}",
            recipient_name="Synthetic Counterparty",
            recipient_email="counterparty@example.invalid",
            sender_name="Synthetic Legal",
            sender_email="legal@example.invalid",
            status="changes_requested",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            responded_at=datetime.now(timezone.utc),
        )
        response = ReviewResponse(
            id=uuid4(),
            review_request_id=review.id,
            decision="changes_requested",
            overall_comment="Synthetic change request",
        )
        db.add_all([contract, version, review, response])
        db.flush()
        negotiations = []
        for index in range(item_count):
            negotiation = Negotiation(
                id=uuid4(),
                contract_id=contract.id,
                version_id=version.id,
                review_request_id=review.id,
                review_comment_id=None,
                clause_ref=f"{index + 1}.1",
                reviewer_comment=f"Synthetic change {index + 1}",
                reviewer_decision="changes_requested",
                status="draft",
                workflow_status="pending_analysis",
                final_summary={
                    "lifecycle": {
                        "round_number": 1,
                        "human_decision_required": True,
                    }
                },
            )
            db.add(negotiation)
            negotiations.append(negotiation)
        db.commit()
        contract_ids.append(contract.id)
        return contract, version, review, negotiations

    yield db, create_case

    db.rollback()
    for contract_id in contract_ids:
        contract = db.get(Contract, contract_id)
        if contract is not None:
            db.delete(contract)
    db.commit()
    db.close()


def _events(db, contract_id) -> list[str]:
    db.expire_all()
    return [
        row.event_type
        for row in (
            db.query(ActivityEvent)
            .filter_by(contract_id=contract_id)
            .order_by(ActivityEvent.created_at.asc(), ActivityEvent.id.asc())
            .all()
        )
    ]


def _analyze(client: TestClient, review_id) -> dict:
    response = client.post(
        "/api/negotiation/analyze",
        headers=AUTH,
        json={"review_id": str(review_id), "comment_id": None},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _followup(db, negotiation: Negotiation, version_id) -> ReviewRequest:
    review = ReviewRequest(
        id=uuid4(),
        contract_id=negotiation.contract_id,
        version_id=version_id,
        token=f"followup-{uuid4()}",
        recipient_name="Synthetic Counterparty",
        recipient_email="counterparty@example.invalid",
        status="sent",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(review)
    db.flush()
    negotiation.sent_review_request_id = review.id
    negotiation.status = "sent"
    negotiation.workflow_status = "sent_to_client"
    negotiation.sent_at = datetime.now(timezone.utc)
    db.commit()
    return review


def test_review_seed_is_reused_and_analysis_is_idempotent(negotiation_db):
    db, create_case = negotiation_db
    contract, _, review, negotiations = create_case()
    client = TestClient(app)

    with patch.object(negotiation_service, "complete_json", return_value=AI_RESULT) as complete:
        first = _analyze(client, review.id)
        second = _analyze(client, review.id)

    assert first["id"] == str(negotiations[0].id)
    assert second["id"] == first["id"]
    assert complete.call_count == 1
    db.expire_all()
    stored = db.get(Negotiation, negotiations[0].id)
    assert stored.workflow_status == "ready"
    assert stored.ai_summary == AI_RESULT["summary"]
    assert stored.final_summary["lifecycle"]["human_decision_required"] is True
    assert db.query(Negotiation).filter_by(review_request_id=review.id).count() == 1
    assert db.get(Contract, contract.id).stage == "negotiation"
    assert _events(db, contract.id).count("negotiation_analysis_started") == 1
    assert _events(db, contract.id).count("negotiation_analyzed") == 1


def test_ai_failure_preserves_retryable_seed_without_stage_change(negotiation_db):
    db, create_case = negotiation_db
    contract, _, review, negotiations = create_case()

    with patch.object(
        negotiation_service,
        "complete_json",
        side_effect=RuntimeError("synthetic AI failure"),
    ):
        response = TestClient(app).post(
            "/api/negotiation/analyze",
            headers=AUTH,
            json={"review_id": str(review.id), "comment_id": None},
        )

    assert response.status_code == 502
    assert response.json()["detail"]["error"] == "ai_failed"
    db.expire_all()
    stored = db.get(Negotiation, negotiations[0].id)
    assert stored.workflow_status == "pending_analysis"
    assert stored.final_summary["lifecycle"]["analysis_status"] == "failed"
    assert stored.final_summary["lifecycle"]["retryable"] is True
    assert db.get(Contract, contract.id).stage == "negotiation"


def test_legal_edit_preserves_original_ai_content(negotiation_db):
    db, create_case = negotiation_db
    contract, _, _, negotiations = create_case()
    negotiation = negotiations[0]
    negotiation.workflow_status = "ready"
    negotiation.ai_summary = AI_RESULT["summary"]
    negotiation.counter_clause = AI_RESULT["counter_clause"]
    db.commit()

    response = TestClient(app).patch(
        f"/api/negotiations/{negotiation.id}",
        headers=AUTH,
        json={"lawyer_final_clause": "Synthetic lawyer-approved wording"},
    )

    assert response.status_code == 200
    assert response.json()["workflow_status"] == "edited_by_legal"
    db.expire_all()
    stored = db.get(Negotiation, negotiation.id)
    assert stored.ai_summary == AI_RESULT["summary"]
    assert stored.counter_clause == AI_RESULT["counter_clause"]
    assert stored.lawyer_final_clause == "Synthetic lawyer-approved wording"
    assert db.get(Contract, contract.id).stage == "negotiation"
    assert _events(db, contract.id).count("negotiation_edited") == 1


def test_counterproposal_send_is_atomic_and_idempotent(negotiation_db):
    db, create_case = negotiation_db
    contract, version, _, negotiations = create_case()
    negotiation = negotiations[0]
    negotiation.workflow_status = "edited_by_legal"
    negotiation.status = "approved"
    negotiation.lawyer_final_clause = "Synthetic lawyer-approved wording"
    db.commit()
    client = TestClient(app)

    first = client.post(f"/api/negotiations/{negotiation.id}/send", headers=AUTH)
    second = client.post(f"/api/negotiations/{negotiation.id}/send", headers=AUTH)

    assert first.status_code == 200, first.text
    first_payload = first.json()
    public_token = first_payload["request"]["token"]
    expected_link = f"http://localhost:3000/review/{public_token}"
    assert first_payload["review_link"] == expected_link
    assert first_payload["request"]["review_link"] == expected_link
    assert first_payload["negotiation"]["final_summary"]["review_link"] == expected_link
    assert expected_link in first_payload["email"]["body"]
    assert "/review/None" not in str(first_payload)
    assert second.status_code == 409
    assert second.json()["detail"]["error"] == "followup_review_already_active"
    db.expire_all()
    stored = db.get(Negotiation, negotiation.id)
    versions = db.query(ContractVersion).filter_by(contract_id=contract.id).all()
    reviews = db.query(ReviewRequest).filter_by(contract_id=contract.id).all()
    assert len(versions) == 2
    assert sum(1 for row in versions if row.is_current) == 1
    assert next(row for row in versions if row.is_current).parent_version_id == version.id
    assert stored.version_id == next(row for row in versions if row.is_current).id
    assert stored.workflow_status == "sent_to_client"
    assert stored.status == "sent"
    assert stored.sent_review_request_id is not None
    assert stored.final_summary["review_link"] == expected_link
    assert len(reviews) == 2
    assert db.get(Contract, contract.id).stage == "negotiation"
    assert _events(db, contract.id).count("counterproposal_sent") == 1


def test_partial_then_final_acceptance_moves_stage_only_when_all_resolved(negotiation_db):
    db, create_case = negotiation_db
    contract, version, _, negotiations = create_case(item_count=2)
    followups = [_followup(db, negotiation, version.id) for negotiation in negotiations]
    client = TestClient(app)

    first = client.post(f"/api/review/{followups[0].token}/approve")

    assert first.status_code == 200, first.text
    assert first.json()["contract_stage"] == "negotiation"
    assert first.json()["negotiation"]["unresolved_count"] == 1
    db.expire_all()
    assert db.get(Negotiation, negotiations[0].id).workflow_status == "accepted"
    assert db.get(Contract, contract.id).stage == "negotiation"

    second = client.post(f"/api/review/{followups[1].token}/approve")

    assert second.status_code == 200, second.text
    assert second.json()["contract_stage"] == "internal_review"
    assert second.json()["negotiation"]["unresolved_count"] == 0
    db.expire_all()
    assert db.get(Contract, contract.id).stage == "internal_review"
    assert _events(db, contract.id).count("contract_entered_internal_review") == 1


def test_change_response_creates_one_next_round_with_lineage(negotiation_db):
    db, create_case = negotiation_db
    contract, version, _, negotiations = create_case()
    followup = _followup(db, negotiations[0], version.id)
    client = TestClient(app)

    first = client.post(
        f"/api/review/{followup.token}/request-changes",
        json={"general_comment": "Synthetic second-round request"},
    )
    second = client.post(
        f"/api/review/{followup.token}/request-changes",
        json={"general_comment": "Synthetic retry"},
    )

    assert first.status_code == 200, first.text
    assert first.json()["negotiation"]["current_round"] == 2
    assert second.status_code == 409
    assert second.json()["detail"]["error"] == "negotiation_closed"
    db.expire_all()
    rows = db.query(Negotiation).filter_by(contract_id=contract.id).all()
    assert len(rows) == 2
    next_round = next(row for row in rows if row.id != negotiations[0].id)
    assert next_round.workflow_status == "pending_analysis"
    assert next_round.final_summary["lifecycle"]["round_number"] == 2
    assert next_round.final_summary["lifecycle"]["parent_negotiation_id"] == str(negotiations[0].id)
    assert db.get(Contract, contract.id).stage == "negotiation"
    assert _events(db, contract.id).count("negotiation_round_started") == 1


def test_definitive_rejection_closes_items_and_contract(negotiation_db):
    db, create_case = negotiation_db
    contract, version, _, negotiations = create_case(item_count=2)
    followup = _followup(db, negotiations[0], version.id)

    response = TestClient(app).post(
        f"/api/review/{followup.token}/reject",
        json={"reason": "Synthetic definitive rejection"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["contract_stage"] == "rejected"
    db.expire_all()
    rows = db.query(Negotiation).filter_by(contract_id=contract.id).all()
    assert all(row.workflow_status == "closed" for row in rows)
    assert all(row.status == "closed" for row in rows)
    assert all(
        row.final_summary["lifecycle"]["closure_outcome"] == "counterparty_rejected"
        for row in rows
    )
    assert db.get(Contract, contract.id).stage == "rejected"
    assert "negotiation_rejected" in _events(db, contract.id)
    assert "contract_rejected" in _events(db, contract.id)


def test_internal_abandonment_requires_reason_and_cancels(negotiation_db):
    db, create_case = negotiation_db
    contract, _, _, negotiations = create_case(item_count=2)
    client = TestClient(app)
    path = f"/api/negotiations/{negotiations[0].id}/abandon"

    missing = client.post(path, headers=AUTH, json={"reason": ""})
    abandoned = client.post(path, headers=AUTH, json={"reason": "Synthetic internal decision"})

    assert missing.status_code == 422
    assert missing.json()["detail"]["error"] == "negotiation_reason_required"
    assert abandoned.status_code == 200
    assert abandoned.json()["contract_stage"] == "cancelled"
    db.expire_all()
    rows = db.query(Negotiation).filter_by(contract_id=contract.id).all()
    assert all(
        row.final_summary["lifecycle"]["closure_outcome"] == "internally_abandoned"
        for row in rows
    )
    assert db.get(Contract, contract.id).stage == "cancelled"
    assert "negotiation_abandoned" in _events(db, contract.id)
    assert "contract_cancelled" in _events(db, contract.id)


def test_stale_negotiation_cannot_be_edited_or_sent(negotiation_db):
    db, create_case = negotiation_db
    contract, version, _, negotiations = create_case()
    negotiation = negotiations[0]
    negotiation.workflow_status = "edited_by_legal"
    negotiation.lawyer_final_clause = "Synthetic wording"
    version.is_current = False
    replacement = ContractVersion(
        id=uuid4(),
        contract_id=contract.id,
        version_number=2,
        version_label="v2",
        parent_version_id=version.id,
        source="manual_upload",
        status="ready",
        file_path="synthetic/replacement.pdf",
        is_current=True,
        created_by="synthetic-test",
    )
    db.add(replacement)
    db.commit()
    client = TestClient(app)

    edit = client.patch(
        f"/api/negotiations/{negotiation.id}",
        headers=AUTH,
        json={"lawyer_final_clause": "Must not persist"},
    )
    send = client.post(f"/api/negotiations/{negotiation.id}/send", headers=AUTH)

    assert edit.status_code == 409
    assert edit.json()["detail"]["error"] == "workflow_stale"
    assert send.status_code == 409
    assert send.json()["detail"]["error"] == "workflow_stale"
    db.expire_all()
    assert db.get(Negotiation, negotiation.id).lawyer_final_clause == "Synthetic wording"
    assert db.get(Contract, contract.id).stage == "negotiation"
    assert db.query(ReviewRequest).filter_by(contract_id=contract.id).count() == 1


def test_activity_failure_rolls_back_legal_edit(negotiation_db):
    db, create_case = negotiation_db
    _, _, _, negotiations = create_case()
    negotiation = negotiations[0]
    negotiation.workflow_status = "ready"
    negotiation.ai_summary = AI_RESULT["summary"]
    db.commit()

    with patch("app.services.approvals.log_activity", side_effect=RuntimeError("synthetic activity failure")):
        with pytest.raises(RuntimeError, match="synthetic activity failure"):
            negotiation_service.apply_patch(
                negotiation,
                {"lawyer_final_clause": "Must roll back"},
                db,
                actor="legal",
            )

    verify = SessionLocal()
    try:
        stored = verify.get(Negotiation, negotiation.id)
        assert stored.lawyer_final_clause is None
        assert stored.workflow_status == "ready"
    finally:
        verify.close()


def test_followup_failure_rolls_back_version_and_negotiation_send(negotiation_db):
    db, create_case = negotiation_db
    contract, _, _, negotiations = create_case()
    negotiation = negotiations[0]
    negotiation.workflow_status = "edited_by_legal"
    negotiation.status = "approved"
    negotiation.lawyer_final_clause = "Synthetic lawyer-approved wording"
    db.commit()

    with patch(
        "app.services.negotiation.create_review_request",
        side_effect=RuntimeError("synthetic review failure"),
    ):
        with pytest.raises(RuntimeError, match="synthetic review failure"):
            negotiation_service.send_updated(
                negotiation,
                db,
                actor="legal",
            )

    verify = SessionLocal()
    try:
        stored = verify.get(Negotiation, negotiation.id)
        assert stored.status == "approved"
        assert stored.workflow_status == "edited_by_legal"
        assert stored.sent_review_request_id is None
        assert (
            verify.query(ContractVersion)
            .filter_by(contract_id=contract.id)
            .count()
            == 1
        )
        assert (
            verify.query(ReviewRequest)
            .filter_by(contract_id=contract.id)
            .count()
            == 1
        )
    finally:
        verify.close()


def test_serialization_and_workflow_summary_are_canonical(negotiation_db):
    db, create_case = negotiation_db
    contract, version, _, negotiations = create_case()
    negotiation = negotiations[0]

    response = TestClient(app).get(
        f"/api/contracts/{contract.id}/negotiations",
        headers=AUTH,
    )
    contracts = TestClient(app).get(
        "/api/contracts?include=workflow_summary",
        headers=AUTH,
    )

    assert response.status_code == 200
    row = next(item for item in response.json()["negotiations"] if item["id"] == str(negotiation.id))
    assert row["editing_status"] == "draft"
    assert row["workflow_status"] == "pending_analysis"
    assert row["closure_outcome"] is None
    assert row["current_round"] == 1
    assert row["total_rounds"] == 1
    assert row["unresolved_count"] == 1
    assert row["is_stale"] is False
    assert row["actionable"] is True
    assert row["current_version_id"] == str(version.id)
    assert row["contract_stage"] == "negotiation"
    assert "analyze" in row["next_allowed_actions"]

    contract_row = next(item for item in contracts.json() if item["id"] == str(contract.id))
    assert contract_row["workflow_summary"]["negotiation_status"] == "pending_analysis"


def _override(client: TestClient, negotiation_id, *, role="legal", reason="Synthetic authorized override"):
    return client.post(
        f"/api/negotiations/{negotiation_id}/record-agreement",
        headers={**AUTH, "X-Demo-Role": role},
        json={"reason": reason} if reason is not None else {},
    )


def test_internal_agreement_override_forbidden_for_non_legal_executive(negotiation_db):
    _, create_case = negotiation_db
    _, _, _, negotiations = create_case()

    response = _override(TestClient(app), negotiations[0].id, role="business_owner")

    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "negotiation_override_role_required"


def test_internal_agreement_override_requires_reason(negotiation_db):
    _, create_case = negotiation_db
    _, _, _, negotiations = create_case()

    response = _override(TestClient(app), negotiations[0].id, reason="   ")

    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "negotiation_reason_required"


def test_internal_agreement_override_resolves_sole_item_and_transitions_via_lifecycle_service(negotiation_db):
    db, create_case = negotiation_db
    contract, version, review, negotiations = create_case()
    negotiation = negotiations[0]

    response = _override(TestClient(app), negotiation.id, role="legal", reason="Verbal agreement confirmed by phone")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["workflow_status"] == "accepted"
    assert payload["closure_outcome"] == "agreement_reached"
    assert payload["contract_stage"] == "internal_review"
    assert payload["unresolved_count"] == 0

    db.expire_all()
    stored = db.get(Negotiation, negotiation.id)
    assert stored.workflow_status == "accepted"
    assert db.get(Contract, contract.id).stage == "internal_review"

    events = _events(db, contract.id)
    assert "negotiation_agreement_override_used" in events
    assert "negotiation_accepted" in events
    assert "contract_entered_internal_review" in events
    assert "negotiation_closed" in events

    # The transition used the exact same LifecycleService event as the public
    # counterparty-approval path (see apply_followup_review_decision) — this
    # is an alternate audited trigger, not a bypass, and no direct
    # `contract.stage = ...` write occurred outside LifecycleService.
    override_event = (
        db.query(ActivityEvent)
        .filter_by(contract_id=contract.id, event_type="negotiation_agreement_override_used")
        .one()
    )
    assert override_event.event_metadata.get("reason_present") is True
    assert "Verbal agreement confirmed by phone" not in json.dumps(override_event.event_metadata)
    assert override_event.actor == "legal"


def test_internal_agreement_override_allows_executive_role(negotiation_db):
    db, create_case = negotiation_db
    contract, _, _, negotiations = create_case()

    response = _override(TestClient(app), negotiations[0].id, role="executive")

    assert response.status_code == 200, response.text
    db.expire_all()
    assert db.get(Contract, contract.id).stage == "internal_review"


def test_internal_agreement_override_with_other_unresolved_items_keeps_negotiation_stage(negotiation_db):
    db, create_case = negotiation_db
    contract, _, _, negotiations = create_case(item_count=2)

    response = _override(TestClient(app), negotiations[0].id, role="legal")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["contract_stage"] == "negotiation"
    assert payload["unresolved_count"] == 1

    db.expire_all()
    assert db.get(Contract, contract.id).stage == "negotiation"
    assert db.get(Negotiation, negotiations[0].id).workflow_status == "accepted"
    assert db.get(Negotiation, negotiations[1].id).workflow_status == "pending_analysis"


def test_internal_agreement_override_rejects_already_closed_negotiation(negotiation_db):
    db, create_case = negotiation_db
    _, _, _, negotiations = create_case()
    negotiation = negotiations[0]
    negotiation.workflow_status = "accepted"
    negotiation.status = "closed"
    db.commit()

    response = _override(TestClient(app), negotiation.id, role="legal")

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "negotiation_closed"


def test_internal_agreement_override_rejects_stale_version(negotiation_db):
    db, create_case = negotiation_db
    _, version, _, negotiations = create_case()
    negotiation = negotiations[0]
    version.is_current = False
    replacement = ContractVersion(
        id=uuid4(),
        contract_id=negotiation.contract_id,
        version_number=2,
        version_label="v2",
        parent_version_id=version.id,
        source="manual_upload",
        status="ready",
        file_path="synthetic/replacement.pdf",
        is_current=True,
        created_by="synthetic-test",
    )
    db.add(replacement)
    db.commit()

    response = _override(TestClient(app), negotiation.id, role="legal")

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "workflow_stale"


# --- Negotiation bugfix round: unified board + "Adopt AI Recommendation" ---
# See docs/negotiation-flow-bugfix-report.md.


def test_board_excludes_terminal_items_and_buckets_summary_correctly(negotiation_db):
    db, create_case = negotiation_db
    _, _, _, pending = create_case(item_count=1)
    _, _, _, waiting_client = create_case(item_count=1)
    _, _, _, waiting_lawyer = create_case(item_count=1)
    _, _, _, closed = create_case(item_count=1)

    waiting_client[0].workflow_status = "sent_to_client"
    waiting_client[0].sent_at = datetime.now(timezone.utc) - timedelta(days=1)
    waiting_lawyer[0].workflow_status = "ready"
    closed[0].workflow_status = "closed"
    db.commit()

    board = negotiation_service.negotiation_board(db)
    ids = {item["negotiation_id"] for item in board["items"]}

    assert str(pending[0].id) in ids
    assert str(waiting_client[0].id) in ids
    assert str(waiting_lawyer[0].id) in ids
    assert str(closed[0].id) not in ids

    by_id = {item["negotiation_id"]: item for item in board["items"]}
    # "pending_analysis" (the seed default) still counts as awaiting the
    # lawyer's first action — it has no "unassigned" state distinct from that.
    assert by_id[str(pending[0].id)]["waiting_party"] == "lawyer"
    assert by_id[str(waiting_client[0].id)]["waiting_party"] == "client"
    assert by_id[str(waiting_lawyer[0].id)]["waiting_party"] == "lawyer"

    summary = board["summary"]
    assert summary["waiting_client"] >= 1
    assert summary["waiting_lawyer"] >= 2
    assert summary["total_active"] == len(board["items"])


def test_board_message_count_matches_negotiation_messages(negotiation_db):
    db, create_case = negotiation_db
    _, _, review, negotiations = create_case()
    client = TestClient(app)

    with patch.object(negotiation_service, "complete_json", return_value=AI_RESULT):
        _analyze(client, review.id)

    board = negotiation_service.negotiation_board(db)
    item = next(i for i in board["items"] if i["negotiation_id"] == str(negotiations[0].id))
    assert item["message_count"] == 1


def test_board_flags_stale_negotiation_against_current_version(negotiation_db):
    db, create_case = negotiation_db
    contract, version, _, negotiations = create_case()
    negotiation = negotiations[0]
    version.is_current = False
    replacement = ContractVersion(
        id=uuid4(),
        contract_id=contract.id,
        version_number=2,
        version_label="v2",
        parent_version_id=version.id,
        source="manual_upload",
        status="ready",
        file_path="synthetic/replacement.pdf",
        is_current=True,
        created_by="synthetic-test",
    )
    db.add(replacement)
    db.commit()

    board = negotiation_service.negotiation_board(db)
    item = next(i for i in board["items"] if i["negotiation_id"] == str(negotiation.id))
    assert item["is_stale"] is True


def test_board_overdue_sla_from_real_sent_at_and_missed_deadline(negotiation_db):
    db, create_case = negotiation_db
    contract, _, _, negotiations = create_case()
    negotiation = negotiations[0]
    negotiation.workflow_status = "sent_to_client"
    negotiation.sent_at = datetime.now(timezone.utc) - timedelta(days=10)
    db.commit()

    board = negotiation_service.negotiation_board(db)
    item = next(i for i in board["items"] if i["negotiation_id"] == str(negotiation.id))
    assert item["days_waiting"] == 10
    assert item["sla_status"] == "overdue"
    assert board["summary"]["overdue"] >= 1


def test_adopt_ai_recommendation_patch_persists_visible_proposal_fields(negotiation_db):
    """Backs the "Adopt AI Recommendation" button: a single PATCH carrying
    status + lawyer_final_clause(_ar) together, matching the exact shape the
    frontend's adoptAiRecommendation() sends. Confirms the field the user
    sees/edits is what actually gets persisted and approved in one call."""
    db, create_case = negotiation_db
    contract, _, _, negotiations = create_case()
    negotiation = negotiations[0]
    negotiation.workflow_status = "ready"
    negotiation.counter_clause = AI_RESULT["counter_clause"]
    negotiation.counter_clause_ar = AI_RESULT["arabic_counter_clause"]
    db.commit()

    response = TestClient(app).patch(
        f"/api/negotiations/{negotiation.id}",
        headers=AUTH,
        json={
            "status": "approved",
            "lawyer_final_clause": AI_RESULT["counter_clause"],
            "lawyer_final_clause_ar": AI_RESULT["arabic_counter_clause"],
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "approved"
    assert body["lawyer_final_clause"] == AI_RESULT["counter_clause"]
    assert body["lawyer_final_clause_ar"] == AI_RESULT["arabic_counter_clause"]

    db.expire_all()
    stored = db.get(Negotiation, negotiation.id)
    assert stored.status == "approved"
    assert stored.lawyer_final_clause == AI_RESULT["counter_clause"]
    assert stored.lawyer_final_clause_ar == AI_RESULT["arabic_counter_clause"]
    # Adopting does not itself dispatch anything to the client — only /send does.
    assert stored.workflow_status == "edited_by_legal"
    assert stored.sent_at is None
    assert db.get(Contract, contract.id).stage == "negotiation"


def test_adopted_recommendation_can_then_be_sent_as_counterproposal(negotiation_db):
    """End of the Bug 2 flow: after Adopt AI Recommendation persists the
    proposal and flips status to approved, /send must still work exactly as
    before — the adoption did not lose or diverge from what gets sent."""
    db, create_case = negotiation_db
    _, _, _, negotiations = create_case()
    negotiation = negotiations[0]
    negotiation.workflow_status = "ready"
    negotiation.counter_clause = AI_RESULT["counter_clause"]
    negotiation.counter_clause_ar = AI_RESULT["arabic_counter_clause"]
    db.commit()
    client = TestClient(app)

    adopt = client.patch(
        f"/api/negotiations/{negotiation.id}",
        headers=AUTH,
        json={
            "status": "approved",
            "lawyer_final_clause": AI_RESULT["counter_clause"],
            "lawyer_final_clause_ar": AI_RESULT["arabic_counter_clause"],
        },
    )
    assert adopt.status_code == 200, adopt.text

    send = client.post(f"/api/negotiations/{negotiation.id}/send", headers=AUTH)
    assert send.status_code == 200, send.text
    assert send.json()["negotiation"]["lawyer_final_clause"] == AI_RESULT["counter_clause"]
