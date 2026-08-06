"""Analysis-tab traceability audit — risk findings must resolve to their
source clause (quote/page/clause_ref), not just an opaque UUID, and the
category rollup must carry both languages. See
docs/analysis-traceability-audit.md.
"""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Clause, Contract, ContractVersion, RiskFinding
from app.services.risk_engine import serialize_risk

AUTH = {"Authorization": "Bearer demo-secret-token", "X-Demo-Role": "legal"}


@pytest.fixture
def risk_db():
    db = SessionLocal()
    contract_ids: list = []

    def create_contract():
        contract = Contract(
            id=uuid4(), title="Synthetic traceability contract", status="ready",
            stage="draft", supported=True, file_url="synthetic/traceability.pdf",
        )
        db.add(contract)
        db.flush()
        version = ContractVersion(
            id=uuid4(), contract_id=contract.id, version_number=1, version_label="v1",
            source="initial_upload", status="ready", file_path=contract.file_url,
            is_current=True, created_by="synthetic-test",
        )
        clause = Clause(
            id=uuid4(), contract_id=contract.id, clause_ref="12.3",
            quote="In the event of a defect, the Contractor must notify the Employer within seven (7) days.",
            page=4, char_start=100, char_end=195,
        )
        db.add_all([version, clause])
        db.flush()
        db.add(
            RiskFinding(
                id=uuid4(), contract_id=contract.id, category="operational",
                code="obligation_defect_notice", points=2, count=1,
                explanation="One obligation requires review.",
                explanation_ar="التزام واحد يتطلب مراجعة.",
                link_tab="obligations", source_clause_id=clause.id, generated=True,
            )
        )
        # A finding with no source clause at all (e.g. a contract-level
        # date inconsistency) — must not crash the resolution and must
        # honestly report source=None rather than a fabricated clause.
        db.add(
            RiskFinding(
                id=uuid4(), contract_id=contract.id, category="missing_date",
                code="date_inconsistency", points=2, count=1,
                explanation="Date inconsistency detected.",
                explanation_ar="تعارض في التواريخ.",
                link_tab="deadlines", source_clause_id=None, generated=True,
            )
        )
        db.commit()
        contract_ids.append(contract.id)
        return contract, version, clause

    yield db, create_contract

    db.rollback()
    for contract_id in contract_ids:
        c = db.get(Contract, contract_id)
        if c is not None:
            db.delete(c)
    db.commit()
    db.close()


def test_finding_with_source_clause_resolves_full_source(risk_db):
    db, create_contract = risk_db
    contract, _, clause = create_contract()

    payload = serialize_risk(contract.id, db)

    finding = next(f for f in payload["findings"] if f["code"] == "obligation_defect_notice")
    assert finding["source"] == {
        "clause_ref": "12.3",
        "quote": "In the event of a defect, the Contractor must notify the Employer within seven (7) days.",
        "page": 4,
        "char_start": 100,
        "char_end": 195,
    }
    assert finding["link_tab"] == "obligations"
    assert finding["explanation_ar"] == "التزام واحد يتطلب مراجعة."


def test_finding_without_source_clause_reports_none_not_fabricated(risk_db):
    db, create_contract = risk_db
    contract, _, _ = create_contract()

    payload = serialize_risk(contract.id, db)

    finding = next(f for f in payload["findings"] if f["code"] == "date_inconsistency")
    assert finding["source"] is None
    assert finding["source_clause_id"] is None


def test_breakdown_carries_both_languages(risk_db):
    db, create_contract = risk_db
    contract, _, _ = create_contract()

    payload = serialize_risk(contract.id, db)

    operational = next(b for b in payload["breakdown"] if b["category"] == "operational")
    assert operational["explanation"] == "One obligation requires review."
    assert operational["explanation_ar"] == "التزام واحد يتطلب مراجعة."


def test_contract_detail_endpoint_exposes_enriched_findings(risk_db):
    db, create_contract = risk_db
    contract, _, clause = create_contract()
    client = TestClient(app)

    response = client.get(f"/api/contracts/{contract.id}", headers=AUTH)

    assert response.status_code == 200, response.text
    risk = response.json()["risk"]
    finding = next(f for f in risk["findings"] if f["code"] == "obligation_defect_notice")
    assert finding["source"]["clause_ref"] == "12.3"
    assert finding["source"]["page"] == 4


def test_obligations_endpoint_already_exposed_full_traceability_data(risk_db):
    """Confirms the pre-existing (unaffected) backend endpoint already
    returns everything the audit needed for obligations — this fix only
    had to make the frontend render it, not change this endpoint."""
    db, create_contract = risk_db
    contract, _, clause = create_contract()
    from app.models import Obligation

    db.add(
        Obligation(
            id=uuid4(), contract_id=contract.id, description="Notify the Employer of any defect.",
            responsible_party="Contractor", trigger_event="defect_discovered",
            completion_criteria="Written notice delivered within 7 days",
            source_clause_id=clause.id, status="pending",
        )
    )
    db.commit()
    client = TestClient(app)

    response = client.get(f"/api/contracts/{contract.id}/obligations", headers=AUTH)

    assert response.status_code == 200, response.text
    row = response.json()[0]
    assert row["source"]["quote"] == clause.quote
    assert row["source"]["page"] == 4
    assert row["trigger_event"] == "defect_discovered"
    assert row["completion_criteria"] == "Written notice delivered within 7 days"
