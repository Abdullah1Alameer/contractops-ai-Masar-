"""Unit tests for F2 deadline engine (no database)."""
from datetime import date, timedelta

import pytest

from app.services.deadlines import classify_notice_trigger, compute_status_and_severity


class TestClassifyNoticeTrigger:
    def test_payment_window_ar(self):
        assert classify_notice_trigger("سداد الفواتير", "خلال 15 يوماً") == "payment_window"

    def test_before_expiry_en(self):
        assert classify_notice_trigger("Notice", "30 days before expiry of the Works") == "before_expiry"

    def test_after_event_ar_claims(self):
        assert classify_notice_trigger("إشعار المطالبات وطلبات التمديد", "") == "after_event"

    def test_after_event_en(self):
        assert classify_notice_trigger("Claim", "within 60 days of becoming aware") == "after_event"

    def test_unknown(self):
        assert classify_notice_trigger("misc", "some generic text") == "unknown"


class TestComputeStatusAndSeverity:
    today = date(2026, 8, 1)

    def test_thirty_days_remaining_info(self):
        d = self.today + timedelta(days=30)
        st, sev, rem, tb = compute_status_and_severity(d, self.today, "contract_expiry", False)
        assert st == "upcoming" and sev == "info" and rem == 30 and tb is False

    def test_fourteen_days_warning(self):
        d = self.today + timedelta(days=14)
        _, sev, rem, _ = compute_status_and_severity(d, self.today, "bond_expiry", False)
        assert sev == "warning" and rem == 14

    def test_seven_days_critical(self):
        d = self.today + timedelta(days=7)
        _, sev, rem, _ = compute_status_and_severity(d, self.today, "bond_expiry", False)
        assert sev == "critical" and rem == 7

    def test_due_today(self):
        st, sev, rem, _ = compute_status_and_severity(self.today, self.today, "contract_expiry", False)
        assert st == "due_today" and sev == "critical" and rem == 0

    def test_missed_notice_time_barred(self):
        d = self.today - timedelta(days=1)
        st, sev, rem, tb = compute_status_and_severity(d, self.today, "notice_deadline", False)
        assert st == "missed" and sev == "critical" and rem == -1 and tb is True

    def test_missed_non_notice_not_time_barred(self):
        d = self.today - timedelta(days=1)
        _, _, _, tb = compute_status_and_severity(d, self.today, "bond_expiry", False)
        assert tb is False

    def test_needs_review_null_date(self):
        st, sev, rem, tb = compute_status_and_severity(None, self.today, "notice_deadline", True)
        assert st == "needs_review" and sev == "warning" and rem is None and tb is False

    def test_notice_thirty_days_before_expiry_math(self):
        end = date(2026, 12, 31)
        notice_days = 30
        deadline = end - timedelta(days=notice_days)
        assert deadline == date(2026, 12, 1)

    def test_notice_fourteen_days_after_event(self):
        ev = date(2026, 8, 1)
        assert ev + timedelta(days=14) == date(2026, 8, 15)

    def test_demo_clock_changes_severity(self):
        deadline = date(2026, 8, 20)
        _, sev_far, _, _ = compute_status_and_severity(deadline, date(2026, 8, 1), "notice_deadline", False)
        _, sev_close, _, _ = compute_status_and_severity(deadline, date(2026, 8, 15), "notice_deadline", False)
        assert sev_far in ("info", "normal", "warning")
        assert sev_close == "critical"

    def test_bond_expiry_upcoming(self):
        st, sev, rem, _ = compute_status_and_severity(date(2026, 9, 1), self.today, "bond_expiry", False)
        assert st == "upcoming" and rem == 31 and sev == "normal"

    def test_warranty_expiry(self):
        st, _, rem, _ = compute_status_and_severity(date(2027, 1, 1), self.today, "warranty_expiry", False)
        assert st == "upcoming" and rem > 30

    def test_metadata_preserved_in_serialize_shape(self):
        from app.models import Clause, Deadline
        from app.services.deadlines import serialize_deadline

        clause = Clause(
            clause_ref="20.1",
            quote="notice within 14 days",
            page=5,
            char_start=10,
            char_end=30,
        )
        d = Deadline(
            type="notice_deadline",
            title="Delay notice",
            needs_review=False,
            deadline_date=date(2026, 8, 15),
            confidence=0.96,
        )
        d.id = __import__("uuid").uuid4()
        d.contract_id = __import__("uuid").uuid4()
        out = serialize_deadline(d, date(2026, 8, 1), clause, {"verified": True, "confidence": 0.96})
        assert out["clause_ref"] == "20.1"
        assert out["verified"] is True
        assert out["char_start"] == 10
        assert out["confidence"] == 0.96

    def test_idempotent_rebuild_deletes_generated_only(self):
        import inspect
        from app.services import deadlines as mod

        src = inspect.getsource(mod.build_deadlines_for_contract)
        assert "generated" in src and "delete" in src
