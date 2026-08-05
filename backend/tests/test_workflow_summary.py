from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import ApprovalWorkflow, Contract, Negotiation, ReviewRequest, SignatureRequest
from app.services.dashboard import workflow_summaries_by_contract


@pytest.fixture
def db_session():
    db = SessionLocal()
    contract_ids = []

    def create_contract(title: str = "Workflow summary test") -> Contract:
        contract = Contract(
            id=uuid4(),
            title=title,
            status="ready",
            stage="negotiation",
            file_url="synthetic-workflow-summary.pdf",
        )
        db.add(contract)
        db.commit()
        contract_ids.append(contract.id)
        return contract

    yield db, create_contract

    db.rollback()
    for contract_id in contract_ids:
        contract = db.get(Contract, contract_id)
        if contract is not None:
            db.delete(contract)
    db.commit()
    db.close()


def _review(contract_id, status: str, created_at: datetime) -> ReviewRequest:
    return ReviewRequest(
        id=uuid4(),
        contract_id=contract_id,
        token=f"review-{uuid4()}",
        recipient_name="Synthetic Reviewer",
        recipient_email="reviewer@example.invalid",
        status=status,
        expires_at=created_at + timedelta(days=7),
        created_at=created_at,
    )


def _signature(contract_id, status: str, created_at: datetime) -> SignatureRequest:
    return SignatureRequest(
        id=uuid4(),
        contract_id=contract_id,
        provider="simulated",
        status=status,
        subject="Synthetic signature request",
        expires_at=created_at + timedelta(days=7),
        created_at=created_at,
    )


def test_contract_without_workflows_returns_all_null_fields(db_session):
    db, create_contract = db_session
    contract = create_contract()

    response = TestClient(app).get(
        "/api/contracts?include=workflow_summary",
        headers={"Authorization": "Bearer demo-secret-token"},
    )

    assert response.status_code == 200
    row = next(item for item in response.json() if item["id"] == str(contract.id))
    assert row["workflow_summary"] == {
        "review_status": None,
        "negotiation_status": None,
        "approval_status": None,
        "signature_status": None,
    }


@pytest.mark.parametrize("status", ["sent", "opened", "changes_requested"])
def test_review_status_uses_canonical_field(db_session, status):
    db, create_contract = db_session
    contract = create_contract()
    db.add(_review(contract.id, status, datetime.now(timezone.utc)))
    db.commit()

    summary = workflow_summaries_by_contract(db)[contract.id]

    assert summary["review_status"] == status
    assert "review" not in summary


def test_approval_and_signature_statuses_are_canonical(db_session):
    db, create_contract = db_session
    contract = create_contract()
    now = datetime.now(timezone.utc)
    db.add(
        ApprovalWorkflow(
            id=uuid4(),
            contract_id=contract.id,
            status="in_progress",
            current_step_order=1,
            created_at=now,
        )
    )
    db.add(_signature(contract.id, "partially_signed", now))
    db.commit()

    summary = workflow_summaries_by_contract(db)[contract.id]

    assert summary["approval_status"] == "in_progress"
    assert summary["signature_status"] == "partially_signed"


def test_latest_records_are_selected_deterministically(db_session):
    db, create_contract = db_session
    contract = create_contract()
    now = datetime.now(timezone.utc)
    db.add_all(
        [
            _review(contract.id, "sent", now - timedelta(minutes=2)),
            _review(contract.id, "opened", now - timedelta(minutes=1)),
            _signature(contract.id, "completed", now - timedelta(minutes=2)),
            _signature(contract.id, "partially_signed", now - timedelta(minutes=1)),
        ]
    )
    db.commit()

    summary = workflow_summaries_by_contract(db)[contract.id]

    assert summary["review_status"] == "opened"
    assert summary["signature_status"] == "partially_signed"


def test_latest_active_negotiation_is_selected(db_session):
    db, create_contract = db_session
    contract = create_contract()
    now = datetime.now(timezone.utc)
    db.add_all(
        [
            Negotiation(
                id=uuid4(),
                contract_id=contract.id,
                status="draft",
                workflow_status="ready",
                created_at=now - timedelta(minutes=2),
                updated_at=now - timedelta(minutes=2),
            ),
            Negotiation(
                id=uuid4(),
                contract_id=contract.id,
                status="completed",
                workflow_status="closed",
                created_at=now - timedelta(minutes=1),
                updated_at=now - timedelta(minutes=1),
            ),
        ]
    )
    db.commit()

    summary = workflow_summaries_by_contract(db)[contract.id]

    assert summary["negotiation_status"] == "ready"


def test_contract_list_api_returns_sent_review_in_canonical_shape(db_session):
    db, create_contract = db_session
    contract = create_contract("Sent review integration")
    db.add(_review(contract.id, "sent", datetime.now(timezone.utc)))
    db.commit()

    response = TestClient(app).get(
        "/api/contracts?include=workflow_summary",
        headers={"Authorization": "Bearer demo-secret-token"},
    )

    assert response.status_code == 200
    row = next(item for item in response.json() if item["id"] == str(contract.id))
    assert row["workflow_summary"] == {
        "review_status": "sent",
        "negotiation_status": None,
        "approval_status": None,
        "signature_status": None,
    }
