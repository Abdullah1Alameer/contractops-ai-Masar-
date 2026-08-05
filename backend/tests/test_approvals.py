"""Feature 8 approval workflow tests."""
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.approvals import (
    DEFAULT_ROLES,
    act_on_step,
    allowed_actions_for_role,
    approval_summary,
    cancel_workflow,
    normalize_demo_role,
    start_workflow,
    unresolved_negotiations,
)
from app.services.reviews import build_public_payload


def test_default_four_roles_order():
    assert DEFAULT_ROLES == ["business_owner", "legal", "finance", "executive"]


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


def test_unresolved_negotiations():
    db = MagicMock()
    db.query.return_value.filter_by.return_value.all.return_value = [
        SimpleNamespace(id=uuid.uuid4(), clause_ref="5", workflow_status="ready"),
        SimpleNamespace(id=uuid.uuid4(), clause_ref="6", workflow_status="accepted"),
    ]
    out = unresolved_negotiations(uuid.uuid4(), db)
    assert len(out) == 1


def test_start_workflow_unresolved_without_force():
    db = MagicMock()
    cid = uuid.uuid4()
    contract = SimpleNamespace(id=cid, stage="negotiation")
    db.get.return_value = contract
    with patch("app.services.approvals.get_active_workflow", return_value=None):
        with patch("app.services.approvals.unresolved_negotiations", return_value=[{"id": "x"}]):
            with pytest.raises(ValueError, match="unresolved_negotiations"):
                start_workflow(cid, db, force=False)


def test_act_wrong_role():
    step = SimpleNamespace(id=uuid.uuid4(), workflow_id=uuid.uuid4(), role="legal", step_order=2, status="pending")
    w = SimpleNamespace(id=step.workflow_id, contract_id=uuid.uuid4(), status="in_progress", current_step_order=2)
    db = MagicMock()
    db.get.side_effect = lambda model, pk: step if pk == step.id else w
    with pytest.raises(ValueError, match="wrong_role"):
        act_on_step(step.id, db, decision="approved", comment=None, demo_role="finance")


def test_act_out_of_order():
    step = SimpleNamespace(id=uuid.uuid4(), workflow_id=uuid.uuid4(), role="legal", step_order=2, status="locked")
    w = SimpleNamespace(id=step.workflow_id, contract_id=uuid.uuid4(), status="in_progress", current_step_order=1)
    db = MagicMock()
    db.get.side_effect = lambda model, pk: step if pk == step.id else w
    with pytest.raises(ValueError, match="out_of_order"):
        act_on_step(step.id, db, decision="approved", comment=None, demo_role="legal")


def test_act_reject_requires_comment():
    step = SimpleNamespace(id=uuid.uuid4(), workflow_id=uuid.uuid4(), role="business_owner", step_order=1, status="pending")
    w = SimpleNamespace(id=step.workflow_id, contract_id=uuid.uuid4(), status="in_progress", current_step_order=1)
    db = MagicMock()
    db.get.side_effect = lambda model, pk: step if pk == step.id else w
    with pytest.raises(ValueError, match="comment_required"):
        act_on_step(step.id, db, decision="rejected", comment="", demo_role="business_owner")


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
                    },
                ):
                    payload = build_public_payload(req, db)
    assert not any(k.lower().startswith("approval") for k in payload.keys())


def test_start_workflow_creates_four_steps():
    cid = uuid.uuid4()
    contract = SimpleNamespace(id=cid, stage="negotiation")
    db = MagicMock()
    db.get.return_value = contract
    added = []

    def capture_add(obj):
        added.append(obj)

    db.add = capture_add
    db.flush = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()

    with patch("app.services.approvals.get_active_workflow", return_value=None):
        with patch("app.services.approvals.unresolved_negotiations", return_value=[]):
            with patch("app.services.approvals.set_stage") as mock_stage:
                with patch("app.services.approvals.log_activity"):
                    start_workflow(cid, db, force=False)

    steps = [o for o in added if hasattr(o, "step_order")]
    assert len(steps) == 4
    assert [s.step_order for s in steps] == [1, 2, 3, 4]
    assert steps[0].status == "pending"
    assert steps[1].status == "locked"
    mock_stage.assert_called_once()


def test_start_workflow_already_active():
    db = MagicMock()
    contract = SimpleNamespace(id=uuid.uuid4(), stage="negotiation")
    db.get.return_value = contract
    with patch("app.services.approvals.get_active_workflow", return_value=SimpleNamespace()):
        with patch("app.services.approvals.unresolved_negotiations", return_value=[]):
            with pytest.raises(ValueError, match="workflow_already_active"):
                start_workflow(contract.id, db)


def test_start_workflow_contract_not_eligible():
    db = MagicMock()
    contract = SimpleNamespace(id=uuid.uuid4(), stage="approved")
    db.get.return_value = contract
    with patch("app.services.approvals.get_active_workflow", return_value=None):
        with pytest.raises(ValueError, match="contract_not_eligible"):
            start_workflow(contract.id, db)


def test_act_approve_advances_current_step():
    wid = uuid.uuid4()
    cid = uuid.uuid4()
    step1 = SimpleNamespace(
        id=uuid.uuid4(),
        workflow_id=wid,
        contract_id=cid,
        role="business_owner",
        step_order=1,
        status="pending",
    )
    step2 = SimpleNamespace(
        id=uuid.uuid4(),
        workflow_id=wid,
        contract_id=cid,
        role="legal",
        step_order=2,
        status="locked",
    )
    w = SimpleNamespace(
        id=wid,
        contract_id=cid,
        status="in_progress",
        current_step_order=1,
        started_by="demo",
        started_at=None,
        completed_at=None,
        updated_at=None,
    )
    contract = SimpleNamespace(id=cid, stage="internal_review")
    db = MagicMock()
    db.get.side_effect = lambda model, pk: (
        step1 if pk == step1.id else w if pk == wid else contract
    )
    db.query.return_value.filter_by.return_value.first.return_value = step2
    db.commit = MagicMock()
    db.refresh = MagicMock()

    with patch("app.services.approvals.log_activity"):
        with patch("app.services.approvals.serialize_workflow", return_value={"current_step_order": 2}) as mock_ser:
            act_on_step(step1.id, db, decision="approved", comment=None, demo_role="business_owner")

    assert w.current_step_order == 2
    assert step2.status == "pending"
    mock_ser.assert_called_once()


def test_act_final_approval_sets_stage_approved():
    wid = uuid.uuid4()
    cid = uuid.uuid4()
    step = SimpleNamespace(
        id=uuid.uuid4(),
        workflow_id=wid,
        contract_id=cid,
        role="executive",
        step_order=4,
        status="pending",
    )
    w = SimpleNamespace(
        id=wid,
        contract_id=cid,
        status="in_progress",
        current_step_order=4,
        started_by="demo",
        started_at=None,
        completed_at=None,
        updated_at=None,
    )
    contract = SimpleNamespace(id=cid, stage="internal_review")
    db = MagicMock()
    db.get.side_effect = lambda model, pk: (
        step if pk == step.id else w if pk == wid else contract
    )
    db.commit = MagicMock()
    db.refresh = MagicMock()

    with patch("app.services.approvals.log_activity"):
        with patch("app.services.approvals.set_stage") as mock_stage:
            with patch("app.services.approvals.serialize_workflow", return_value={"status": "approved"}):
                act_on_step(step.id, db, decision="approved", comment="OK", demo_role="executive")

    assert w.status == "approved"
    mock_stage.assert_called_with(contract, "approved", db)


def test_act_on_completed_workflow():
    step = SimpleNamespace(id=uuid.uuid4(), workflow_id=uuid.uuid4(), role="legal", step_order=1, status="pending")
    w = SimpleNamespace(id=step.workflow_id, contract_id=uuid.uuid4(), status="approved", current_step_order=1)
    db = MagicMock()
    db.get.side_effect = lambda model, pk: step if pk == step.id else w
    with pytest.raises(ValueError, match="workflow_completed"):
        act_on_step(step.id, db, decision="approved", comment=None, demo_role="legal")


def test_cancel_active_workflow():
    cid = uuid.uuid4()
    w = SimpleNamespace(
        id=uuid.uuid4(),
        contract_id=cid,
        status="in_progress",
        current_step_order=1,
        started_by="demo",
        started_at=None,
        completed_at=None,
    )
    contract = SimpleNamespace(id=cid, stage="internal_review")
    db = MagicMock()
    db.get.return_value = contract
    db.commit = MagicMock()
    db.refresh = MagicMock()

    with patch("app.services.approvals.get_active_workflow", return_value=w):
        with patch("app.services.approvals.set_stage") as mock_stage:
            with patch("app.services.approvals.log_activity"):
                with patch("app.services.approvals._steps_for_workflow", return_value=[]):
                    out = cancel_workflow(cid, db)

    assert w.status == "cancelled"
    mock_stage.assert_called_with(contract, "negotiation", db)
    assert out["status"] == "cancelled"


def test_approval_summary_counts():
    db = MagicMock()
    db.query.return_value.filter_by.return_value.all.return_value = [
        SimpleNamespace(current_step_order=2, id=uuid.uuid4()),
    ]
    pending_step = SimpleNamespace(role="finance", status="pending", step_order=2)
    db.query.return_value.filter_by.return_value.first.return_value = pending_step
    db.query.return_value.all.side_effect = [
        [
            SimpleNamespace(stage="internal_review"),
            SimpleNamespace(stage="approved"),
        ],
        [SimpleNamespace(current_step_order=2, id=uuid.uuid4())],
    ]

    # Re-mock query chain for approval_summary's two queries
    contracts_q = MagicMock()
    contracts_q.all.return_value = [
        SimpleNamespace(stage="internal_review"),
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

    db.query.side_effect = query_side
    summary = approval_summary(db)
    assert summary["internal_review"] == 1
    assert summary["pending_finance"] == 1
    assert summary["approved_awaiting_signature"] == 1
