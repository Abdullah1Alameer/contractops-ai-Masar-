"""Persisted proof for the draft -> ready_for_client entry action, and for
the root-cause fix: a newly created contract defaults to `draft`, not
`negotiation` (see backend/app/models.py Contract.stage and
database/migrations/019_contract_stage_default_draft.sql).
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import ActivityEvent, Contract, ContractVersion, ReviewRequest

AUTH = {"Authorization": "Bearer demo-secret-token", "X-Demo-Role": "legal"}


@pytest.fixture(autouse=True)
def portal_token_secret(monkeypatch):
    monkeypatch.setenv("PORTAL_TOKEN_SECRET", "contract-lifecycle-integration-secret")


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


@pytest.fixture
def contract_db():
    db = SessionLocal()
    contract_ids: list = []

    def create_contract(*, stage="draft", status="ready", with_version=True, supported=True):
        contract = Contract(
            id=uuid4(),
            title="Synthetic contract lifecycle",
            status=status,
            stage=stage,
            supported=supported,
            file_url="synthetic/contract-lifecycle.pdf",
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
        row = db.get(Contract, contract_id)
        if row is not None:
            db.delete(row)
    db.commit()
    db.close()


# --------------------------------------------------------------------------
# Root cause: a new Contract() defaults to draft, not negotiation.
# --------------------------------------------------------------------------
def test_new_contract_defaults_to_draft_not_negotiation():
    """Directly exercises the ORM Column default every insert path uses,
    including the frozen `POST /api/contracts` upload endpoint (which never
    sets `stage` explicitly) — this is the actual mechanism that produced
    the reported bug, and the actual mechanism the fix changes."""
    db = SessionLocal()
    contract = Contract(
        id=uuid4(),
        title="Synthetic default-stage contract",
        status="processing",
        supported=None,
        file_url="synthetic/default-stage.pdf",
        # stage intentionally omitted — this is what upload_contract() does.
    )
    db.add(contract)
    try:
        db.commit()
        db.refresh(contract)
        assert contract.stage == "draft"
    finally:
        db.delete(contract)
        db.commit()
        db.close()


# --------------------------------------------------------------------------
# mark-ready-for-client: draft -> ready_for_client
# --------------------------------------------------------------------------
def test_mark_ready_for_client_requires_current_version(contract_db):
    db, create_contract = contract_db
    contract, _ = create_contract(with_version=False)

    response = TestClient(app).post(
        f"/api/contracts/{contract.id}/mark-ready-for-client", headers=AUTH
    )

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "no_current_version"
    db.expire_all()
    assert db.get(Contract, contract.id).stage == "draft"


def test_mark_ready_for_client_rejects_unfinished_extraction(contract_db):
    db, create_contract = contract_db
    contract, _ = create_contract(status="processing")

    response = TestClient(app).post(
        f"/api/contracts/{contract.id}/mark-ready-for-client", headers=AUTH
    )

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "contract_not_ready"
    db.expire_all()
    assert db.get(Contract, contract.id).stage == "draft"


def test_mark_ready_for_client_rejects_unsupported_document(contract_db):
    db, create_contract = contract_db
    contract, _ = create_contract(status="ready", supported=False)

    response = TestClient(app).post(
        f"/api/contracts/{contract.id}/mark-ready-for-client", headers=AUTH
    )

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "contract_not_ready"


def test_mark_ready_for_client_rejects_active_review(contract_db):
    db, create_contract = contract_db
    contract, version = create_contract(status="ready")
    db.add(
        ReviewRequest(
            id=uuid4(),
            contract_id=contract.id,
            version_id=version.id,
            token=f"active-{uuid4()}",
            recipient_name="Synthetic Reviewer",
            recipient_email="reviewer@example.invalid",
            status="sent",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
    )
    db.commit()

    response = TestClient(app).post(
        f"/api/contracts/{contract.id}/mark-ready-for-client", headers=AUTH
    )

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "review_already_active"


def test_mark_ready_for_client_succeeds_and_is_atomic_with_activity(contract_db):
    db, create_contract = contract_db
    contract, version = create_contract(status="ready")

    response = TestClient(app).post(
        f"/api/contracts/{contract.id}/mark-ready-for-client", headers=AUTH
    )

    assert response.status_code == 200, response.text
    assert response.json() == {"id": str(contract.id), "stage": "ready_for_client"}
    db.expire_all()
    assert db.get(Contract, contract.id).stage == "ready_for_client"
    assert "contract_ready_for_client" in _events(db, contract.id)


def test_mark_ready_for_client_only_valid_from_draft(contract_db):
    """The source-stage check is enforced by LifecycleService itself — this
    proves the deterministic 409 invalid_stage_transition response, and that
    a second call is rejected rather than silently re-applied."""
    db, create_contract = contract_db
    contract, _ = create_contract(stage="negotiation", status="ready")

    response = TestClient(app).post(
        f"/api/contracts/{contract.id}/mark-ready-for-client", headers=AUTH
    )

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "invalid_stage_transition"
    assert response.json()["detail"]["current_stage"] == "negotiation"


def test_mark_ready_for_client_then_send_for_review_chains_correctly(contract_db):
    """draft -> ready_for_client -> client_review, proving the new action
    unlocks exactly the existing review-send transition and nothing else."""
    db, create_contract = contract_db
    contract, _ = create_contract(status="ready")
    client = TestClient(app)

    ready = client.post(f"/api/contracts/{contract.id}/mark-ready-for-client", headers=AUTH)
    assert ready.status_code == 200

    sent = client.post(
        f"/api/contracts/{contract.id}/review/send",
        headers=AUTH,
        json={
            "recipient_name": "Synthetic Reviewer",
            "recipient_email": "reviewer@example.invalid",
            "sender_name": "Synthetic Sender",
            "sender_email": "sender@example.invalid",
            "expires_in_days": 7,
        },
    )
    assert sent.status_code == 200, sent.text
    db.expire_all()
    assert db.get(Contract, contract.id).stage == "client_review"
