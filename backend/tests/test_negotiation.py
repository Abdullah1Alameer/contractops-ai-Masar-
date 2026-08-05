"""Feature 7 negotiation assistant tests (no live OpenAI)."""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.ai.negotiation_prompt import NEGOTIATION_SCHEMA, build_negotiation_prompt
from app.services import negotiation as neg_svc


def test_schema_has_required_enums():
    props = NEGOTIATION_SCHEMA["schema"]["properties"]
    assert "low" in props["risk_level"]["enum"]
    assert "negotiate" in props["recommendation"]["enum"]


def test_build_negotiation_prompt_includes_comment():
    text = build_negotiation_prompt(
        {"reviewer_comment": "Limit liability", "contract_title": "MSA", "original_clause": "Art 5"}
    )
    assert "Limit liability" in text
    assert "MSA" in text


def test_analyze_invalid_review():
    db = MagicMock()
    db.get.return_value = None
    with pytest.raises(ValueError, match="invalid_review"):
        neg_svc.analyze(uuid.uuid4(), None, db)


def test_analyze_no_comment_or_reason():
    review_id = uuid.uuid4()
    contract_id = uuid.uuid4()
    review = MagicMock(
        id=review_id,
        contract_id=contract_id,
        status="rejected",
    )
    contract = MagicMock(id=contract_id)
    response = MagicMock(decision="reject", overall_comment=None)

    db = MagicMock()
    db.get.side_effect = lambda model, pk: review if pk == review_id else contract
    db.query.return_value.filter_by.return_value.first.return_value = response

    with patch.object(neg_svc, "build_review_dossier", return_value={"ai_summary": "x"}):
        with pytest.raises(ValueError, match="no_comment_or_reason"):
            neg_svc.analyze(review_id, None, db)


def test_apply_patch_invalid_risk():
    db = MagicMock()
    n = MagicMock(status="draft")
    with pytest.raises(ValueError, match="invalid_risk_level"):
        neg_svc.apply_patch(n, {"risk_level": "extreme"}, db)


def test_apply_patch_accepts_risk_levels():
    db = MagicMock()
    n = MagicMock(status="draft", workflow_status="ready", edited_by_lawyer=False)
    for level in ("low", "medium", "high", "critical"):
        n.risk_level = None
        neg_svc.apply_patch(n, {"risk_level": level}, db)
        assert n.risk_level == level


def test_apply_patch_lawyer_final_sets_edited():
    db = MagicMock()
    n = MagicMock(status="draft", workflow_status="ready", edited_by_lawyer=False)
    neg_svc.apply_patch(n, {"lawyer_final_clause": "New EN"}, db)
    assert n.workflow_status == "edited_by_legal"


@patch("app.services.negotiation.complete_json")
@patch("app.services.negotiation.build_review_dossier")
def test_analyze_sets_workflow_ready(mock_dossier, mock_ai):
    mock_dossier.return_value = {"ai_summary": "Contract summary"}
    mock_ai.return_value = {
        "summary": "Sum",
        "business_impact": "Biz",
        "legal_impact": "Leg",
        "risk_level": "high",
        "recommendation": "negotiate",
        "reasoning": "Because",
        "counter_clause": "EN text",
        "arabic_counter_clause": "AR text",
        "pros": ["p1"],
        "cons": ["c1"],
    }

    review_id = uuid.uuid4()
    contract_id = uuid.uuid4()
    review = MagicMock(id=review_id, contract_id=contract_id, status="changes_requested")
    contract = MagicMock(id=contract_id, title="T")
    response = MagicMock(decision="changes_requested", overall_comment="Please soften clause 4")

    db = MagicMock()
    db.get.side_effect = lambda model, pk: review if pk == review_id else contract
    db.query.return_value.filter_by.return_value.first.side_effect = [response, None]
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock(side_effect=lambda n: setattr(n, "workflow_status", getattr(n, "workflow_status", "ready")))

    neg = neg_svc.analyze(review_id, None, db)
    assert neg.workflow_status == "ready"


@patch("app.services.negotiation.create_review_request")
@patch("app.services.negotiation.build_email_template")
@patch("app.services.negotiation.review_link")
def test_send_updated_links_review(mock_link, mock_email, mock_create):
    mock_create.return_value = MagicMock(id=uuid.uuid4(), token="tok")
    mock_link.return_value = "http://localhost:3000/review/tok"
    mock_email.return_value = {"subject": "s", "body": "b", "review_link": mock_link.return_value}

    neg = MagicMock(
        id=uuid.uuid4(),
        contract_id=uuid.uuid4(),
        review_request_id=uuid.uuid4(),
        status="approved",
        workflow_status="edited_by_legal",
        clause_ref="5.1",
        counter_clause="EN",
        counter_clause_ar="AR",
        lawyer_final_clause=None,
        lawyer_final_clause_ar=None,
        reviewer_comment="fix",
        original_clause="orig",
        recommendation="negotiate",
        reasoning="R",
        sent_review_request_id=None,
    )
    review = MagicMock(recipient_name="C", recipient_email="c@x.com", sender_name=None, sender_email=None)
    contract = MagicMock(title="T")

    db = MagicMock()
    db.get.side_effect = lambda model, pk: review if pk == neg.review_request_id else contract
    db.commit = MagicMock()
    db.refresh = MagicMock()

    with patch("app.services.negotiation.serialize_review_request", return_value={"id": "x"}):
        with patch("app.services.negotiation.serialize_negotiation", return_value={"id": str(neg.id)}):
            out = neg_svc.send_updated(neg, db)

    assert neg.workflow_status == "sent_to_client"
    assert neg.final_summary is not None
    assert "review_link" in out
    mock_create.assert_called_once()
