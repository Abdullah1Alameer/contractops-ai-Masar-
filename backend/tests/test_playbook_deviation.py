"""Playbook deviation tests."""
import uuid
from unittest.mock import MagicMock

from app.models import PlaybookRule
from app.services.negotiation_monitor.playbook import evaluate_playbook


def test_payment_90_unacceptable_finance():
    rule = PlaybookRule(
        clause_category="Payment Terms",
        rule_name="Net payment days",
        preferred_position="30 days",
        fallback_position="45 days",
        unacceptable_position="More than 60 days",
        approval_required_role="finance",
        severity="high",
    )
    db = MagicMock()
    db.query.return_value.filter_by.return_value.all.return_value = [rule]
    out = evaluate_playbook(
        db,
        playbook_id=uuid.uuid4(),
        client_text="Payment within ninety (90) days",
        template_deviations=[
            {"clause_category": "Payment Terms", "client_clause": "Payment within ninety (90) days", "template_clause": "30 days"}
        ],
    )
    assert out[0]["deviation_level"] == "unacceptable"
    assert out[0]["required_approver"] == "finance"


def test_unlimited_liability_critical():
    rule = PlaybookRule(
        clause_category="Liability",
        rule_name="Cap",
        preferred_position="Contract value",
        fallback_position="2x",
        unacceptable_position="Unlimited liability",
        approval_required_role="legal",
        severity="critical",
    )
    db = MagicMock()
    db.query.return_value.filter_by.return_value.all.return_value = [rule]
    out = evaluate_playbook(
        db,
        playbook_id=uuid.uuid4(),
        client_text="liability shall be unlimited",
        template_deviations=[],
    )
    assert any(r["deviation_level"] == "unacceptable" for r in out)
