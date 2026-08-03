"""F2 — Time-Bar Guardian: derive deadlines from extractions + events (no LLM)."""
from __future__ import annotations

import re
import uuid as _uuid
from datetime import date, timedelta

from sqlalchemy.orm import Session

from ..models import Clause, Contract, Deadline, DemoSettings, Event, Extraction, Obligation

NOTICE_TIME_BAR_TYPES = frozenset({"notice_deadline", "submission_deadline"})

_PAYMENT = re.compile(
    r"سداد|فاتورة|invoice|payment|قيمة\s*الفاتورة|within\s+\d+\s+days\s+of\s+receipt",
    re.I,
)
_BEFORE_EXPIRY = re.compile(
    r"قبل\s+انتهاء|قبل\s+نهاية|prior\s+to\s+expir|before\s+expir|before\s+the\s+end|قبل\s+تاريخ\s+انتهاء",
    re.I,
)
_AFTER_EVENT = re.compile(
    r"من\s+تاريخ|من\s+وقوع|بعد\s+وقوع|من\s+علم|from\s+the\s+date|after\s+the|within\s+\d+|"
    r"خلال\s+\d+|يوماً\s+من|أيام\s+من|يوم\s+من|إشعار\s+المطالبات|claim|extension|تمديد|becoming\s+aware",
    re.I,
)


def classify_notice_trigger(purpose: str, quote: str = "") -> str:
    text = f"{purpose or ''} {quote or ''}"
    if _PAYMENT.search(text):
        return "payment_window"
    if _BEFORE_EXPIRY.search(text):
        return "before_expiry"
    if _AFTER_EVENT.search(text):
        return "after_event"
    return "unknown"


def compute_status_and_severity(
    deadline_date: date | None,
    today: date,
    dl_type: str,
    needs_review: bool,
) -> tuple[str, str, int | None, bool]:
    """Centralized rules — returns (status, severity, days_remaining, time_barred)."""
    if needs_review or deadline_date is None:
        return "needs_review", "warning", None, False

    days_remaining = (deadline_date - today).days
    is_notice = dl_type in NOTICE_TIME_BAR_TYPES

    if days_remaining < 0:
        return "missed", "critical", days_remaining, is_notice
    if days_remaining == 0:
        return "due_today", "critical", 0, False
    if days_remaining <= 7:
        return "upcoming", "critical", days_remaining, False
    if days_remaining <= 14:
        return "upcoming", "warning", days_remaining, False
    if days_remaining <= 30:
        return "upcoming", "info", days_remaining, False
    return "upcoming", "normal", days_remaining, False


def get_demo_today(db: Session) -> date:
    row = db.get(DemoSettings, 1)
    if row is None:
        return date.today()
    return row.today


def _clause_uuid(item: dict) -> _uuid.UUID | None:
    cid = item.get("clause_id")
    if not cid:
        return None
    try:
        return _uuid.UUID(str(cid))
    except ValueError:
        return None


def _responsible_for_clause(db: Session, contract_id, clause_id) -> str | None:
    if clause_id is None:
        return None
    o = db.query(Obligation).filter_by(contract_id=contract_id, source_clause_id=clause_id).first()
    return o.responsible_party if o else None


def _snapshot_severity(deadline_date: date | None, today: date, dl_type: str, needs_review: bool) -> str:
    _, sev, _, _ = compute_status_and_severity(deadline_date, today, dl_type, needs_review)
    return sev


def build_deadlines_for_contract(contract_id, db: Session) -> list[Deadline]:
    contract = db.get(Contract, contract_id)
    if contract is None:
        raise ValueError("contract_not_found")

    today = get_demo_today(db)
    db.query(Deadline).filter(
        Deadline.contract_id == contract_id,
        Deadline.generated.is_(True),
    ).delete(synchronize_session=False)

    extr = {e.field_name: e.value_json for e in db.query(Extraction).filter_by(contract_id=contract_id)}
    notices = extr.get("notice_periods") or []
    if not isinstance(notices, list):
        notices = []

    events = db.query(Event).filter_by(contract_id=contract_id).order_by(Event.event_date.asc()).all()
    rows: list[Deadline] = []

    def add_row(**kwargs):
        dl_type = kwargs["type"]
        dl_date = kwargs.get("deadline_date")
        needs = kwargs.get("needs_review", False)
        sev = _snapshot_severity(dl_date, today, dl_type, needs)
        d = Deadline(
            id=_uuid.uuid4(),
            contract_id=contract_id,
            generated=True,
            severity=sev,
            **kwargs,
        )
        db.add(d)
        rows.append(d)

    if contract.end_date:
        add_row(
            type="contract_expiry",
            title="Contract expiry",
            label="Contract expiry",
            description="Contractual completion / expiry date.",
            deadline_date=contract.end_date,
            source_trigger_date=contract.end_date,
            needs_review=False,
        )
    if contract.bond_expiry:
        add_row(
            type="bond_expiry",
            title="Bond expiry",
            label="Bond expiry",
            description="Performance / bank bond expiry.",
            deadline_date=contract.bond_expiry,
            source_trigger_date=contract.bond_expiry,
            needs_review=False,
        )
    if contract.warranty_end:
        add_row(
            type="warranty_expiry",
            title="Warranty expiry",
            label="Warranty expiry",
            description="End of warranty period.",
            deadline_date=contract.warranty_end,
            source_trigger_date=contract.warranty_end,
            needs_review=False,
        )

    for item in notices:
        purpose = item.get("purpose") or "Notice period"
        quote = item.get("quote") or ""
        days = item.get("days")
        if days is None:
            continue
        try:
            days_int = int(days)
        except (TypeError, ValueError):
            continue

        clause_id = _clause_uuid(item)
        conf = item.get("confidence")
        trigger = classify_notice_trigger(purpose, quote)
        desc = f"Notice: {purpose} ({days_int} days)."
        title = purpose[:120]

        if trigger == "before_expiry":
            if contract.end_date:
                dl_date = contract.end_date - timedelta(days=days_int)
                add_row(
                    type="notice_deadline",
                    title=title,
                    label=title,
                    description=desc,
                    deadline_date=dl_date,
                    source_trigger_date=contract.end_date,
                    notice_period_days=days_int,
                    needs_review=False,
                    review_reason=None,
                    source_clause_id=clause_id,
                    confidence=conf,
                    responsible_party=_responsible_for_clause(db, contract_id, clause_id),
                )
            else:
                add_row(
                    type="notice_deadline",
                    title=title,
                    label=title,
                    description=desc,
                    deadline_date=None,
                    notice_period_days=days_int,
                    needs_review=True,
                    review_reason="no_contract_end_date",
                    source_clause_id=clause_id,
                    confidence=conf,
                    responsible_party=_responsible_for_clause(db, contract_id, clause_id),
                )
            continue

        if trigger == "after_event":
            if events:
                for ev in events:
                    dl_date = ev.event_date + timedelta(days=days_int)
                    add_row(
                        type="notice_deadline",
                        title=f"{title} ({ev.type})",
                        label=title,
                        description=f"{desc} Trigger: {ev.type} on {ev.event_date.isoformat()}.",
                        deadline_date=dl_date,
                        source_trigger_date=ev.event_date,
                        notice_period_days=days_int,
                        needs_review=False,
                        source_clause_id=clause_id,
                        confidence=conf,
                        responsible_party=_responsible_for_clause(db, contract_id, clause_id),
                        triggered_by_event_id=ev.id,
                    )
            else:
                add_row(
                    type="notice_deadline",
                    title=title,
                    label=title,
                    description=desc,
                    deadline_date=None,
                    notice_period_days=days_int,
                    needs_review=True,
                    review_reason="no_event_yet",
                    source_clause_id=clause_id,
                    confidence=conf,
                    responsible_party=_responsible_for_clause(db, contract_id, clause_id),
                )
            continue

        if trigger == "payment_window":
            add_row(
                type="payment_deadline",
                title=title,
                label=title,
                description=desc,
                deadline_date=None,
                notice_period_days=days_int,
                needs_review=True,
                review_reason="no_invoice_yet",
                source_clause_id=clause_id,
                confidence=conf,
                responsible_party=_responsible_for_clause(db, contract_id, clause_id),
            )
            continue

        add_row(
            type="notice_deadline",
            title=title,
            label=title,
            description=desc,
            deadline_date=None,
            notice_period_days=days_int,
            needs_review=True,
            review_reason="trigger_unresolved",
            source_clause_id=clause_id,
            confidence=conf,
            responsible_party=_responsible_for_clause(db, contract_id, clause_id),
        )

    db.flush()
    return rows


def serialize_deadline(d: Deadline, today: date, clause: Clause | None, extr_item: dict | None) -> dict:
    status, severity, days_remaining, time_barred = compute_status_and_severity(
        d.deadline_date, today, d.type or "other", d.needs_review
    )
    verified = bool(clause) and extr_item and extr_item.get("verified", True)
    quote = clause.quote if clause else (extr_item or {}).get("quote")
    clause_ref = clause.clause_ref if clause else (extr_item or {}).get("clause_ref")
    page = clause.page if clause else (extr_item or {}).get("page")
    char_start = clause.char_start if clause else (extr_item or {}).get("char_start")
    char_end = clause.char_end if clause else (extr_item or {}).get("char_end")
    conf = float(d.confidence) if d.confidence is not None else (extr_item or {}).get("confidence")

    return {
        "id": str(d.id),
        "contract_id": str(d.contract_id),
        "type": d.type,
        "title": d.title or d.label,
        "description": d.description,
        "event_date": d.deadline_date.isoformat() if d.deadline_date else None,
        "deadline_date": d.deadline_date.isoformat() if d.deadline_date else None,
        "source_trigger_date": d.source_trigger_date.isoformat() if d.source_trigger_date else None,
        "notice_period_days": d.notice_period_days,
        "days_remaining": days_remaining,
        "severity": severity,
        "status": status,
        "time_barred": time_barred,
        "needs_review": d.needs_review,
        "review_reason": d.review_reason,
        "responsible_party": d.responsible_party,
        "clause_ref": clause_ref,
        "quote": quote,
        "page": page,
        "confidence": round(conf, 2) if conf is not None else None,
        "verified": verified and char_start is not None and char_end is not None,
        "char_start": char_start,
        "char_end": char_end,
        "source_clause_id": str(d.source_clause_id) if d.source_clause_id else None,
        "triggered_by_event_id": str(d.triggered_by_event_id) if d.triggered_by_event_id else None,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


def _extr_by_clause(extractions: list[Extraction]) -> dict:
    """Map clause_id -> notice item for quote metadata fallback."""
    out: dict = {}
    for e in extractions:
        if e.field_name != "notice_periods" or not isinstance(e.value_json, list):
            continue
        for item in e.value_json:
            cid = item.get("clause_id")
            if cid:
                out[str(cid)] = item
    return out


def list_deadlines_for_contract(contract_id, db: Session) -> list[dict]:
    today = get_demo_today(db)
    contract = db.get(Contract, contract_id)
    if contract is None:
        raise ValueError("contract_not_found")

    clauses = {c.id: c for c in db.query(Clause).filter_by(contract_id=contract_id)}
    extractions = db.query(Extraction).filter_by(contract_id=contract_id).all()
    extr_map = _extr_by_clause(extractions)

    deadlines = db.query(Deadline).filter_by(contract_id=contract_id).all()
    out = []
    for d in deadlines:
        clause = clauses.get(d.source_clause_id) if d.source_clause_id else None
        extr_item = extr_map.get(str(d.source_clause_id)) if d.source_clause_id else None
        out.append(serialize_deadline(d, today, clause, extr_item))

    def sort_key(item: dict):
        if item["needs_review"]:
            return (0, item.get("event_date") or "9999-12-31")
        st = item["status"]
        ed = item.get("event_date") or "9999-12-31"
        if st == "missed":
            return (2, ed)
        if st in ("upcoming", "due_today"):
            return (1, ed)
        return (3, ed)

    out.sort(key=sort_key)
    return out


def deadline_summary(deadlines: list[dict]) -> dict:
    critical = sum(1 for d in deadlines if d["severity"] == "critical" and d["status"] != "needs_review")
    within_14 = sum(
        1
        for d in deadlines
        if d.get("days_remaining") is not None and 0 <= d["days_remaining"] <= 14
    )
    missed_tb = sum(1 for d in deadlines if d["status"] == "missed" or d.get("time_barred"))
    needs = sum(1 for d in deadlines if d["needs_review"])
    return {
        "total": len(deadlines),
        "critical": critical,
        "within_14_days": within_14,
        "missed_or_time_barred": missed_tb,
        "needs_review": needs,
    }
