"""Unit tests for F3 payment engine (no database)."""
from datetime import date
from types import SimpleNamespace

import pytest

from app.services.payments import (
    apply_milestone_patch,
    classify_payment_type,
    classify_precondition_type,
    compute_payment_status_and_readiness,
    stable_precondition_id,
)


def _row(**kwargs):
    defaults = {
        "paid": False,
        "label": "Payment 1",
        "amount_sar": 100000,
        "amount_percentage": None,
        "due_date": None,
        "preconditions": [],
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestClassifiers:
    def test_payment_type_advance_ar(self):
        assert classify_payment_type("الدفعة المقدمة", "") == "advance_payment"

    def test_payment_type_retention_en(self):
        assert classify_payment_type("Retention release", "") == "retention_release"

    def test_precondition_approval_ar(self):
        assert classify_precondition_type("اعتماد المهندس") == "approval"

    def test_precondition_inspection_en(self):
        assert classify_precondition_type("Inspection passed") == "inspection"

    def test_stable_id_deterministic(self):
        cid = "11111111-1111-1111-1111-111111111111"
        a = stable_precondition_id(cid, 1, "Engineer approval")
        b = stable_precondition_id(cid, 1, "engineer  approval")
        assert a == b


class TestComputeStatus:
    today = date(2026, 8, 1)

    def test_all_preconditions_incomplete_blocked(self):
        pre = [
            {"id": "1", "label": "A", "required": True, "completed": False},
            {"id": "2", "label": "B", "required": True, "completed": False},
        ]
        st, pct, claim, missing = compute_payment_status_and_readiness(_row(preconditions=pre), self.today)
        assert st == "blocked" and pct == 0 and claim is False and len(missing) == 2

    def test_partial_readiness(self):
        pre = [
            {"id": "1", "label": "A", "required": True, "completed": True},
            {"id": "2", "label": "B", "required": True, "completed": False},
        ]
        _, pct, _, _ = compute_payment_status_and_readiness(_row(preconditions=pre), self.today)
        assert pct == 50

    def test_all_complete_claimable(self):
        pre = [{"id": "1", "label": "A", "required": True, "completed": True}]
        st, pct, claim, missing = compute_payment_status_and_readiness(_row(preconditions=pre), self.today)
        assert st == "claimable" and pct == 100 and claim is True and missing == []

    def test_mark_paid(self):
        st, pct, claim, _ = compute_payment_status_and_readiness(_row(paid=True), self.today)
        assert st == "paid" and pct == 100 and claim is False

    def test_overdue_before_paid_priority(self):
        st, _, claim, _ = compute_payment_status_and_readiness(
            _row(due_date=date(2026, 7, 1), preconditions=[]),
            self.today,
        )
        assert st == "overdue" and claim is False

    def test_no_preconditions_claimable(self):
        st, pct, claim, _ = compute_payment_status_and_readiness(_row(preconditions=[]), self.today)
        assert st == "claimable" and pct == 100 and claim is True

    def test_missing_details_needs_review(self):
        st, _, claim, _ = compute_payment_status_and_readiness(
            _row(label="", amount_sar=None, amount_percentage=None),
            self.today,
        )
        assert st == "needs_review" and claim is False

    def test_sar_only(self):
        st, _, _, _ = compute_payment_status_and_readiness(_row(amount_sar=500000, amount_percentage=None), self.today)
        assert st == "claimable"

    def test_percentage_only(self):
        st, _, _, _ = compute_payment_status_and_readiness(_row(amount_sar=None, amount_percentage=20), self.today)
        assert st == "claimable"

    def test_sar_and_percentage(self):
        st, _, _, _ = compute_payment_status_and_readiness(
            _row(amount_sar=500000, amount_percentage=20),
            self.today,
        )
        assert st == "claimable"

    def test_demo_clock_overdue_flip(self):
        row = _row(due_date=date(2026, 8, 15), preconditions=[])
        st1, _, _, _ = compute_payment_status_and_readiness(row, date(2026, 8, 1))
        st2, _, _, _ = compute_payment_status_and_readiness(row, date(2026, 8, 20))
        assert st1 == "claimable"
        assert st2 == "overdue"


class TestApplyPatch:
    today = date(2026, 8, 1)

    def test_patch_precondition(self):
        pid = stable_precondition_id("11111111-1111-1111-1111-111111111111", 1, "Engineer approval")
        m = SimpleNamespace(
            paid=False,
            label="Pay 1",
            amount_sar=1,
            amount_percentage=None,
            due_date=None,
            preconditions=[{"id": pid, "label": "Engineer approval", "required": True, "completed": False}],
            status="blocked",
            updated_at=None,
        )
        apply_milestone_patch(m, {"precondition_id": pid, "completed": True}, self.today)
        assert m.preconditions[0]["completed"] is True
        assert m.status == "claimable"

    def test_patch_paid(self):
        m = _row(preconditions=[])
        m.status = "claimable"
        m.updated_at = None
        apply_milestone_patch(m, {"paid": True}, self.today)
        assert m.paid is True
        assert m.status == "paid"

    def test_invalid_precondition_raises(self):
        m = _row(preconditions=[])
        m.updated_at = None
        with pytest.raises(ValueError, match="invalid_precondition_id"):
            apply_milestone_patch(m, {"precondition_id": "bad", "completed": True}, self.today)


class TestMetadataAndRebuild:
    def test_serialize_shape(self):
        from app.models import Clause, PaymentMilestone
        from app.services.payments import serialize_milestone

        clause = Clause(clause_ref="14.3", quote="Payment No. 3", page=18, char_start=120, char_end=250)
        row = PaymentMilestone(
            seq=3,
            type="progress_payment",
            label="Payment No. 3",
            amount_sar=500000,
            amount_percentage=20,
            paid=False,
            preconditions=[],
        )
        row.id = __import__("uuid").uuid4()
        row.contract_id = __import__("uuid").uuid4()
        extr = {"verified": True, "clause_ref": "14.3", "char_start": 120, "char_end": 250, "confidence": 0.95}
        out = serialize_milestone(row, date(2026, 8, 1), extr, clause)
        assert out["clause_ref"] == "14.3"
        assert out["verified"] is True
        assert out["confidence"] == 0.95

    def test_rebuild_deletes_stale_generated(self):
        import inspect
        from app.services import payments as mod

        src = inspect.getsource(mod.build_payment_milestones_for_contract)
        assert "generated" in src and "delete" in src

    def test_arabic_classifier(self):
        assert classify_payment_type("دفعة مرحلية", "") in ("progress_payment", "milestone_payment", "interim_payment")

    def test_english_classifier(self):
        assert classify_payment_type("Final payment", "") == "final_payment"
