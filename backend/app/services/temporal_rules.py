"""Deterministic temporal rule resolution (no LLM arithmetic)."""
from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Any

from ..models import Contract, Event
from .date_semantics import resolve_base_date

BASE_DATE_LABELS = {
    "contract_end_date": ("contract end date", "تاريخ نهاية العقد"),
    "commencement_date": ("commencement date", "تاريخ مباشرة العمل"),
    "contract_start_date": ("contract start date", "تاريخ بداية العقد"),
    "starting_date": ("starting date", "تاريخ بدء العقد"),
    "execution_date": ("execution date", "تاريخ إبرام العقد"),
    "termination_date": ("termination date", "تاريخ إنهاء العقد"),
    "invoice_date": ("invoice date", "تاريخ الفاتورة"),
}


def _clamp_day(year: int, month: int, day: int) -> date:
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last))


def compute_due_date(
    base: date | None,
    direction: str | None,
    offset_value: int | None,
    offset_unit: str | None,
) -> date | None:
    if base is None or offset_value is None:
        return None
    unit = offset_unit or "calendar_days"
    if unit == "business_days":
        return None
    delta = timedelta(days=int(offset_value))
    direction = (direction or "after").lower()
    if direction == "before":
        return base - delta
    if direction in ("after", "on"):
        if direction == "on":
            return base
        return base + delta
    return None


def compute_next_day_of_month(from_day: date, day_of_month: int) -> date:
    dom = max(1, min(31, int(day_of_month)))
    candidate = _clamp_day(from_day.year, from_day.month, dom)
    if candidate >= from_day:
        return candidate
    if from_day.month == 12:
        return _clamp_day(from_day.year + 1, 1, dom)
    return _clamp_day(from_day.year, from_day.month + 1, dom)


def compute_recurrence_occurrences(
    start: date | None,
    end: date | None,
    due_rule: dict | None,
    demo_today: date,
    *,
    limit: int = 24,
) -> list[date]:
    if not due_rule or due_rule.get("type") != "day_of_month":
        return []
    dom = due_rule.get("day")
    if dom is None:
        return []
    period_start = start or demo_today
    period_end = end or (demo_today.replace(year=demo_today.year + 2))
    out: list[date] = []
    cursor = period_start
    while cursor <= period_end and len(out) < limit:
        nxt = compute_next_day_of_month(cursor, int(dom))
        if nxt > period_end:
            break
        if nxt >= period_start:
            out.append(nxt)
        cursor = nxt + timedelta(days=1)
    return out


def _event_for_trigger(events: list[Event], trigger_event: str | None) -> Event | None:
    if not trigger_event:
        return None
    aliases = {
        "termination": ("termination", "contract_termination", "terminated"),
        "contract_ends": ("contract_end", "contract_ends"),
        "invoice_received": ("invoice_received", "invoice"),
    }
    allowed = aliases.get(trigger_event, (trigger_event,))
    for ev in sorted(events, key=lambda e: e.event_date):
        if (ev.type or "").lower() in allowed:
            return ev
    return None


def explain_temporal_calculation(
    rule: dict,
    base: date | None,
    computed: date | None,
    *,
    needs_review: bool = False,
    review_reason: str | None = None,
) -> tuple[str, str]:
    btype = rule.get("base_date_type") or "unknown"
    labels = BASE_DATE_LABELS.get(btype, (btype.replace("_", " "), btype))
    direction = rule.get("direction") or "after"
    offset = rule.get("offset_value")
    unit = rule.get("offset_unit") or "calendar_days"
    unit_en = "calendar days" if unit == "calendar_days" else str(unit)
    unit_ar = "أيام تقويمية" if unit == "calendar_days" else str(unit)

    if rule.get("trigger_event") and base is None and computed is None:
        en = f"Awaiting triggering event ({rule.get('trigger_event')}); deadline not yet active."
        ar = f"بانتظار حدث التفعيل ({rule.get('trigger_event')})؛ الموعد غير نشط بعد."
        return en, ar

    if needs_review and review_reason == "excluded_days_unavailable":
        en = (
            f"Provisional: {offset} {unit_en} {direction} the {labels[0]}"
            f"{(' of ' + base.isoformat()) if base else ''}; "
            f"computed: {computed.isoformat() if computed else 'unknown'}. "
            "Excluded holidays/absence data not available for exact adjustment."
        )
        ar = (
            f"مؤقت: {offset} {unit_ar} {direction} {labels[1]}"
            f"{(' ' + base.isoformat()) if base else ''}؛ "
            f"الموعد المحسوب: {computed.isoformat() if computed else 'غير معروف'}. "
            "بيانات العطل/الغياب غير متوفرة للتعديل الدقيق."
        )
        return en, ar

    if computed and base and offset is not None:
        dir_en = "before" if direction == "before" else "after"
        dir_ar = "قبل" if direction == "before" else "بعد"
        en = (
            f"Due {offset} {unit_en} {dir_en} the {labels[0]} of {base.isoformat()}; "
            f"computed deadline: {computed.isoformat()}."
        )
        ar = (
            f"يستحق {dir_ar} {offset} {unit_ar} من {labels[1]} {base.isoformat()}؛ "
            f"الموعد المحسوب: {computed.isoformat()}."
        )
        return en, ar

    if needs_review:
        en = "Date reference could not be fully resolved; requires human review."
        ar = "تعذر حل مرجع التاريخ بالكامل؛ يتطلب مراجعة بشرية."
        return en, ar

    return "", ""


def resolve_temporal_rule(
    contract: Contract,
    rule: dict | None,
    events: list[Event],
    demo_today: date,
    *,
    termination_event_only: bool = False,
) -> dict[str, Any]:
    rule = dict(rule or {})
    trigger = rule.get("trigger_event")
    needs_review = bool(rule.get("needs_review"))
    review_reason = rule.get("review_reason")

    if rule.get("offset_unit") == "business_days":
        needs_review = True
        review_reason = review_reason or "business_days_unsupported"

    base: date | None = None
    if trigger in ("termination",) or termination_event_only:
        ev = _event_for_trigger(events, "termination")
        if ev is None:
            en, ar = explain_temporal_calculation(rule, None, None)
            return {
                "computed_date": None,
                "base_date": None,
                "status": "inactive",
                "needs_review": False,
                "review_reason": "awaiting_trigger",
                "calculation_explanation": en,
                "calculation_explanation_ar": ar,
                "temporal_rule": rule,
            }
        base = ev.event_date
        rule["base_date"] = base.isoformat()
        rule["base_date_type"] = "termination_date"
    else:
        fixed = rule.get("base_date")
        if fixed:
            try:
                base = date.fromisoformat(str(fixed)[:10])
            except ValueError:
                base = None
        if base is None:
            base = resolve_base_date(contract, rule.get("base_date_type"))
        if base:
            rule["base_date"] = base.isoformat()

    computed = rule.get("computed_date")
    if computed and isinstance(computed, str):
        try:
            computed = date.fromisoformat(computed[:10])
        except ValueError:
            computed = None
    if computed is None:
        computed = compute_due_date(
            base,
            rule.get("direction"),
            rule.get("offset_value"),
            rule.get("offset_unit"),
        )
    if computed:
        rule["computed_date"] = computed.isoformat()

    if base is None and not trigger:
        needs_review = True
        review_reason = review_reason or "missing_base_date"

    status = "needs_review" if needs_review else "scheduled"
    if computed and not needs_review:
        days = (computed - demo_today).days
        if days < 0:
            status = "overdue"
        elif days == 0:
            status = "upcoming"
        elif days <= 7:
            status = "critical" if days <= 7 else "upcoming"
        elif days <= 30:
            status = "upcoming"
        else:
            status = "scheduled"

    en, ar = explain_temporal_calculation(
        rule, base, computed, needs_review=needs_review, review_reason=review_reason
    )
    return {
        "computed_date": computed,
        "base_date": base,
        "status": status,
        "needs_review": needs_review,
        "review_reason": review_reason,
        "calculation_explanation": en,
        "calculation_explanation_ar": ar,
        "temporal_rule": rule,
    }
