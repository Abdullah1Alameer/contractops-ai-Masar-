"""Consent classifier and reclassify endpoint tests."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.ai.classifier import (
    CONSENT_SUPPORTED_CATEGORIES,
    CONFIDENCE_THRESHOLD,
    classify_contract,
    is_supported_category,
    text_has_consent_triggers,
)
from app.ai.consent_schema import is_consent_category


def test_consent_agreement_category_supported():
    assert "Consent Agreement" in CONSENT_SUPPORTED_CATEGORIES
    assert is_supported_category("Consent Agreement", CONFIDENCE_THRESHOLD)


@patch("app.ai.classifier.complete_json")
def test_authorize_background_check_supported(mock_llm):
    mock_llm.return_value = {
        "contract_category": "Employment Screening Consent",
        "confidence": 0.91,
        "reasoning_brief": "screening consent",
    }
    text = "I authorize the Company to conduct background check on my employment history."
    out = classify_contract(text)
    assert out["supported"] is True
    assert out["contract_category"] == "Employment Screening Consent"


@patch("app.ai.classifier.complete_json")
def test_cv_like_text_unsupported(mock_llm):
    mock_llm.return_value = {
        "contract_category": "Curriculum Vitae",
        "confidence": 0.95,
        "reasoning_brief": "resume",
    }
    text = "Curriculum Vitae\nWork Experience:\nSoftware Engineer at Acme\nEducation: Bachelor of Science"
    out = classify_contract(text)
    assert out["supported"] is False
    assert out["contract_category"] == "Curriculum Vitae"


@patch("app.ai.classifier.complete_json")
def test_uncertain_consent_trigger_needs_review(mock_llm):
    mock_llm.return_value = {
        "contract_category": "Unknown",
        "confidence": 0.55,
        "reasoning_brief": "unclear",
    }
    text = "I consent to the processing of my personal data for employment screening purposes."
    out = classify_contract(text)
    assert out["supported"] is True
    assert out["needs_review"] is True
    assert out["contract_category"] == "Other Legal Consent"
    assert out.get("message") == "needs_classification_review"


@patch("app.ai.classifier.complete_json")
def test_id_only_unsupported(mock_llm):
    mock_llm.return_value = {
        "contract_category": "Personal Identification Document",
        "confidence": 0.9,
        "reasoning_brief": "id card",
    }
    text = "National Identity Card\nIdentification Card Number: 1234567890"
    out = classify_contract(text)
    assert out["supported"] is False


def test_is_consent_category_helper():
    assert is_consent_category("Other Legal Consent")
    assert not is_consent_category("NDA")


def test_consent_triggers_detected():
    assert text_has_consent_triggers("I authorize release of information")


@pytest.fixture
def db_session():
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_reclassify_endpoint_logs_activity(db_session):
    from fastapi.testclient import TestClient

    from app.main import app
    from app.models import ActivityEvent, Contract

    client = TestClient(app)
    contract = Contract(
        id=uuid4(),
        title="Blocked upload",
        status="unsupported",
        supported=False,
        contract_category="Curriculum Vitae",
        file_url="demo/key.pdf",
    )
    db_session.add(contract)
    db_session.commit()

    with patch("app.routers.contracts.run_extraction") as mock_run:
        mock_run.return_value = {"supported": True, "status": "ready"}
        res = client.post(
            f"/api/contracts/{contract.id}/reclassify",
            json={"contract_category": "Other Legal Consent", "actor": "tester"},
            headers={"Authorization": "Bearer demo-secret-token"},
        )
    assert res.status_code == 200
    db_session.refresh(contract)
    assert contract.contract_category == "Other Legal Consent"
    assert contract.supported is True
    events = (
        db_session.query(ActivityEvent)
        .filter_by(contract_id=contract.id, event_type="contract_reclassified")
        .all()
    )
    assert len(events) == 1
    assert events[0].event_metadata.get("to") == "Other Legal Consent"
