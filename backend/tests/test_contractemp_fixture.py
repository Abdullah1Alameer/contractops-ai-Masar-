"""contractEmp regression fixture (clause text shapes)."""
from datetime import date

from app.services.date_semantics import parse_header_dates
from app.services.temporal_inference import detect_day_of_month_due_rule, infer_temporal_rule_from_notice

EMP_HEADER = """
Contract execution date: 2025/11/17
Commencement date: 2025/11/16
Starting date: 2026/05/16
Contract end date: 2026/11/15
"""

RENEWAL_QUOTE = (
    "it will be automatically renewed for an equivalent period, unless one party notifies the other "
    "of their desire not to renew through the Portal, at least 10 days before the contract end date."
)

PROBATION_QUOTE = (
    "The Second Party is subject to a specified probationary period of 90 days, starting from the "
    "commencement date of work. The following days do not count towards this period: Eid al-Fitr."
)

WAGE_TEXT = "Due Date: 30th of each month"


def test_header_dates_parsed():
    h = parse_header_dates(EMP_HEADER)
    assert h["execution_date"] == date(2025, 11, 17)
    assert h["commencement_date"] == date(2025, 11, 16)
    assert h["starting_date"] == date(2026, 5, 16)
    assert h["contract_end_date"] == date(2026, 11, 15)


def test_renewal_rule():
    rule = infer_temporal_rule_from_notice({"purpose": "renewal notice", "days": 10, "quote": RENEWAL_QUOTE})
    assert rule["base_date_type"] == "contract_end_date"
    assert rule["direction"] == "before"


def test_probation_needs_review_for_exclusions():
    rule = infer_temporal_rule_from_notice(
        {"purpose": "probationary period termination", "days": 90, "quote": PROBATION_QUOTE}
    )
    assert rule["base_date_type"] == "commencement_date"
    assert rule["needs_review"] is True


def test_day_of_month_from_text():
    assert detect_day_of_month_due_rule(WAGE_TEXT) == {"type": "day_of_month", "day": 30}
