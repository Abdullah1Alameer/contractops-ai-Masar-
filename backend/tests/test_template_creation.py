"""Real "Use Template" contract creation flow — see
docs/signature-placement-and-template-flow-report.md."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Contract, ContractTemplate, ContractVersion

AUTH = {"Authorization": "Bearer demo-secret-token", "X-Demo-Role": "legal"}

MSA_VARIABLES = {
    "party_a": "ContractOps LLC",
    "party_b": "Synthetic Test Client",
    "effective_date": "2026-08-01",
    "term_months": "12",
    "governing_law": "Saudi Arabia",
    "service_description": "Synthetic managed hosting services",
    "contract_value": "150000",
}


@pytest.fixture
def template_db():
    db = SessionLocal()
    contract_ids = []
    yield db
    db.rollback()
    for contract_id in contract_ids:
        contract = db.get(Contract, contract_id)
        if contract is not None:
            db.delete(contract)
    db.commit()
    db.close()


def _cleanup(db, contract_id):
    from sqlalchemy import text

    for tbl in (
        "activity_events", "deadlines", "payment_milestones", "obligations",
        "extractions", "contract_summaries", "clauses", "contract_versions",
    ):
        db.execute(text(f"DELETE FROM {tbl} WHERE contract_id = :id"), {"id": str(contract_id)})
        db.commit()
    db.execute(text("DELETE FROM contracts WHERE id = :id"), {"id": str(contract_id)})
    db.commit()


def test_unknown_template_returns_deterministic_error(template_db):
    client = TestClient(app)
    response = client.get("/api/templates/does-not-exist", headers=AUTH)
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "template_not_found"

    create = client.post(
        "/api/templates/does-not-exist/create-contract", headers=AUTH, json={"variables": {}}
    )
    assert create.status_code == 404
    assert create.json()["detail"]["error"] == "template_not_found"


def test_missing_required_variables_returns_deterministic_error(template_db):
    client = TestClient(app)
    response = client.post(
        "/api/templates/msa/create-contract", headers=AUTH, json={"variables": {"party_a": "Only One Field"}}
    )
    assert response.status_code == 422
    body = response.json()["detail"]
    assert body["error"] == "template_variables_missing"
    assert "party_b" in body["missing"]


def test_preview_substitutes_variables_into_rendered_sections(template_db):
    client = TestClient(app)
    response = client.post("/api/templates/msa/preview", headers=AUTH, json={"variables": MSA_VARIABLES})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["missing_variables"] == []
    joined = " ".join(s["body"] for s in body["sections_en"])
    assert MSA_VARIABLES["party_a"] in joined
    assert MSA_VARIABLES["party_b"] in joined
    assert MSA_VARIABLES["service_description"] in joined


def test_create_contract_from_template_persists_draft_v1_and_source(template_db):
    db = template_db
    client = TestClient(app)
    template = db.query(ContractTemplate).filter_by(key="msa").first()
    assert template is not None
    usage_before = template.usage_count

    response = client.post(
        "/api/templates/msa/create-contract", headers=AUTH, json={"variables": MSA_VARIABLES}
    )
    assert response.status_code == 201, response.text
    body = response.json()
    contract_id = body["id"]
    assert body["stage"] == "draft"
    assert body["template_id"] == str(template.id)

    try:
        db.expire_all()
        contract = db.get(Contract, contract_id)
        assert contract is not None
        assert contract.stage == "draft"
        assert str(contract.template_id) == str(template.id)
        assert contract.party_a == MSA_VARIABLES["party_a"]
        assert contract.party_b == MSA_VARIABLES["party_b"]

        versions = db.query(ContractVersion).filter_by(contract_id=contract_id).all()
        assert len(versions) == 1
        assert versions[0].version_number == 1
        assert versions[0].source == "template_generated"
        assert versions[0].is_current is True
        assert versions[0].file_path is not None

        db.refresh(template)
        assert template.usage_count == usage_before + 1
    finally:
        _cleanup(db, contract_id)
        db.expire_all()
        stale_template = db.query(ContractTemplate).filter_by(key="msa").first()
        stale_template.usage_count = usage_before
        db.commit()


def test_cancelling_before_submit_creates_no_partial_contract(template_db):
    """"Cancelling" in this flow means the frontend never calls
    create-contract — preview alone (or a validation failure) must not
    persist anything."""
    db = template_db
    client = TestClient(app)
    before = db.query(Contract).count()

    client.post("/api/templates/msa/preview", headers=AUTH, json={"variables": MSA_VARIABLES})
    failed = client.post(
        "/api/templates/msa/create-contract", headers=AUTH, json={"variables": {}}
    )
    assert failed.status_code == 422

    after = db.query(Contract).count()
    assert after == before
