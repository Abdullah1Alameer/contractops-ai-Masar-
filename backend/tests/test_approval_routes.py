"""Configurable approval routes and reusable route templates — see
docs/configurable-approval-routes-report.md."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import (
    ApprovalRoute,
    ApprovalStep,
    ApprovalWorkflow,
    Contract,
    ContractApprovalRoute,
    ContractVersion,
    ReviewRequest,
)

AUTH_LEGAL = {"Authorization": "Bearer demo-secret-token", "X-Demo-Role": "legal"}
AUTH_EXEC = {"Authorization": "Bearer demo-secret-token", "X-Demo-Role": "executive"}
AUTH_SALES = {"Authorization": "Bearer demo-secret-token", "X-Demo-Role": "sales"}
AUTH_FINANCE = {"Authorization": "Bearer demo-secret-token", "X-Demo-Role": "finance"}


@pytest.fixture
def route_db():
    db = SessionLocal()
    contract_ids: list = []
    route_ids: list = []

    def create_contract(*, stage: str = "internal_review", with_version: bool = True) -> tuple[Contract, ContractVersion | None]:
        contract = Contract(
            id=uuid4(), title="Synthetic approval route", status="ready", stage=stage,
            supported=True, file_url="synthetic/approval-route.pdf",
        )
        db.add(contract)
        version = None
        if with_version:
            version = ContractVersion(
                id=uuid4(), contract_id=contract.id, version_number=1, version_label="v1",
                source="initial_upload", status="ready", file_path=contract.file_url,
                is_current=True, created_by="synthetic-test",
            )
            db.add(version)
            db.add(
                ReviewRequest(
                    id=uuid4(), contract_id=contract.id, version_id=version.id,
                    token=f"synthetic-{uuid4().hex}", recipient_name="Synthetic Reviewer",
                    recipient_email="reviewer@example.invalid", status="approved",
                    expires_at=datetime.now(timezone.utc) + timedelta(days=7),
                    responded_at=datetime.now(timezone.utc),
                )
            )
        db.commit()
        contract_ids.append(contract.id)
        return contract, version

    yield db, create_contract, route_ids

    db.rollback()
    for contract_id in contract_ids:
        contract = db.get(Contract, contract_id)
        if contract is not None:
            db.delete(contract)
    db.commit()
    for route_id in route_ids:
        route = db.get(ApprovalRoute, route_id)
        if route is not None:
            db.delete(route)
    db.commit()
    db.close()


def configure(client, contract_id, *, headers=AUTH_LEGAL, steps, name=None, source_route_id=None, save_as_route=False, save_as_route_name=None):
    return client.put(
        f"/api/contracts/{contract_id}/approval-route",
        headers=headers,
        json={
            "name": name, "steps": steps, "source_route_id": source_route_id,
            "save_as_route": save_as_route, "save_as_route_name": save_as_route_name,
        },
    )


def start(client, contract_id, *, headers=AUTH_LEGAL):
    return client.post(f"/api/contracts/{contract_id}/approvals/start", headers=headers, json={})


def approve(client, step_id, *, headers):
    return client.patch(f"/api/approvals/{step_id}", headers=headers, json={"status": "approved"})


def workflow_steps(db, contract_id) -> list[ApprovalStep]:
    db.expire_all()
    wf = (
        db.query(ApprovalWorkflow)
        .filter_by(contract_id=contract_id)
        .order_by(ApprovalWorkflow.created_at.desc())
        .first()
    )
    if wf is None:
        return []
    return (
        db.query(ApprovalStep)
        .filter_by(workflow_id=wf.id)
        .order_by(ApprovalStep.step_order.asc())
        .all()
    )


# 1. Internal review contract can configure a one-step Executive route.
def test_one_step_executive_route(route_db):
    db, create_contract, _ = route_db
    contract, _ = create_contract()
    client = TestClient(app)

    response = configure(client, contract.id, steps=[{"role": "executive"}], name="Fast Executive Approval")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "draft"
    assert [s["role"] for s in body["steps"]] == ["executive"]

    started = start(client, contract.id)
    assert started.status_code == 200, started.text
    assert started.json()["total_step_count"] == 1
    assert started.json()["current_required_role"] == "executive"


# 2. Legal -> Sales -> Executive route preserves order.
def test_legal_sales_executive_order_preserved(route_db):
    db, create_contract, _ = route_db
    contract, _ = create_contract()
    client = TestClient(app)

    configure(client, contract.id, steps=[{"role": "legal"}, {"role": "sales"}, {"role": "executive"}])
    started = start(client, contract.id)
    assert started.status_code == 200, started.text

    persisted = workflow_steps(db, contract.id)
    assert [s.role for s in persisted] == ["legal", "sales", "executive"]
    assert [s.step_order for s in persisted] == [1, 2, 3]

    ids = {s.role: str(s.id) for s in persisted}
    assert approve(client, ids["legal"], headers=AUTH_LEGAL).status_code == 200
    assert approve(client, ids["sales"], headers=AUTH_SALES).status_code == 200
    final = approve(client, ids["executive"], headers=AUTH_EXEC)
    assert final.status_code == 200, final.text
    assert final.json()["contract_stage"] == "ready_to_sign"


# 3. Existing four-role route can be saved and reused.
def test_four_role_route_saved_and_reused(route_db):
    db, create_contract, route_ids = route_db
    contract, _ = create_contract()
    client = TestClient(app)
    steps = [{"role": r} for r in ("business_owner", "legal", "finance", "executive")]

    saved = client.post(
        "/api/approval-routes", headers=AUTH_LEGAL, json={"name": "Legacy Four Role", "steps": steps}
    )
    assert saved.status_code == 201, saved.text
    route_id = saved.json()["id"]
    route_ids.append(route_id)

    configure(client, contract.id, steps=steps, source_route_id=route_id)
    started = start(client, contract.id)
    assert started.status_code == 200, started.text
    assert started.json()["total_step_count"] == 4

    db.expire_all()
    route = db.query(ContractApprovalRoute).filter_by(contract_id=contract.id).first()
    assert str(route.source_route_id) == route_id


# 4. Empty route is rejected.
def test_empty_route_is_rejected(route_db):
    db, create_contract, _ = route_db
    contract, _ = create_contract()
    client = TestClient(app)

    response = client.put(
        f"/api/contracts/{contract.id}/approval-route", headers=AUTH_LEGAL, json={"steps": []}
    )

    assert response.status_code == 422
    # Pydantic's min_length=1 rejects before the service layer even runs —
    # still a 422, consistent with approval_steps_required semantics.


# 5. Duplicate approver is rejected.
def test_duplicate_approver_is_rejected(route_db):
    db, create_contract, _ = route_db
    contract, _ = create_contract()
    client = TestClient(app)

    response = configure(client, contract.id, steps=[{"role": "legal"}, {"role": "legal"}])

    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "duplicate_approver"


def test_duplicate_role_with_distinct_named_approvers_is_allowed(route_db):
    """"unless explicitly supported" — two legal steps are fine if they're
    pinned to two different named individuals."""
    db, create_contract, _ = route_db
    contract, _ = create_contract()
    client = TestClient(app)

    response = configure(
        client, contract.id,
        steps=[
            {"role": "legal", "approver_name": "Fatima Al-Otaibi"},
            {"role": "legal", "approver_name": "Yusuf Al-Harbi"},
        ],
    )

    assert response.status_code == 200, response.text
    assert len(response.json()["steps"]) == 2


# 6. Unauthorized user cannot configure a route.
def test_unauthorized_role_cannot_configure_route(route_db):
    db, create_contract, _ = route_db
    contract, _ = create_contract()
    client = TestClient(app)

    response = configure(client, contract.id, headers=AUTH_FINANCE, steps=[{"role": "executive"}])

    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "approval_route_role_required"


# 7. Selected saved route is copied into contract-specific steps.
def test_saved_route_copied_into_contract_specific_steps(route_db):
    db, create_contract, route_ids = route_db
    contract, _ = create_contract()
    client = TestClient(app)
    steps = [{"role": "legal"}, {"role": "executive"}]

    saved = client.post("/api/approval-routes", headers=AUTH_LEGAL, json={"name": "Legal + Executive", "steps": steps})
    route_id = saved.json()["id"]
    route_ids.append(route_id)

    configure(client, contract.id, steps=steps, source_route_id=route_id, name="Legal + Executive")

    db.expire_all()
    contract_route = db.query(ContractApprovalRoute).filter_by(contract_id=contract.id).first()
    assert str(contract_route.source_route_id) == route_id
    assert contract_route.id != route_id  # a real, independent copy — not a shared reference


# 8. Editing a saved route does not mutate a started workflow.
def test_editing_saved_route_does_not_mutate_started_workflow(route_db):
    db, create_contract, route_ids = route_db
    contract, _ = create_contract()
    client = TestClient(app)
    original_steps = [{"role": "legal"}, {"role": "executive"}]

    saved = client.post("/api/approval-routes", headers=AUTH_LEGAL, json={"name": "High-Value Contract Route", "steps": original_steps})
    route_id = saved.json()["id"]
    route_ids.append(route_id)

    configure(client, contract.id, steps=original_steps, source_route_id=route_id)
    started = start(client, contract.id)
    assert started.status_code == 200, started.text

    edited = client.put(
        f"/api/approval-routes/{route_id}", headers=AUTH_LEGAL,
        json={"steps": [{"role": "finance"}, {"role": "sales"}, {"role": "executive"}]},
    )
    assert edited.status_code == 200, edited.text
    assert [s["role"] for s in edited.json()["steps"]] == ["finance", "sales", "executive"]

    persisted = workflow_steps(db, contract.id)
    assert [s.role for s in persisted] == ["legal", "executive"]  # unchanged


# 9. Workflow remains in internal_review while steps are pending.
def test_workflow_remains_in_internal_review_while_pending(route_db):
    db, create_contract, _ = route_db
    contract, _ = create_contract()
    client = TestClient(app)
    configure(client, contract.id, steps=[{"role": "legal"}, {"role": "executive"}])
    started = start(client, contract.id)
    assert started.status_code == 200, started.text
    assert started.json()["contract_stage"] == "internal_review"

    db.expire_all()
    assert db.get(Contract, contract.id).stage == "internal_review"


# 10. Out-of-order approval is blocked.
def test_out_of_order_approval_is_blocked(route_db):
    db, create_contract, _ = route_db
    contract, _ = create_contract()
    client = TestClient(app)
    configure(client, contract.id, steps=[{"role": "legal"}, {"role": "sales"}, {"role": "executive"}])
    start(client, contract.id)
    ids = {s.role: str(s.id) for s in workflow_steps(db, contract.id)}

    response = approve(client, ids["sales"], headers=AUTH_SALES)

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "approval_out_of_order"


# 11. Final configured approver moves contract to ready_to_sign.
def test_final_configured_approver_moves_to_ready_to_sign(route_db):
    db, create_contract, _ = route_db
    contract, version = create_contract()
    client = TestClient(app)
    configure(client, contract.id, steps=[{"role": "sales"}, {"role": "manager"}])
    start(client, contract.id)
    ids = {s.role: str(s.id) for s in workflow_steps(db, contract.id)}

    assert approve(client, ids["sales"], headers=AUTH_SALES).status_code == 200
    final = approve(client, ids["manager"], headers={"Authorization": "Bearer demo-secret-token", "X-Demo-Role": "manager"})

    assert final.status_code == 200, final.text
    assert final.json()["contract_stage"] == "ready_to_sign"
    db.expire_all()
    assert db.get(Contract, contract.id).stage == "ready_to_sign"


# 12. Route cannot be edited after approval starts.
def test_route_cannot_be_edited_after_start(route_db):
    db, create_contract, _ = route_db
    contract, _ = create_contract()
    client = TestClient(app)
    configure(client, contract.id, steps=[{"role": "legal"}, {"role": "executive"}])
    start(client, contract.id)

    response = configure(client, contract.id, steps=[{"role": "executive"}])

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "approval_route_locked"


# 13. Cancel with reason preserves audit history.
def test_cancel_with_reason_preserves_audit_history(route_db):
    db, create_contract, _ = route_db
    contract, _ = create_contract()
    client = TestClient(app)
    configure(client, contract.id, steps=[{"role": "legal"}, {"role": "executive"}], name="Two Step")
    start(client, contract.id)

    cancelled = client.post(
        f"/api/contracts/{contract.id}/approvals/cancel", headers=AUTH_LEGAL,
        json={"reason": "Synthetic redacted route change"},
    )
    assert cancelled.status_code == 200, cancelled.text

    db.expire_all()
    old_steps = workflow_steps(db, contract.id)
    assert [s.status for s in old_steps] == ["locked", "locked"]
    assert [s.role for s in old_steps] == ["legal", "executive"]  # untouched, not deleted


# 14. Restart creates a new workflow and steps.
def test_restart_creates_new_workflow_and_steps(route_db):
    db, create_contract, _ = route_db
    contract, _ = create_contract()
    client = TestClient(app)
    configure(client, contract.id, steps=[{"role": "legal"}, {"role": "executive"}])
    start(client, contract.id)
    client.post(f"/api/contracts/{contract.id}/approvals/cancel", headers=AUTH_LEGAL, json={"reason": "Synthetic redacted restart"})

    configure(client, contract.id, steps=[{"role": "sales"}, {"role": "manager"}, {"role": "executive"}])
    restarted = start(client, contract.id)

    assert restarted.status_code == 200, restarted.text
    db.expire_all()
    all_workflows = db.query(ApprovalWorkflow).filter_by(contract_id=contract.id).order_by(ApprovalWorkflow.created_at.asc()).all()
    assert len(all_workflows) == 2
    assert all_workflows[0].status == "cancelled"
    assert all_workflows[1].status == "in_progress"
    new_steps = (
        db.query(ApprovalStep).filter_by(workflow_id=all_workflows[1].id).order_by(ApprovalStep.step_order.asc()).all()
    )
    assert [s.role for s in new_steps] == ["sales", "manager", "executive"]


def test_active_workflow_blocks_reconfigure_with_locked_not_active(route_db):
    """approval_already_active is for the START call; approval_route_locked
    is for attempting to edit configuration while a workflow is running."""
    db, create_contract, _ = route_db
    contract, _ = create_contract()
    client = TestClient(app)
    configure(client, contract.id, steps=[{"role": "executive"}])
    start(client, contract.id)

    reconfigure = configure(client, contract.id, steps=[{"role": "legal"}])
    restart = start(client, contract.id)

    assert reconfigure.status_code == 409 and reconfigure.json()["detail"]["error"] == "approval_route_locked"
    assert restart.status_code == 409 and restart.json()["detail"]["error"] == "approval_already_active"


def test_start_without_configured_route_is_rejected(route_db):
    db, create_contract, _ = route_db
    contract, _ = create_contract()
    client = TestClient(app)

    response = start(client, contract.id)

    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "approval_route_required"


def test_invalid_approver_role_is_rejected(route_db):
    db, create_contract, _ = route_db
    contract, _ = create_contract()
    client = TestClient(app)

    response = configure(client, contract.id, steps=[{"role": "chief_pirate"}])

    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "invalid_approver"


def test_list_and_archive_saved_routes(route_db):
    db, create_contract, route_ids = route_db
    client = TestClient(app)

    saved = client.post(
        "/api/approval-routes", headers=AUTH_LEGAL,
        json={"name": "Standard Commercial", "steps": [{"role": "legal"}, {"role": "sales"}, {"role": "executive"}]},
    )
    assert saved.status_code == 201, saved.text
    route_id = saved.json()["id"]
    route_ids.append(route_id)

    listed = client.get("/api/approval-routes", headers=AUTH_LEGAL)
    assert listed.status_code == 200
    assert any(r["id"] == route_id for r in listed.json()["routes"])

    archived = client.post(f"/api/approval-routes/{route_id}/archive", headers=AUTH_LEGAL)
    assert archived.status_code == 200
    assert archived.json()["active"] is False

    listed_after = client.get("/api/approval-routes", headers=AUTH_LEGAL)
    assert not any(r["id"] == route_id for r in listed_after.json()["routes"])
    listed_all = client.get("/api/approval-routes?include_inactive=true", headers=AUTH_LEGAL)
    assert any(r["id"] == route_id for r in listed_all.json()["routes"])
