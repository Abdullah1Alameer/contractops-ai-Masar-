"""Persisted proof that the public Client Review Portal's data matches the
same authorized-review dossier the internal endpoints show, for every tab:
risks, obligations, timeline, payments, comparison. See
docs/review-portal-data-audit.md for the full trace and root-cause writeup.
"""
from datetime import date, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import (
    Clause,
    Contract,
    ContractVersion,
    Deadline,
    Obligation,
    PaymentMilestone,
    RiskFinding,
)
from app.services.risk_engine import serialize_risk

AUTH = {"Authorization": "Bearer demo-secret-token", "X-Demo-Role": "legal"}


@pytest.fixture(autouse=True)
def portal_token_secret(monkeypatch):
    monkeypatch.setenv("PORTAL_TOKEN_SECRET", "review-portal-audit-secret")


@pytest.fixture
def portal_db():
    db = SessionLocal()
    contract_ids: list = []

    def create_contract(*, main_contract_id=None):
        contract = Contract(
            id=uuid4(),
            title="Synthetic portal audit contract",
            status="ready",
            stage="ready_for_client",
            supported=True,
            file_url="synthetic/portal-audit.pdf",
            parent_main_contract_id=main_contract_id,
        )
        db.add(contract)
        db.flush()
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
        clause = Clause(
            id=uuid4(),
            contract_id=contract.id,
            clause_ref="3",
            quote="Either party must give sixty (60) days written notice",
            page=2,
            char_start=0,
            char_end=52,
        )
        db.add_all([version, clause])
        db.flush()

        db.add(
            Obligation(
                id=uuid4(),
                contract_id=contract.id,
                title="Pay monthly wage",
                description="Provider shall invoice Client monthly.",
                responsible_party="Provider",
                beneficiary="Client",
                trigger_type="recurring",
                trigger_event="monthly_payroll",
                completion_criteria="Invoice acknowledged",
                suggested_evidence=["payroll_record"],
                due_date=date.today() + timedelta(days=30),
                penalty_text="0.5% per week late fee",
                status="pending",
                source_clause_id=clause.id,
            )
        )
        db.add(
            Deadline(
                id=uuid4(),
                contract_id=contract.id,
                type="notice_deadline",
                event_type="renewal_notice",
                title="Termination notice",
                deadline_date=None,
                source_trigger_date=None,
                notice_period_days=60,
                status="needs_review",
                needs_review=True,
                review_reason="missing_base_date",
                responsible_party="either_party",
                calculation_explanation="Date reference could not be fully resolved; requires human review.",
                calculation_explanation_ar="تعذر حل مرجع التاريخ بالكامل؛ يتطلب مراجعة بشرية.",
                source_clause_id=clause.id,
                generated=True,
            )
        )
        db.add(
            PaymentMilestone(
                id=uuid4(),
                contract_id=contract.id,
                seq=1,
                label="First milestone",
                amount_sar=50000,
                due_date=date.today() + timedelta(days=30),
                status="due",
                source_clause_id=clause.id,
                generated=True,
            )
        )
        db.add(
            RiskFinding(
                id=uuid4(),
                contract_id=contract.id,
                category="temporal",
                code="deadline_renewal_notice",
                points=2,
                count=1,
                explanation="Date reference could not be fully resolved; requires human review.",
                explanation_ar="تعذر حل مرجع التاريخ بالكامل؛ يتطلب مراجعة بشرية.",
                link_tab="deadlines",
                source_clause_id=clause.id,
                generated=True,
            )
        )
        db.commit()
        contract_ids.append(contract.id)
        return contract, version

    yield db, create_contract

    db.rollback()
    # Delete subcontracts before their main contract (parent_main_contract_id
    # FK) — commit each deletion individually so SQLAlchemy can't batch the
    # two DELETEs together out of order.
    for contract_id in reversed(contract_ids):
        row = db.get(Contract, contract_id)
        if row is not None:
            db.delete(row)
            db.commit()
    db.close()


def _send_and_get_token(client: TestClient, contract_id) -> str:
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
    return response.json()["request"]["token"]


def test_public_risk_score_matches_internal_risk_engine_exactly(portal_db):
    db, create_contract = portal_db
    contract, _ = create_contract()
    client = TestClient(app)
    token = _send_and_get_token(client, contract.id)

    internal_risk = serialize_risk(contract.id, db)
    portal = client.get(f"/api/review/{token}").json()

    assert portal["risks"]["score"] == internal_risk["score"]
    assert portal["risks"]["level"] == internal_risk["level"]
    scoring_items = [i for i in portal["risks"]["items"] if i["contributes_to_score"]]
    assert len(scoring_items) == len(internal_risk["findings"])
    assert scoring_items[0]["category"] == "temporal"
    assert scoring_items[0]["detail"] == internal_risk["findings"][0]["explanation"]
    assert scoring_items[0]["detail_ar"] == internal_risk["findings"][0]["explanation_ar"]


def test_public_risks_never_show_no_data_when_a_real_score_exists(portal_db):
    """Regression for the reported bug: a contract with a non-zero internal
    risk score used to show an empty public Risks tab because the old
    build_risk_summary() never consulted risk_engine at all."""
    db, create_contract = portal_db
    contract, _ = create_contract()
    client = TestClient(app)
    token = _send_and_get_token(client, contract.id)

    portal = client.get(f"/api/review/{token}").json()

    assert portal["risks"]["score"] > 0
    assert portal["risks"]["count"] > 0
    assert any(i["contributes_to_score"] for i in portal["risks"]["items"])


def test_public_obligations_render_complete_available_fields(portal_db):
    db, create_contract = portal_db
    contract, _ = create_contract()
    client = TestClient(app)
    token = _send_and_get_token(client, contract.id)

    portal = client.get(f"/api/review/{token}").json()
    obligation = portal["obligations"][0]

    for field in (
        "title",
        "beneficiary",
        "trigger_type",
        "trigger_event",
        "completion_criteria",
        "suggested_evidence",
    ):
        assert field in obligation, f"missing {field}"
    assert obligation["title"] == "Pay monthly wage"
    assert obligation["beneficiary"] == "Client"
    assert obligation["trigger_event"] == "monthly_payroll"


def test_public_timeline_includes_trigger_status_and_source(portal_db):
    db, create_contract = portal_db
    contract, _ = create_contract()
    client = TestClient(app)
    token = _send_and_get_token(client, contract.id)

    portal = client.get(f"/api/review/{token}").json()
    deadline = portal["timeline"]["deadlines"][0]

    assert deadline["status"] == "needs_review"
    assert deadline["notice_period_days"] == 60
    assert deadline["calculation_explanation"]
    assert deadline["calculation_explanation_ar"]
    assert deadline["clause_ref"] == "3"
    assert deadline["page"] == 2
    # The date is genuinely unresolved (missing_base_date) — null is the
    # honest value here, not a serialization bug.
    assert deadline["deadline_date"] is None
    assert deadline["review_reason"] == "missing_base_date"


def test_public_payments_render_complete_available_fields(portal_db):
    db, create_contract = portal_db
    contract, _ = create_contract()
    client = TestClient(app)
    token = _send_and_get_token(client, contract.id)

    portal = client.get(f"/api/review/{token}").json()
    milestone = portal["payments"]["milestones"][0]

    assert milestone["status"] in ("due", "claimable", "blocked", "scheduled")
    assert milestone["amount_sar"] == 50000.0
    assert milestone["due_date"] is not None
    assert milestone["clause_ref"] == "3"


def test_comparison_reason_is_not_linked_for_a_standalone_contract(portal_db):
    """Root-cause finding: comparison emptiness is about flowdown main/sub
    linkage, not about how many contract versions exist. A standalone
    contract with a single version and no subcontract link is exactly the
    "not_linked" case — the message must say that, not mention versions."""
    db, create_contract = portal_db
    contract, _ = create_contract()
    client = TestClient(app)
    token = _send_and_get_token(client, contract.id)

    portal = client.get(f"/api/review/{token}").json()

    assert portal["comparison"] is None
    assert portal["comparison_unavailable_reason"] == "not_linked"


def test_comparison_reason_is_not_yet_compared_when_linked_without_findings(portal_db):
    db, create_contract = portal_db
    main, _ = create_contract()
    sub, _ = create_contract(main_contract_id=main.id)
    client = TestClient(app)
    token = _send_and_get_token(client, sub.id)

    portal = client.get(f"/api/review/{token}").json()

    assert portal["comparison"] is None
    assert portal["comparison_unavailable_reason"] == "not_yet_compared"


def test_public_dossier_leaks_no_internal_only_fields(portal_db):
    """Extends the existing public-boundary contract: the enriched payload
    must still carry only safe business fields — no tokens, no raw actor
    identities beyond what review recipients already see, no negotiation
    playbook content."""
    db, create_contract = portal_db
    contract, _ = create_contract()
    client = TestClient(app)
    token = _send_and_get_token(client, contract.id)

    portal = client.get(f"/api/review/{token}").json()
    import json

    blob = json.dumps(portal)
    for forbidden in ("playbook", "template_deviation", "token_hash", "token_nonce", token):
        assert forbidden not in blob
