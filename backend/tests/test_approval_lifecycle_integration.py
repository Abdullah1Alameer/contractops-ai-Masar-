"""Persisted API/database proof for internal approval lifecycle integration."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import (
    ActivityEvent,
    ApprovalStep,
    ApprovalWorkflow,
    Contract,
    ContractVersion,
    Negotiation,
    ReviewRequest,
    SignatureRequest,
)

TOKEN = "Bearer demo-secret-token"
ROLE_SEQUENCE = ["business_owner", "legal", "finance", "executive"]


def auth(role: str = "legal") -> dict:
    return {"Authorization": TOKEN, "X-Demo-Role": role}


@pytest.fixture
def approval_db():
    db = SessionLocal()
    contract_ids = []

    def create_contract(
        *,
        stage: str = "internal_review",
        status: str = "ready",
        with_version: bool = True,
        with_approved_review: bool = True,
    ) -> tuple[Contract, ContractVersion | None]:
        contract = Contract(
            id=uuid4(),
            title="Synthetic approval lifecycle",
            status=status,
            stage=stage,
            supported=True,
            file_url="synthetic/approval-lifecycle.pdf",
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
        if with_approved_review and version is not None:
            db.add(
                ReviewRequest(
                    id=uuid4(),
                    contract_id=contract.id,
                    version_id=version.id,
                    token=f"synthetic-{uuid4().hex}",
                    recipient_name="Synthetic Reviewer",
                    recipient_email="reviewer@example.invalid",
                    status="approved",
                    expires_at=datetime.now(timezone.utc) + timedelta(days=7),
                    responded_at=datetime.now(timezone.utc),
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


def add_negotiation(db, contract, version, *, workflow_status: str = "pending_analysis") -> Negotiation:
    negotiation = Negotiation(
        id=uuid4(),
        contract_id=contract.id,
        version_id=version.id if version else None,
        clause_ref="7.1",
        reviewer_comment="Synthetic redacted comment",
        reviewer_decision="changes_requested",
        status="draft",
        workflow_status=workflow_status,
    )
    db.add(negotiation)
    db.commit()
    return negotiation


def add_signature_request(db, contract, version, *, status: str = "sent") -> SignatureRequest:
    request = SignatureRequest(
        id=uuid4(),
        contract_id=contract.id,
        version_id=version.id if version else None,
        provider="simulated",
        status=status,
        subject="Synthetic signature",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(request)
    db.commit()
    return request


def configure_route(client: TestClient, contract_id, *, role: str = "legal", roles: list[str] | None = None, name: str | None = None):
    steps = [{"role": r} for r in (roles or ROLE_SEQUENCE)]
    return client.put(
        f"/api/contracts/{contract_id}/approval-route",
        headers=auth(role),
        json={"name": name, "steps": steps},
    )


def start_approval(client: TestClient, contract_id, *, role: str = "legal", body: dict | None = None, roles: list[str] | None = None):
    """Configures the (default four-role, unless overridden) route and
    starts the workflow — mirrors the real UI flow (configure, then start).
    Route configuration always uses an admin-eligible role ("legal"),
    independent of `role` (the acting role for the *start*/override call
    itself, which several tests exercise with non-admin roles on purpose).
    Skips (re)configuring when a workflow is already active, exactly like
    the frontend does (it would show the active workflow, not the route
    builder), so a second call correctly surfaces approval_already_active
    from start_workflow itself rather than approval_route_locked from a
    redundant configure attempt."""
    probe = client.get(f"/api/contracts/{contract_id}/approvals", headers=auth(role))
    has_active = (
        probe.status_code == 200
        and probe.json().get("workflow") is not None
        and probe.json()["workflow"]["status"] == "in_progress"
    )
    if not has_active:
        configured = configure_route(client, contract_id, role="legal", roles=roles)
        if configured.status_code != 200:
            return configured
    return client.post(
        f"/api/contracts/{contract_id}/approvals/start",
        headers=auth(role),
        json=body if body is not None else {},
    )


def workflows(db, contract_id) -> list[ApprovalWorkflow]:
    db.expire_all()
    return (
        db.query(ApprovalWorkflow)
        .filter_by(contract_id=contract_id)
        .order_by(ApprovalWorkflow.created_at.asc())
        .all()
    )


def steps(db, workflow_id) -> list[ApprovalStep]:
    db.expire_all()
    return (
        db.query(ApprovalStep)
        .filter_by(workflow_id=workflow_id)
        .order_by(ApprovalStep.step_order.asc())
        .all()
    )


def event_names(db, contract_id) -> list[str]:
    db.expire_all()
    return [
        row.event_type
        for row in db.query(ActivityEvent)
        .filter_by(contract_id=contract_id)
        .order_by(ActivityEvent.created_at.asc(), ActivityEvent.id.asc())
        .all()
    ]


def event_metadata(db, contract_id, event_type: str) -> dict:
    db.expire_all()
    row = (
        db.query(ActivityEvent)
        .filter_by(contract_id=contract_id, event_type=event_type)
        .order_by(ActivityEvent.created_at.desc())
        .first()
    )
    assert row is not None, f"missing activity event {event_type}"
    return row.event_metadata or {}


def test_start_from_internal_review_creates_ordered_locked_steps(approval_db):
    db, create_contract = approval_db
    contract, version = create_contract()

    response = start_approval(TestClient(app), contract.id)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "in_progress"
    assert payload["contract_stage"] == "internal_review"
    assert payload["version_id"] == str(version.id)
    assert payload["current_required_role"] == "business_owner"
    assert payload["completed_step_count"] == 0
    assert payload["total_step_count"] == len(ROLE_SEQUENCE)
    assert payload["stale"] is False
    assert payload["override_used"] is False

    db.refresh(contract)
    assert contract.stage == "internal_review"
    stored = workflows(db, contract.id)
    assert len(stored) == 1
    assert stored[0].version_id == version.id
    persisted_steps = steps(db, stored[0].id)
    assert [step.role for step in persisted_steps] == ROLE_SEQUENCE
    assert [step.status for step in persisted_steps] == ["pending", "locked", "locked", "locked"]
    names = event_names(db, contract.id)
    assert "approval_workflow_started" in names
    assert "contract_entered_internal_review" not in names


def test_start_from_invalid_stage_creates_no_workflow(approval_db):
    db, create_contract = approval_db
    contract, _ = create_contract(stage="client_review")

    response = start_approval(TestClient(app), contract.id)

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "invalid_stage_transition"
    assert workflows(db, contract.id) == []
    db.refresh(contract)
    assert contract.stage == "client_review"


def test_start_without_current_version_is_blocked(approval_db):
    db, create_contract = approval_db
    contract, _ = create_contract(with_version=False)

    response = start_approval(TestClient(app), contract.id)

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "current_version_required"
    assert workflows(db, contract.id) == []


def test_start_without_approval_entry_evidence_is_blocked(approval_db):
    db, create_contract = approval_db
    contract, _ = create_contract(with_approved_review=False)

    response = start_approval(TestClient(app), contract.id)

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "contract_not_ready"
    assert workflows(db, contract.id) == []


def test_start_with_unprocessed_contract_status_is_blocked(approval_db):
    db, create_contract = approval_db
    contract, _ = create_contract(status="processing")

    response = start_approval(TestClient(app), contract.id)

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "contract_not_ready"
    assert workflows(db, contract.id) == []


def test_start_with_unresolved_negotiation_is_blocked(approval_db):
    db, create_contract = approval_db
    contract, version = create_contract()
    negotiation = add_negotiation(db, contract, version)

    response = start_approval(TestClient(app), contract.id)

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["error"] == "unresolved_negotiations"
    assert [item["id"] for item in detail["unresolved"]] == [str(negotiation.id)]
    assert workflows(db, contract.id) == []


def test_start_with_agreed_negotiation_evidence_succeeds(approval_db):
    db, create_contract = approval_db
    contract, version = create_contract(with_approved_review=False)
    negotiation = add_negotiation(db, contract, version, workflow_status="accepted")

    response = start_approval(TestClient(app), contract.id)

    assert response.status_code == 200, response.text
    assert len(workflows(db, contract.id)) == 1
    db.refresh(negotiation)
    assert negotiation.workflow_status == "accepted"


def test_start_with_active_signature_request_is_blocked(approval_db):
    db, create_contract = approval_db
    contract, version = create_contract()
    add_signature_request(db, contract, version)

    response = start_approval(TestClient(app), contract.id)

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "signature_request_active"
    assert workflows(db, contract.id) == []


def test_duplicate_start_returns_approval_already_active(approval_db):
    db, create_contract = approval_db
    contract, _ = create_contract()
    client = TestClient(app)
    assert start_approval(client, contract.id).status_code == 200

    response = start_approval(client, contract.id)

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "approval_already_active"
    assert len(workflows(db, contract.id)) == 1


def test_configure_route_with_unknown_approver_role_is_rejected(approval_db):
    # Superseded: "approver_names" no longer exists on /approvals/start —
    # role validation now happens when the route is configured, not when
    # a fixed sequence is (no longer) resolved at start time.
    db, create_contract = approval_db
    contract, _ = create_contract()

    response = configure_route(TestClient(app), contract.id, roles=["chief_pirate"])

    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "invalid_approver"
    assert workflows(db, contract.id) == []


def test_legacy_force_flag_is_rejected_without_structured_override(approval_db):
    db, create_contract = approval_db
    contract, version = create_contract()
    add_negotiation(db, contract, version)

    response = start_approval(TestClient(app), contract.id, body={"force": True})

    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "approval_reason_required"
    assert workflows(db, contract.id) == []


def decide(client: TestClient, step_id, *, role: str, status: str, comment: str | None = None):
    body: dict = {"status": status}
    if comment is not None:
        body["comment"] = comment
    return client.patch(f"/api/approvals/{step_id}", headers=auth(role), json=body)


def step_ids(db, contract_id) -> dict[str, str]:
    workflow = workflows(db, contract_id)[-1]
    return {step.role: str(step.id) for step in steps(db, workflow.id)}


def approve_until(client, db, contract_id, *, last_role: str) -> None:
    ids = step_ids(db, contract_id)
    for role in ROLE_SEQUENCE:
        response = decide(client, ids[role], role=role, status="approved")
        assert response.status_code == 200, response.text
        if role == last_role:
            return


def test_intermediate_approval_unlocks_only_the_next_step(approval_db):
    db, create_contract = approval_db
    contract, _ = create_contract()
    client = TestClient(app)
    assert start_approval(client, contract.id).status_code == 200
    ids = step_ids(db, contract.id)

    response = decide(client, ids["business_owner"], role="business_owner", status="approved")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "in_progress"
    assert payload["contract_stage"] == "internal_review"
    assert payload["current_required_role"] == "legal"
    assert payload["completed_step_count"] == 1

    db.refresh(contract)
    assert contract.stage == "internal_review"
    workflow = workflows(db, contract.id)[0]
    assert [step.status for step in steps(db, workflow.id)] == [
        "approved",
        "pending",
        "locked",
        "locked",
    ]
    names = event_names(db, contract.id)
    assert "approval_step_approved" in names
    assert "contract_ready_to_sign" not in names


def test_out_of_order_decision_is_rejected(approval_db):
    db, create_contract = approval_db
    contract, _ = create_contract()
    client = TestClient(app)
    assert start_approval(client, contract.id).status_code == 200
    ids = step_ids(db, contract.id)

    response = decide(client, ids["legal"], role="legal", status="approved")

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "approval_out_of_order"
    workflow = workflows(db, contract.id)[0]
    assert [step.status for step in steps(db, workflow.id)] == [
        "pending",
        "locked",
        "locked",
        "locked",
    ]


def test_wrong_role_decision_is_forbidden(approval_db):
    db, create_contract = approval_db
    contract, _ = create_contract()
    client = TestClient(app)
    assert start_approval(client, contract.id).status_code == 200
    ids = step_ids(db, contract.id)

    response = decide(client, ids["business_owner"], role="legal", status="approved")

    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "approval_role_required"
    workflow = workflows(db, contract.id)[0]
    assert steps(db, workflow.id)[0].status == "pending"


def test_repeated_decision_on_closed_step_conflicts(approval_db):
    db, create_contract = approval_db
    contract, _ = create_contract()
    client = TestClient(app)
    assert start_approval(client, contract.id).status_code == 200
    ids = step_ids(db, contract.id)
    assert decide(client, ids["business_owner"], role="business_owner", status="approved").status_code == 200

    response = decide(client, ids["business_owner"], role="business_owner", status="approved")

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "approval_step_closed"


def test_final_approval_marks_version_and_moves_to_ready_to_sign(approval_db):
    db, create_contract = approval_db
    contract, version = create_contract()
    client = TestClient(app)
    assert start_approval(client, contract.id).status_code == 200
    ids = step_ids(db, contract.id)

    last = None
    for role in ROLE_SEQUENCE:
        last = decide(client, ids[role], role=role, status="approved")
        assert last.status_code == 200, last.text

    payload = last.json()
    assert payload["status"] == "approved"
    assert payload["contract_stage"] == "ready_to_sign"
    assert payload["completed_step_count"] == len(ROLE_SEQUENCE)
    assert payload["actionable"] is False
    assert payload["next_allowed_actions"] == []

    db.refresh(contract)
    db.refresh(version)
    workflow = workflows(db, contract.id)[0]
    assert contract.stage == "ready_to_sign"
    assert workflow.status == "approved"
    assert workflow.completed_at is not None
    assert version.status == "approved"
    assert version.approval_workflow_id == workflow.id
    assert [step.status for step in steps(db, workflow.id)] == ["approved"] * len(ROLE_SEQUENCE)

    names = event_names(db, contract.id)
    for expected in (
        "approval_workflow_started",
        "approval_step_approved",
        "approval_workflow_completed",
        "version_approved",
        "contract_ready_to_sign",
    ):
        assert expected in names, expected
    assert db.query(SignatureRequest).filter_by(contract_id=contract.id).count() == 0

    readback = client.get(f"/api/contracts/{contract.id}/approvals", headers=auth())
    assert readback.status_code == 200
    assert readback.json()["workflow"]["status"] == "approved"
    assert readback.json()["workflow"]["contract_stage"] == "ready_to_sign"


def test_final_approval_blocked_by_active_signature_request(approval_db):
    db, create_contract = approval_db
    contract, version = create_contract()
    client = TestClient(app)
    assert start_approval(client, contract.id).status_code == 200
    approve_until(client, db, contract.id, last_role="finance")
    add_signature_request(db, contract, version)
    ids = step_ids(db, contract.id)

    response = decide(client, ids["executive"], role="executive", status="approved")

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "signature_request_active"
    db.refresh(contract)
    workflow = workflows(db, contract.id)[0]
    assert contract.stage == "internal_review"
    assert workflow.status == "in_progress"
    assert steps(db, workflow.id)[3].status == "pending"


def test_final_approval_blocked_by_new_unresolved_negotiation(approval_db):
    db, create_contract = approval_db
    contract, version = create_contract()
    client = TestClient(app)
    assert start_approval(client, contract.id).status_code == 200
    approve_until(client, db, contract.id, last_role="finance")
    add_negotiation(db, contract, version)
    ids = step_ids(db, contract.id)

    response = decide(client, ids["executive"], role="executive", status="approved")

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "unresolved_negotiations"
    db.refresh(contract)
    assert contract.stage == "internal_review"
    assert workflows(db, contract.id)[0].status == "in_progress"


def test_request_changes_creates_exactly_one_negotiation_seed(approval_db):
    db, create_contract = approval_db
    contract, version = create_contract()
    client = TestClient(app)
    assert start_approval(client, contract.id).status_code == 200
    ids = step_ids(db, contract.id)

    response = decide(
        client,
        ids["business_owner"],
        role="business_owner",
        status="changes_requested",
        comment="Synthetic redacted change request",
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "changes_requested"
    assert payload["contract_stage"] == "negotiation"
    assert payload["actionable"] is False

    db.refresh(contract)
    assert contract.stage == "negotiation"
    workflow = workflows(db, contract.id)[0]
    assert [step.status for step in steps(db, workflow.id)] == [
        "changes_requested",
        "locked",
        "locked",
        "locked",
    ]

    seeds = db.query(Negotiation).filter_by(contract_id=contract.id).all()
    assert len(seeds) == 1
    lifecycle = (seeds[0].final_summary or {})["lifecycle"]
    assert lifecycle["origin"] == "internal_approval"
    assert lifecycle["approval_workflow_id"] == str(workflow.id)
    assert seeds[0].version_id == version.id
    assert seeds[0].workflow_status == "pending_analysis"

    names = event_names(db, contract.id)
    for expected in (
        "approval_changes_requested",
        "contract_entered_negotiation",
        "negotiation_analysis_requested",
    ):
        assert expected in names, expected
    changes_metadata = event_metadata(db, contract.id, "approval_changes_requested")
    assert changes_metadata["reason_present"] is True
    assert "Synthetic redacted change request" not in str(changes_metadata)


def test_request_changes_requires_a_reason(approval_db):
    db, create_contract = approval_db
    contract, _ = create_contract()
    client = TestClient(app)
    assert start_approval(client, contract.id).status_code == 200
    ids = step_ids(db, contract.id)

    response = decide(client, ids["business_owner"], role="business_owner", status="changes_requested")

    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "approval_reason_required"
    db.refresh(contract)
    assert contract.stage == "internal_review"
    assert db.query(Negotiation).filter_by(contract_id=contract.id).count() == 0


def test_rejection_is_terminal_and_creates_no_negotiation(approval_db):
    db, create_contract = approval_db
    contract, _ = create_contract()
    client = TestClient(app)
    assert start_approval(client, contract.id).status_code == 200
    ids = step_ids(db, contract.id)

    response = decide(
        client,
        ids["business_owner"],
        role="business_owner",
        status="rejected",
        comment="Synthetic redacted rejection",
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "rejected"
    assert response.json()["contract_stage"] == "rejected"

    db.refresh(contract)
    assert contract.stage == "rejected"
    workflow = workflows(db, contract.id)[0]
    assert workflow.status == "rejected"
    assert [step.status for step in steps(db, workflow.id)] == [
        "rejected",
        "locked",
        "locked",
        "locked",
    ]
    assert db.query(Negotiation).filter_by(contract_id=contract.id).count() == 0
    names = event_names(db, contract.id)
    for expected in ("approval_step_rejected", "approval_rejected", "contract_rejected"):
        assert expected in names, expected

    duplicate = decide(
        client,
        ids["business_owner"],
        role="business_owner",
        status="rejected",
        comment="Synthetic redacted rejection",
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["error"] == "approval_step_closed"


def test_cancel_keeps_internal_review_and_allows_restart(approval_db):
    db, create_contract = approval_db
    contract, _ = create_contract()
    client = TestClient(app)
    assert start_approval(client, contract.id).status_code == 200

    response = client.post(
        f"/api/contracts/{contract.id}/approvals/cancel",
        headers=auth(),
        json={"reason": "Synthetic redacted cancellation"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "cancelled"
    assert response.json()["contract_stage"] == "internal_review"

    db.refresh(contract)
    assert contract.stage == "internal_review"
    workflow = workflows(db, contract.id)[0]
    assert workflow.status == "cancelled"
    assert all(step.status == "locked" for step in steps(db, workflow.id))
    names = event_names(db, contract.id)
    assert "approval_workflow_cancelled" in names
    assert "contract_entered_negotiation" not in names

    assert start_approval(client, contract.id).status_code == 200
    assert len(workflows(db, contract.id)) == 2


def test_cancel_requires_reason_and_active_workflow(approval_db):
    db, create_contract = approval_db
    contract, _ = create_contract()
    client = TestClient(app)

    missing_workflow = client.post(
        f"/api/contracts/{contract.id}/approvals/cancel",
        headers=auth(),
        json={"reason": "Synthetic redacted cancellation"},
    )
    assert missing_workflow.status_code == 404
    assert missing_workflow.json()["detail"]["error"] == "approval_workflow_not_found"

    assert start_approval(client, contract.id).status_code == 200
    missing_reason = client.post(
        f"/api/contracts/{contract.id}/approvals/cancel",
        headers=auth(),
        json={},
    )

    assert missing_reason.status_code == 422
    assert missing_reason.json()["detail"]["error"] == "approval_reason_required"
    assert workflows(db, contract.id)[0].status == "in_progress"


def test_stale_workflow_decision_is_rejected_without_mutation(approval_db):
    db, create_contract = approval_db
    contract, version = create_contract()
    client = TestClient(app)
    assert start_approval(client, contract.id).status_code == 200
    ids = step_ids(db, contract.id)

    version.is_current = False
    db.add(
        ContractVersion(
            id=uuid4(),
            contract_id=contract.id,
            version_number=2,
            version_label="v2",
            source="internal_revision",
            status="ready",
            file_path=contract.file_url,
            is_current=True,
            created_by="synthetic-test",
        )
    )
    db.commit()

    response = decide(client, ids["business_owner"], role="business_owner", status="approved")

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "workflow_stale"
    db.refresh(contract)
    workflow = workflows(db, contract.id)[0]
    assert contract.stage == "internal_review"
    assert workflow.status == "in_progress"
    assert steps(db, workflow.id)[0].status == "pending"
    assert "approval_step_approved" not in event_names(db, contract.id)


def test_activity_failure_rolls_back_step_workflow_and_stage(approval_db):
    db, create_contract = approval_db
    contract, version = create_contract()
    client = TestClient(app)
    assert start_approval(client, contract.id).status_code == 200
    approve_until(client, db, contract.id, last_role="finance")
    ids = step_ids(db, contract.id)

    with patch(
        "app.services.approvals.log_activity",
        side_effect=RuntimeError("synthetic activity failure"),
    ):
        with pytest.raises(RuntimeError):
            decide(client, ids["executive"], role="executive", status="approved")

    verify = SessionLocal()
    try:
        stored_contract = verify.get(Contract, contract.id)
        stored_version = verify.get(ContractVersion, version.id)
        workflow = (
            verify.query(ApprovalWorkflow).filter_by(contract_id=contract.id).one()
        )
        final_step = (
            verify.query(ApprovalStep)
            .filter_by(workflow_id=workflow.id, step_order=4)
            .one()
        )
        assert stored_contract.stage == "internal_review"
        assert stored_version.status != "approved"
        assert workflow.status == "in_progress"
        assert workflow.current_step_order == 4
        assert final_step.status == "pending"
        assert (
            verify.query(ActivityEvent)
            .filter_by(contract_id=contract.id, event_type="approval_workflow_completed")
            .count()
            == 0
        )
    finally:
        verify.close()


def override_body(negotiations, *, reason: str = "Synthetic redacted override", rules=None) -> dict:
    payload = {
        "override": {
            "reason": reason,
            "negotiation_ids": [str(item.id) for item in negotiations],
        }
    }
    if rules is not None:
        payload["override"]["rules"] = rules
    return payload


def test_override_requires_legal_or_executive_role(approval_db):
    db, create_contract = approval_db
    contract, version = create_contract()
    negotiation = add_negotiation(db, contract, version)

    response = start_approval(
        TestClient(app),
        contract.id,
        role="finance",
        body=override_body([negotiation]),
    )

    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "approval_role_required"
    assert workflows(db, contract.id) == []
    db.refresh(negotiation)
    assert negotiation.workflow_status == "pending_analysis"


def test_override_requires_a_reason(approval_db):
    db, create_contract = approval_db
    contract, version = create_contract()
    negotiation = add_negotiation(db, contract, version)

    response = start_approval(
        TestClient(app),
        contract.id,
        body={"override": {"negotiation_ids": [str(negotiation.id)]}},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "approval_reason_required"
    assert workflows(db, contract.id) == []


def test_override_must_list_every_blocking_negotiation(approval_db):
    db, create_contract = approval_db
    contract, version = create_contract()
    listed = add_negotiation(db, contract, version)
    unlisted = add_negotiation(db, contract, version)

    response = start_approval(TestClient(app), contract.id, body=override_body([listed]))

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["error"] == "unresolved_negotiations"
    assert [item["id"] for item in detail["unresolved"]] == [str(unlisted.id)]
    assert workflows(db, contract.id) == []


def test_override_rejects_rules_that_are_not_overridable(approval_db):
    db, create_contract = approval_db
    contract, version = create_contract()
    negotiation = add_negotiation(db, contract, version)

    response = start_approval(
        TestClient(app),
        contract.id,
        body=override_body([negotiation], rules=["workflow_stale"]),
    )

    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "forbidden_transition"
    assert workflows(db, contract.id) == []


def test_valid_legal_override_is_audited_and_keeps_every_step(approval_db):
    db, create_contract = approval_db
    contract, version = create_contract()
    negotiation = add_negotiation(db, contract, version)

    response = start_approval(TestClient(app), contract.id, body=override_body([negotiation]))

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "in_progress"
    assert payload["override_used"] is True
    assert payload["total_step_count"] == len(ROLE_SEQUENCE)
    assert payload["current_required_role"] == "business_owner"

    workflow = workflows(db, contract.id)[0]
    assert [step.status for step in steps(db, workflow.id)] == [
        "pending",
        "locked",
        "locked",
        "locked",
    ]
    db.refresh(negotiation)
    assert negotiation.workflow_status == "closed"
    lifecycle = (negotiation.final_summary or {})["lifecycle"]
    assert lifecycle["closure_outcome"] == "approval_overridden"
    assert lifecycle["override_reason"] == "Synthetic redacted override"

    metadata = event_metadata(db, contract.id, "approval_override_used")
    assert metadata["overridden_negotiation_ids"] == [str(negotiation.id)]
    assert metadata["overridden_rules"] == ["unresolved_negotiations"]
    assert metadata["role"] == "legal"
    assert metadata["reason_present"] is True
    assert metadata["reason_hash"]
    assert metadata["timestamp"]
    assert "Synthetic redacted override" not in str(metadata)


def test_overridden_negotiation_no_longer_blocks_final_approval(approval_db):
    db, create_contract = approval_db
    contract, version = create_contract()
    negotiation = add_negotiation(db, contract, version)
    client = TestClient(app)
    assert start_approval(client, contract.id, body=override_body([negotiation])).status_code == 200

    ids = step_ids(db, contract.id)
    for role in ROLE_SEQUENCE:
        assert decide(client, ids[role], role=role, status="approved").status_code == 200

    db.refresh(contract)
    assert contract.stage == "ready_to_sign"


def test_override_cannot_bypass_missing_current_version(approval_db):
    db, create_contract = approval_db
    contract, _ = create_contract(with_version=False)

    response = start_approval(
        TestClient(app),
        contract.id,
        body={"override": {"reason": "Synthetic redacted override", "negotiation_ids": []}},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "current_version_required"
    assert workflows(db, contract.id) == []


def test_override_cannot_bypass_active_signature_request(approval_db):
    db, create_contract = approval_db
    contract, version = create_contract()
    negotiation = add_negotiation(db, contract, version)
    add_signature_request(db, contract, version)

    response = start_approval(TestClient(app), contract.id, body=override_body([negotiation]))

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "signature_request_active"
    assert workflows(db, contract.id) == []
    db.refresh(negotiation)
    assert negotiation.workflow_status == "pending_analysis"


def test_override_cannot_bypass_terminal_stage(approval_db):
    db, create_contract = approval_db
    contract, version = create_contract(stage="rejected")
    negotiation = add_negotiation(db, contract, version)

    response = start_approval(TestClient(app), contract.id, body=override_body([negotiation]))

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "invalid_stage_transition"
    assert workflows(db, contract.id) == []


def test_workflow_summary_reports_canonical_approval_state(approval_db):
    db, create_contract = approval_db
    contract, _ = create_contract()
    client = TestClient(app)
    assert start_approval(client, contract.id).status_code == 200

    in_progress = client.get("/api/contracts?include=workflow_summary", headers=auth())
    row = next(item for item in in_progress.json() if item["id"] == str(contract.id))
    assert row["stage"] == "internal_review"
    assert row["workflow_summary"]["approval_status"] == "in_progress"

    ids = step_ids(db, contract.id)
    for role in ROLE_SEQUENCE:
        assert decide(client, ids[role], role=role, status="approved").status_code == 200

    approved = client.get("/api/contracts?include=workflow_summary", headers=auth())
    row = next(item for item in approved.json() if item["id"] == str(contract.id))
    assert row["stage"] == "ready_to_sign"
    assert row["workflow_summary"]["approval_status"] == "approved"
