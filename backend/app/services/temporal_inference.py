"""Infer temporal_rule from legacy notice_periods extraction items."""
from __future__ import annotations

import re
from typing import Any

_BEFORE_CONTRACT_END = re.compile(
    r"before\s+the\s+contract\s+end\s+date|"
    r"at\s+least\s+\d+\s+days?\s+before\s+the\s+contract\s+end|"
    r"قبل\s+.*(?:نهاية|انتهاء)\s+العقد",
    re.I,
)
_RENEWAL = re.compile(r"renew|renewal|تجديد|عدم\s+التجديد", re.I)
_PROBATION = re.compile(r"probation|probationary|تجرب", re.I)
_FROM_COMMENCEMENT = re.compile(
    r"from\s+the\s+commencement\s+date|commencement\s+date\s+of\s+work|"
    r"من\s+.*(?:مباشرة|ابتداء)\s+.*(?:العمل|العقد)",
    re.I,
)
_AFTER_CONTRACT_END = re.compile(
    r"from\s+the\s+contract\s+end\s+date|contract\s+end\s+date|"
    r"week\s+from\s+the\s+contract\s+end|"
    r"من\s+.*(?:نهاية|انتهاء)\s+العقد",
    re.I,
)
_TERMINATION = re.compile(
    r"Contract\s+Termination\s+Date|as\s+of\s+the\s+Contract\s+Termination|"
    r"ends\s+the\s+contract|"
    r"تاريخ\s+إنهاء\s+العقد",
    re.I,
)
_EXCLUDED_DAYS = re.compile(
    r"do not count towards this period|Eid al-Fitr|sick leave|"
    r"لا\s+تحتسب|عيد\s+الفطر|الإجازة\s+المرضية",
    re.I,
)
_DAY_OF_MONTH = re.compile(
    r"(\d{1,2})(?:st|nd|rd|th)?\s+of\s+each\s+month|"
    r"Due\s+Date:\s*(\d{1,2})|"
    r"(\d{1,2})\s*(?:من\s+)?(?:كل\s+)?(?:شهر|الشهر)",
    re.I,
)


def infer_temporal_rule_from_notice(item: dict) -> dict[str, Any]:
    purpose = item.get("purpose") or ""
    quote = item.get("quote") or ""
    text = f"{purpose} {quote}"
    days = item.get("days")
    try:
        days_int = int(days) if days is not None else None
    except (TypeError, ValueError):
        days_int = None

    rule: dict[str, Any] = {
        "base_date_type": "unknown",
        "base_date": None,
        "direction": "unknown",
        "offset_value": days_int,
        "offset_unit": "calendar_days",
        "computed_date": None,
        "recurrence": {"frequency": "none", "day_of_month": None, "interval": 1},
        "trigger_event": None,
        "condition_text": None,
        "calculation_confidence": float(item.get("confidence") or 0.8),
        "needs_review": False,
        "review_reason": None,
    }

    if _RENEWAL.search(text) and _BEFORE_CONTRACT_END.search(text):
        rule.update(
            {
                "base_date_type": "contract_end_date",
                "direction": "before",
                "recurrence": {"frequency": "per_term", "day_of_month": None, "interval": 1},
            }
        )
        rule["condition_text"] = purpose
        return rule

    if _PROBATION.search(text) and _FROM_COMMENCEMENT.search(text):
        rule.update(
            {
                "base_date_type": "commencement_date",
                "direction": "after",
            }
        )
        if _EXCLUDED_DAYS.search(text):
            rule["needs_review"] = True
            rule["review_reason"] = "excluded_days_unavailable"
        return rule

    if _TERMINATION.search(text) and days_int is not None:
        rule.update(
            {
                "base_date_type": "termination_date",
                "direction": "after",
                "trigger_event": "termination",
                "condition_text": purpose or "terminated_by_second_party",
            }
        )
        return rule

    if (
        "termination" in purpose.lower() or "Second Party ends" in quote
    ) and days_int is not None:
        rule.update(
            {
                "base_date_type": "termination_date",
                "direction": "after",
                "trigger_event": "termination",
                "condition_text": "terminated_by_second_party",
            }
        )
        return rule

    if _AFTER_CONTRACT_END.search(text) and days_int is not None:
        if "entitlement" in purpose.lower() or "settle" in quote.lower():
            rule.update(
                {
                    "base_date_type": "contract_end_date",
                    "direction": "after",
                    "condition_text": "contract_ended_normally_or_by_first_party",
                }
            )
            return rule

    if _BEFORE_CONTRACT_END.search(text) and days_int is not None:
        rule.update(
            {
                "base_date_type": "contract_end_date",
                "direction": "before",
            }
        )
        return rule

    if _FROM_COMMENCEMENT.search(text) and days_int is not None:
        rule.update(
            {
                "base_date_type": "commencement_date",
                "direction": "after",
            }
        )
        return rule

    rule["needs_review"] = True
    rule["review_reason"] = "trigger_unresolved"
    return rule


def infer_event_type_from_notice(item: dict, rule: dict) -> str:
    purpose = (item.get("purpose") or "").lower()
    if "renewal" in purpose:
        return "renewal_notice"
    if "probation" in purpose:
        return "probation_end"
    cond = rule.get("condition_text") or ""
    if rule.get("trigger_event") == "termination":
        return "settlement_after_termination"
    if "entitlement" in purpose or "contract end" in purpose:
        return "settlement_after_contract_end"
    return "notice_deadline"


def infer_responsible_party(item: dict, rule: dict) -> str | None:
    text = f"{item.get('purpose') or ''} {item.get('quote') or ''}".lower()
    if "either party" in text or "one party notifies" in text:
        return "either_party"
    if "second party ends" in text:
        return "first_party"
    if "first party" in text:
        return "first_party"
    if "second party" in text:
        return "second_party"
    return None


def detect_day_of_month_due_rule(raw_text: str | None) -> dict | None:
    if not raw_text:
        return None
    m = _DAY_OF_MONTH.search(raw_text)
    if not m:
        return None
    for g in m.groups():
        if g:
            try:
                day = int(g)
                if 1 <= day <= 31:
                    return {"type": "day_of_month", "day": day}
            except ValueError:
                pass
    return None


def merge_temporal_rule(item: dict) -> dict[str, Any]:
    embedded = item.get("temporal_rule")
    if isinstance(embedded, dict) and embedded.get("base_date_type") not in (None, "unknown"):
        return embedded
    return infer_temporal_rule_from_notice(item)
