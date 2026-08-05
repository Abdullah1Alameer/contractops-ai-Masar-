"""Pure negotiation prompt and canonical status tests.

Persisted service behavior is covered by test_negotiation_lifecycle_integration.
"""

from app.ai.negotiation_prompt import NEGOTIATION_SCHEMA, build_negotiation_prompt
from app.services.negotiation import (
    ALLOWED_STATUS,
    ALLOWED_WORKFLOW_STATUS,
    NegotiationClosureOutcome,
    NegotiationError,
)


def test_schema_has_required_enums():
    props = NEGOTIATION_SCHEMA["schema"]["properties"]
    assert "low" in props["risk_level"]["enum"]
    assert "negotiate" in props["recommendation"]["enum"]


def test_build_negotiation_prompt_includes_comment():
    text = build_negotiation_prompt(
        {
            "reviewer_comment": "Limit liability",
            "contract_title": "MSA",
            "original_clause": "Art 5",
        }
    )
    assert "Limit liability" in text
    assert "MSA" in text


def test_editing_and_workflow_status_domains_remain_separate():
    assert ALLOWED_STATUS == {"draft", "approved", "edited", "sent", "closed"}
    assert ALLOWED_WORKFLOW_STATUS == {
        "pending_analysis",
        "ready",
        "edited_by_legal",
        "sent_to_client",
        "client_responded",
        "accepted",
        "closed",
    }


def test_closure_outcomes_are_explicit():
    assert {item.value for item in NegotiationClosureOutcome} == {
        "agreement_reached",
        "counterparty_rejected",
        "internally_abandoned",
        "superseded",
        "approval_overridden",
    }


def test_negotiation_error_preserves_http_contract():
    error = NegotiationError(409, "workflow_stale")
    assert error.status_code == 409
    assert error.payload == {"error": "workflow_stale"}
