"""Approval workflow unit tests.

Full start/decide/cancel/override flows are proved against a real database in
tests/test_approval_lifecycle_integration.py; this module covers the pure
helpers that guard those flows.
"""
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.approval_routes import _validate_steps
from app.services.approvals import (
    DEFAULT_ROLES,
    OVERRIDABLE_RULES,
    OVERRIDE_ROLES,
    ApprovalError,
    _authorize_override,
    _negotiation_view,
    _normalize_override,
    _reason_audit,
    allowed_actions_for_role,
    approval_summary,
    normalize_demo_role,
)
from app.services.reviews import build_public_payload


def test_default_four_roles_order():
    assert DEFAULT_ROLES == ["business_owner", "legal", "finance", "executive"]


def test_only_legal_and_executive_may_override():
    assert OVERRIDE_ROLES == {"legal", "executive"}


def test_normalize_demo_role_unknown():
    assert normalize_demo_role("hacker") == "legal"


def test_allowed_actions_wrong_role():
    w = SimpleNamespace(status="in_progress", current_step_order=2)
    steps = [
        SimpleNamespace(step_order=2, role="legal", status="pending"),
    ]
    assert allowed_actions_for_role(w, steps, "finance") == []


def test_allowed_actions_current_role():
    w = SimpleNamespace(status="in_progress", current_step_order=1)
    steps = [SimpleNamespace(step_order=1, role="business_owner", status="pending")]
    assert "approved" in allowed_actions_for_role(w, steps, "business_owner")


def test_allowed_actions_on_closed_workflow():
    w = SimpleNamespace(status="approved", current_step_order=4)
    steps = [SimpleNamespace(step_order=4, role="executive", status="approved")]
    assert allowed_actions_for_role(w, steps, "executive") == []


def test_validate_steps_preserves_order_and_defaults():
    # _resolve_sequence() (which always returned the hardcoded DEFAULT_ROLES
    # regardless of input) was removed as part of configurable approval
    # routes — _validate_steps() is its replacement, and actually honors
    # whatever roles/order the caller supplies. See
    # docs/configurable-approval-routes-report.md.
    clean = _validate_steps([{"role": "legal"}, {"role": "sales"}, {"role": "executive"}])
    assert [s["role"] for s in clean] == ["legal", "sales", "executive"]
    assert all(s["required"] is True for s in clean)


def test_validate_steps_rejects_unknown_role():
    with pytest.raises(ApprovalError) as excinfo:
        _validate_steps([{"role": "chief_pirate"}])
    assert excinfo.value.code == "invalid_approver"
    assert excinfo.value.status_code == 422


def test_validate_steps_rejects_empty():
    with pytest.raises(ApprovalError) as excinfo:
        _validate_steps([])
    assert excinfo.value.code == "approval_steps_required"


def test_validate_steps_rejects_duplicate_role_without_distinct_name():
    with pytest.raises(ApprovalError) as excinfo:
        _validate_steps([{"role": "legal"}, {"role": "legal"}])
    assert excinfo.value.code == "duplicate_approver"

    # Distinct named approvers under the same role are allowed.
    clean = _validate_steps(
        [{"role": "legal", "approver_name": "Fatima"}, {"role": "legal", "approver_name": "Yusuf"}]
    )
    assert len(clean) == 2


def test_legacy_force_flag_needs_structured_override():
    with pytest.raises(ApprovalError) as excinfo:
        _normalize_override(None, force=True)
    assert excinfo.value.code == "approval_reason_required"
    assert _normalize_override(None, force=False) is None


def test_normalize_override_requires_reason_and_known_rules():
    with pytest.raises(ApprovalError) as excinfo:
        _normalize_override({"reason": "   ", "negotiation_ids": []}, force=False)
    assert excinfo.value.code == "approval_reason_required"

    with pytest.raises(ApprovalError) as excinfo:
        _normalize_override(
            {"reason": "documented", "rules": ["workflow_stale"]},
            force=False,
        )
    assert excinfo.value.code == "forbidden_transition"

    normalized = _normalize_override({"reason": " documented ", "negotiation_ids": [1]}, force=False)
    assert normalized == {"reason": "documented", "negotiation_ids": ["1"], "rules": []}


def test_authorize_override_blocks_unlisted_blockers():
    listed = SimpleNamespace(id=uuid.uuid4(), clause_ref="7.1", workflow_status="ready")
    unlisted = SimpleNamespace(id=uuid.uuid4(), clause_ref="9.2", workflow_status="ready")
    override = {"reason": "documented", "negotiation_ids": [str(listed.id)], "rules": []}

    with pytest.raises(ApprovalError) as excinfo:
        _authorize_override(override, "legal", [listed, unlisted])

    assert excinfo.value.code == "unresolved_negotiations"
    assert excinfo.value.payload["unresolved"] == [_negotiation_view(unlisted)]


def test_authorize_override_requires_privileged_role():
    blocker = SimpleNamespace(id=uuid.uuid4(), clause_ref=None, workflow_status="ready")
    override = {"reason": "documented", "negotiation_ids": [str(blocker.id)], "rules": []}

    with pytest.raises(ApprovalError) as excinfo:
        _authorize_override(override, "finance", [blocker])

    assert excinfo.value.code == "approval_role_required"
    assert excinfo.value.status_code == 403


def test_authorize_override_records_rules_and_ids():
    blocker = SimpleNamespace(id=uuid.uuid4(), clause_ref=None, workflow_status="ready")
    override = {"reason": "documented", "negotiation_ids": [str(blocker.id)], "rules": []}

    granted = _authorize_override(override, "executive", [blocker])

    assert granted["negotiation_ids"] == [str(blocker.id)]
    assert granted["rules"] == list(OVERRIDABLE_RULES)


def test_missing_override_keeps_deterministic_unresolved_error():
    blocker = SimpleNamespace(id=uuid.uuid4(), clause_ref="7.1", workflow_status="pending_analysis")

    with pytest.raises(ApprovalError) as excinfo:
        _authorize_override(None, "legal", [blocker])

    assert excinfo.value.code == "unresolved_negotiations"
    assert excinfo.value.status_code == 409


def test_reason_audit_never_returns_reason_text():
    audit = _reason_audit("Confidential legal position")
    assert audit["reason_present"] is True
    assert "Confidential" not in str(audit)
    assert _reason_audit("  ") == {"reason_present": False}


def test_public_review_payload_no_approval_keys():
    req = SimpleNamespace(
        id=uuid.uuid4(),
        contract_id=uuid.uuid4(),
        recipient_name="C",
        status="opened",
        expires_at=None,
    )
    db = MagicMock()
    with patch("app.services.reviews.expire_if_needed", side_effect=lambda r, d: r):
        with patch("app.services.reviews.mark_opened"):
            with patch("app.services.reviews.build_review_dossier", return_value={"contract": {}, "ai_summary": ""}):
                with patch(
                    "app.services.reviews.serialize_review_request",
                    return_value={
                        "comments": [],
                        "expires_at": None,
                        "opened_at": None,
                        "responded_at": None,
                        "decision": None,
                        "overall_comment": None,
                        "contract_stage": "client_review",
                        "actionable": True,
                        "is_stale": False,
                        "terminal_decision": None,
                        "next_allowed_actions": ["approve", "reject", "request_changes"],
                    },
                ):
                    payload = build_public_payload(req, db)
    assert not any(k.lower().startswith("approval") for k in payload.keys())


def test_approval_summary_counts_canonical_stages():
    pending_step = SimpleNamespace(role="finance", status="pending", step_order=2)
    contracts_q = MagicMock()
    contracts_q.all.return_value = [
        SimpleNamespace(stage="internal_review"),
        SimpleNamespace(stage="ready_to_sign"),
        SimpleNamespace(stage="approved"),
    ]
    workflow_q = MagicMock()
    workflow_q.filter_by.return_value.all.return_value = [SimpleNamespace(current_step_order=2, id=uuid.uuid4())]
    step_q = MagicMock()
    step_q.filter_by.return_value.first.return_value = pending_step

    def query_side(model):
        from app.models import ApprovalStep, ApprovalWorkflow, Contract

        if model is Contract:
            return contracts_q
        if model is ApprovalWorkflow:
            return workflow_q
        if model is ApprovalStep:
            return step_q
        return MagicMock()

    db = MagicMock()
    db.query.side_effect = query_side
    summary = approval_summary(db)

    assert summary["internal_review"] == 1
    assert summary["pending_finance"] == 1
    assert summary["approved_awaiting_signature"] == 2
