"""Unit tests for temporal rule resolver."""
from datetime import date

from app.models import Contract, Event
from app.services.temporal_inference import infer_temporal_rule_from_notice, merge_temporal_rule
from app.services.temporal_rules import (
    compute_due_date,
    compute_next_day_of_month,
    resolve_temporal_rule,
)


def test_ten_days_before_contract_end():
    item = {
        "purpose": "renewal notice",
        "days": 10,
        "quote": "at least 10 days before the contract end date.",
        "confidence": 1.0,
    }
    rule = infer_temporal_rule_from_notice(item)
    c = Contract(end_date=date(2026, 11, 15), commencement_date=date(2025, 11, 16))
    out = resolve_temporal_rule(c, rule, [], date(2026, 8, 3))
    assert out["computed_date"] == date(2026, 11, 5)


def test_ninety_days_after_commencement():
    item = {
        "purpose": "probationary period termination",
        "days": 90,
        "quote": "90 days, starting from the commencement date of work.",
        "confidence": 1.0,
    }
    rule = infer_temporal_rule_from_notice(item)
    c = Contract(commencement_date=date(2025, 11, 16))
    out = resolve_temporal_rule(c, rule, [], date(2026, 8, 3))
    assert out["computed_date"] == date(2026, 2, 14)


def test_seven_days_after_contract_end():
    item = {
        "purpose": "payment of entitlements after contract end",
        "days": 7,
        "quote": "within a maximum period of one week from the contract end date.",
        "confidence": 1.0,
    }
    rule = infer_temporal_rule_from_notice(item)
    c = Contract(end_date=date(2026, 11, 15))
    out = resolve_temporal_rule(c, rule, [], date(2026, 8, 3))
    assert out["computed_date"] == date(2026, 11, 22)


def test_termination_inactive_without_event():
    item = {
        "purpose": "payment of entitlements after termination by Second Party",
        "days": 14,
        "quote": "as of the Contract Termination Date.",
        "confidence": 1.0,
    }
    rule = infer_temporal_rule_from_notice(item)
    c = Contract(end_date=date(2026, 11, 15))
    out = resolve_temporal_rule(c, rule, [], date(2026, 8, 3), termination_event_only=True)
    assert out["computed_date"] is None
    assert out["status"] == "inactive"


def test_termination_active_with_event():
    item = {
        "purpose": "payment of entitlements after termination by Second Party",
        "days": 14,
        "quote": "as of the Contract Termination Date.",
        "confidence": 1.0,
    }
    rule = infer_temporal_rule_from_notice(item)
    c = Contract(end_date=date(2026, 11, 15))
    ev = Event(type="termination", event_date=date(2026, 10, 1))
    out = resolve_temporal_rule(c, rule, [ev], date(2026, 8, 3), termination_event_only=True)
    assert out["computed_date"] == date(2026, 10, 15)


def test_monthly_day_30():
    assert compute_next_day_of_month(date(2026, 8, 3), 30) == date(2026, 8, 30)
    assert compute_next_day_of_month(date(2026, 8, 31), 30) == date(2026, 9, 30)


def test_unknown_base_needs_review():
    rule = {"base_date_type": "unknown", "direction": "after", "offset_value": 5, "offset_unit": "calendar_days"}
    c = Contract()
    out = resolve_temporal_rule(c, rule, [], date(2026, 8, 3))
    assert out["needs_review"] is True


def test_merge_prefers_embedded_rule():
    item = {
        "days": 10,
        "temporal_rule": {
            "base_date_type": "contract_end_date",
            "direction": "before",
            "offset_value": 10,
            "offset_unit": "calendar_days",
        },
    }
    rule = merge_temporal_rule(item)
    assert rule["base_date_type"] == "contract_end_date"


def test_compute_due_date_before():
    assert compute_due_date(date(2026, 11, 15), "before", 10, "calendar_days") == date(2026, 11, 5)
