"""F3 — Payment Conditions Tracker: derive milestones from extractions (no LLM)."""
from __future__ import annotations

import re
import uuid as _uuid
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified


def _mark_jsonb_dirty(instance, attr: str) -> None:
    """Flag a JSONB column as modified; no-op for non-mapped test doubles."""
    try:
        flag_modified(instance, attr)
    except (AttributeError, Exception):
        pass

from ..models import Clause, Contract, DemoSettings, Event, Extraction, PaymentMilestone
from ..services.dates import parse_date_raw
from .date_semantics import sync_contract_date_semantics
from .temporal_inference import detect_day_of_month_due_rule
from .temporal_rules import compute_next_day_of_month, compute_recurrence_occurrences

_ADVANCE = re.compile(r"دفعة\s*مقدمة|advance\s*payment|down\s*payment|مقدم", re.I)
_RETENTION = re.compile(r"احتجاز|محتجز|retention", re.I)
_FINAL = re.compile(r"دفعة\s*نهائية|final\s*payment|final\s*invoice|الدفعة\s*الأخيرة", re.I)
_VARIATION = re.compile(r"أمر\s*تغيير|variation\s*order|variation", re.I)
_INTERIM = re.compile(r"مرحلية|interim", re.I)
_PROGRESS = re.compile(r"progress|إنجاز|مرحلة|interim\s*payment", re.I)
_MILESTONE = re.compile(r"milestone|دفعة", re.I)

_PRE_APPROVAL = re.compile(r"اعتماد|approval|approve|موافقة|engineer", re.I)
_PRE_INSPECTION = re.compile(r"فحص|inspection|test", re.I)
_PRE_CERT = re.compile(r"شهادة|certificate", re.I)
_PRE_COMPLETION = re.compile(r"إنجاز|إكمال|completion|delivery|work\s*completed", re.I)
_PRE_INVOICE = re.compile(r"فاتورة|invoice|claim\s*submission", re.I)

_STATUS_ORDER = {
    "overdue": 0,
    "due": 1,
    "claimable": 2,
    "blocked": 3,
    "scheduled": 4,
    "inactive": 5,
    "needs_review": 6,
    "paid": 7,
}

_COMPONENT_LABELS = frozenset(
    {"basic wage", "housing allowance", "transportation allowance", "transport allowance"}
)


def get_demo_today(db: Session) -> date:
    row = db.get(DemoSettings, 1)
    if row is None:
        return date.today()
    return row.today


def _normalize_label(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def stable_precondition_id(contract_id, seq: int, label: str) -> str:
    key = f"{contract_id}:{seq}:{_normalize_label(label)}"
    return str(_uuid.uuid5(_uuid.NAMESPACE_URL, key))


def classify_payment_type(label: str, quote: str = "") -> str:
    text = f"{label or ''} {quote or ''}"
    if re.search(r"salary|wage|أجر|راتب", text, re.I):
        if re.search(r"total\s+wage|أجر.*إجمال|total wage", text, re.I):
            return "salary"
        if re.search(r"allowance|بدل", text, re.I):
            return "allowance"
        return "salary"
    if _ADVANCE.search(text):
        return "advance_payment"
    if _RETENTION.search(text):
        return "retention_release"
    if _FINAL.search(text):
        return "final_payment"
    if _VARIATION.search(text):
        return "variation_payment"
    if _INTERIM.search(text):
        return "interim_payment"
    if _PROGRESS.search(text):
        return "progress_payment"
    if _MILESTONE.search(text):
        return "milestone_payment"
    return "other"


def classify_precondition_type(text: str) -> str:
    t = text or ""
    if _PRE_APPROVAL.search(t):
        return "approval"
    if _PRE_INSPECTION.search(t):
        return "inspection"
    if _PRE_CERT.search(t):
        return "certificate"
    if _PRE_COMPLETION.search(t):
        return "completion"
    if _PRE_INVOICE.search(t):
        return "invoice"
    return "other"


def _clause_uuid(item: dict) -> _uuid.UUID | None:
    cid = item.get("clause_id")
    if not cid:
        return None
    try:
        return _uuid.UUID(str(cid))
    except ValueError:
        return None


def _parse_due_date(item: dict) -> date | None:
    if item.get("due_date"):
        try:
            return date.fromisoformat(str(item["due_date"])[:10])
        except ValueError:
            pass
    raw = item.get("due_date_raw")
    if isinstance(raw, dict):
        return parse_date_raw(raw.get("value"), raw.get("detected_calendar"))
    return None


def _build_preconditions_list(
    contract_id,
    seq: int,
    raw_list: list | None,
    existing: list | None,
) -> list[dict]:
    existing_by_id = {p["id"]: p for p in (existing or []) if isinstance(p, dict) and p.get("id")}
    out: list[dict] = []
    for raw in raw_list or []:
        if isinstance(raw, dict):
            label = raw.get("label") or str(raw)
        else:
            label = str(raw)
        pid = stable_precondition_id(contract_id, seq, label)
        prev = existing_by_id.get(pid, {})
        out.append(
            {
                "id": pid,
                "label": label,
                "type": classify_precondition_type(label),
                "required": True,
                "completed": bool(prev.get("completed", False)),
            }
        )
    return out


def _needs_review_row(row: PaymentMilestone) -> bool:
    if not row.label or not str(row.label).strip():
        return True
    if row.amount_sar is None and row.amount_percentage is None:
        return True
    return False


def _classify_component_role(items: list[dict]) -> dict[int, tuple[str, int | None]]:
    """Return seq -> (role, parent_seq)."""
    by_label = {int(it.get("seq", 0)): (it.get("label") or "").strip().lower() for it in items if it.get("seq")}
    total_seq = None
    for seq, lbl in by_label.items():
        if "total wage" in lbl or "إجمال" in lbl:
            total_seq = seq
            break
    out: dict[int, tuple[str, int | None]] = {}
    for seq, lbl in by_label.items():
        if seq == total_seq:
            out[seq] = ("total", None)
        elif total_seq and lbl in _COMPONENT_LABELS:
            out[seq] = ("component", total_seq)
        else:
            out[seq] = ("standalone", None)
    return out


def _trigger_fired(row: PaymentMilestone, events: list | None = None) -> bool:
    if not row.trigger_event:
        return True
    if not events:
        return False
    for ev in events:
        if (ev.type or "").lower() in ("termination", "contract_termination", row.trigger_event):
            return True
    return False


def compute_payment_status_and_readiness(
    row: PaymentMilestone,
    today: date,
    *,
    events: list | None = None,
) -> tuple[str, int, bool, list[str]]:
    """Returns (status, readiness_percentage, claimable, missing_precondition_labels)."""
    pre = row.preconditions if isinstance(row.preconditions, list) else []
    required = [p for p in pre if isinstance(p, dict) and p.get("required", True)]
    completed = [p for p in required if p.get("completed")]
    missing = [p.get("label") or "" for p in required if not p.get("completed")]

    if required:
        readiness = round(100 * len(completed) / len(required))
    else:
        readiness = 100

    if row.paid:
        return "paid", 100, False, []

    if getattr(row, "role", None) == "component":
        return "scheduled", 100, False, missing

    if _needs_review_row(row):
        return "needs_review", 0, False, missing

    due = getattr(row, "next_due_date", None) or row.due_date
    trigger = getattr(row, "trigger_event", None)
    if trigger and not _trigger_fired(row, events):
        return "inactive", readiness, False, missing

    if due is None and trigger is None and not getattr(row, "due_rule", None):
        return "needs_review", readiness, False, missing

    if due and due > today:
        if required and len(completed) < len(required):
            return "blocked", readiness, False, missing
        return "scheduled", readiness, False, missing

    if due and due < today:
        return "overdue", readiness, False, missing

    if due and due <= today:
        if required and len(completed) < len(required):
            return "blocked", readiness, False, missing
        return "due", readiness, True, missing

    if required and len(completed) < len(required):
        return "blocked", readiness, False, missing

    return "needs_review", readiness, False, missing


def _effective_amount_sar(row: PaymentMilestone, contract: Contract | None) -> float:
    if row.amount_sar is not None:
        return float(row.amount_sar)
    if row.amount_percentage is not None and contract and contract.value_sar is not None:
        return float(contract.value_sar) * float(row.amount_percentage) / 100.0
    return 0.0


def _extr_milestones_by_seq(extractions: list[Extraction]) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for e in extractions:
        if e.field_name != "payment_milestones" or not isinstance(e.value_json, list):
            continue
        for item in e.value_json:
            if not isinstance(item, dict):
                continue
            seq = item.get("seq")
            if seq is not None:
                out[int(seq)] = item
    return out


def build_payment_milestones_for_contract(contract_id, db: Session) -> list[PaymentMilestone]:
    contract = db.get(Contract, contract_id)
    if contract is None:
        raise ValueError("contract_not_found")

    sync_contract_date_semantics(contract, db)
    due_rule_global = detect_day_of_month_due_rule(contract.raw_text)

    extractions = db.query(Extraction).filter_by(contract_id=contract_id).all()
    items: list[dict] = []
    for e in extractions:
        if e.field_name == "payment_milestones" and isinstance(e.value_json, list):
            items = e.value_json
            break

    roles = _classify_component_role([it for it in items if isinstance(it, dict)])
    events = db.query(Event).filter_by(contract_id=contract_id).all()
    today = get_demo_today(db)
    period_start = contract.commencement_date or contract.start_date
    period_end = contract.end_date

    existing_rows = {
        (m.seq): m
        for m in db.query(PaymentMilestone).filter_by(contract_id=contract_id).all()
    }
    seen_seq: set[int] = set()
    result: list[PaymentMilestone] = []

    for item in items:
        if not isinstance(item, dict):
            continue
        seq = item.get("seq")
        if seq is None:
            continue
        try:
            seq_int = int(seq)
        except (TypeError, ValueError):
            continue
        seen_seq.add(seq_int)

        label = item.get("label") or f"Payment {seq_int}"
        quote = item.get("quote") or ""
        ptype = classify_payment_type(label, quote)
        if ptype == "other" and re.search(r"monthly", quote, re.I):
            ptype = "salary" if "total" in label.lower() else "allowance"
        clause_id = _clause_uuid(item)
        amount_pct = item.get("amount_pct")
        amount_sar = item.get("amount_sar")
        conf = item.get("confidence")
        due = _parse_due_date(item)

        raw_pre = item.get("preconditions")
        if not isinstance(raw_pre, list):
            raw_pre = []

        role, parent_seq = roles.get(seq_int, ("standalone", None))
        frequency = item.get("frequency") or ("monthly" if re.search(r"monthly", quote, re.I) else None)
        due_rule = item.get("due_rule") if isinstance(item.get("due_rule"), dict) else due_rule_global
        next_due = None
        if due_rule and role != "component":
            next_due = compute_next_day_of_month(today, int(due_rule.get("day", 30)))
            if period_end and next_due > period_end:
                next_due = None
            if period_start and next_due and next_due < period_start:
                occ = compute_recurrence_occurrences(period_start, period_end, due_rule, today, limit=1)
                next_due = occ[0] if occ else next_due

        prev = existing_rows.get(seq_int)
        if prev and not prev.generated:
            result.append(prev)
            continue

        merged_pre = _build_preconditions_list(
            contract_id,
            seq_int,
            raw_pre,
            prev.preconditions if prev else None,
        )

        paid = prev.paid if prev else False
        paid_at = prev.paid_at if prev else None

        calc_en = None
        calc_ar = None
        if due_rule and next_due:
            calc_en = f"Monthly payment due on day {due_rule.get('day')} of each month; next due: {next_due.isoformat()}."
            calc_ar = f"الاستحقاق الشهري يوم {due_rule.get('day')} من كل شهر؛ الموعد التالي: {next_due.isoformat()}."

        common = dict(
            type=ptype,
            label=label,
            description=quote[:500] if quote else None,
            amount_sar=amount_sar,
            amount_percentage=amount_pct,
            due_date=due or next_due,
            next_due_date=next_due,
            preconditions=merged_pre,
            confidence=conf,
            source_clause_id=clause_id,
            paid=paid,
            paid_at=paid_at,
            role=role,
            parent_seq=parent_seq,
            frequency=frequency,
            due_rule=due_rule,
            period_start=period_start,
            period_end=period_end,
            responsible_party=item.get("responsible_party") or "first_party",
            beneficiary=item.get("beneficiary") or "second_party",
            trigger_event=item.get("trigger_event"),
            calculation_explanation=calc_en,
            calculation_explanation_ar=calc_ar,
        )

        if prev and prev.generated:
            for k, v in common.items():
                setattr(prev, k, v)
            prev.updated_at = datetime.now(timezone.utc)
            st, _, _, _ = compute_payment_status_and_readiness(prev, today, events=events)
            prev.status = st
            result.append(prev)
        else:
            m = PaymentMilestone(
                id=_uuid.uuid4(),
                contract_id=contract_id,
                seq=seq_int,
                generated=True,
                **common,
            )
            st, _, _, _ = compute_payment_status_and_readiness(m, today, events=events)
            m.status = st
            db.add(m)
            result.append(m)

    for seq_int, row in existing_rows.items():
        if row.generated and seq_int not in seen_seq:
            db.delete(row)

    db.flush()
    return result


def serialize_milestone(
    row: PaymentMilestone,
    today: date,
    extr_item: dict | None,
    clause: Clause | None,
) -> dict:
    status, readiness, claimable, missing = compute_payment_status_and_readiness(row, today)
    claimable = claimable and status in ("due", "claimable")

    quote = (extr_item or {}).get("quote") or (clause.quote if clause else None)
    clause_ref = (extr_item or {}).get("clause_ref") or (clause.clause_ref if clause else None)
    page = (extr_item or {}).get("page") if extr_item else (clause.page if clause else None)
    char_start = (extr_item or {}).get("char_start") if extr_item else (clause.char_start if clause else None)
    char_end = (extr_item or {}).get("char_end") if extr_item else (clause.char_end if clause else None)
    verified = bool(extr_item.get("verified")) if extr_item else bool(clause)
    conf = float(row.confidence) if row.confidence is not None else (extr_item or {}).get("confidence")

    pre = row.preconditions if isinstance(row.preconditions, list) else []

    amount_sar = float(row.amount_sar) if row.amount_sar is not None else None
    amount_pct = float(row.amount_percentage) if row.amount_percentage is not None else None

    return {
        "id": str(row.id),
        "contract_id": str(row.contract_id),
        "sequence": row.seq,
        "type": row.type or "other",
        "label": row.label,
        "description": row.description,
        "amount_sar": amount_sar,
        "amount_percentage": amount_pct,
        "due_date": row.due_date.isoformat() if row.due_date else None,
        "next_due_date": row.next_due_date.isoformat() if row.next_due_date else None,
        "frequency": row.frequency,
        "due_rule": row.due_rule,
        "role": row.role,
        "parent_seq": row.parent_seq,
        "responsible_party": row.responsible_party,
        "beneficiary": row.beneficiary,
        "trigger_event": row.trigger_event,
        "calculation_explanation": row.calculation_explanation,
        "calculation_explanation_ar": row.calculation_explanation_ar,
        "period_start": row.period_start.isoformat() if row.period_start else None,
        "period_end": row.period_end.isoformat() if row.period_end else None,
        "status": status,
        "readiness_percentage": readiness,
        "claimable": claimable,
        "paid": bool(row.paid),
        "preconditions": pre,
        "missing_preconditions": missing,
        "clause_ref": clause_ref,
        "quote": quote,
        "page": page,
        "confidence": round(conf, 2) if conf is not None else None,
        "verified": verified and char_start is not None and char_end is not None,
        "char_start": char_start,
        "char_end": char_end,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def list_payment_milestones_for_contract(contract_id, db: Session) -> list[dict]:
    contract = db.get(Contract, contract_id)
    if contract is None:
        raise ValueError("contract_not_found")

    today = get_demo_today(db)
    extractions = db.query(Extraction).filter_by(contract_id=contract_id).all()
    by_seq = _extr_milestones_by_seq(extractions)
    clauses = {c.id: c for c in db.query(Clause).filter_by(contract_id=contract_id)}

    rows = db.query(PaymentMilestone).filter_by(contract_id=contract_id).all()
    out = []
    for row in rows:
        extr_item = by_seq.get(row.seq)
        clause = clauses.get(row.source_clause_id) if row.source_clause_id else None
        out.append(serialize_milestone(row, today, extr_item, clause))

    def sort_key(item: dict):
        return (_STATUS_ORDER.get(item["status"], 99), item.get("sequence") or 0)

    out.sort(key=sort_key)
    return out


def payments_summary(milestones: list[dict], contract: Contract | None) -> dict:
    total = len(milestones)
    claimable_sar = 0.0
    blocked_sar = 0.0
    overdue_sar = 0.0
    paid_sar = 0.0
    needs_review_count = 0

    for m in milestones:
        if m.get("role") == "component":
            continue
        amt = m.get("amount_sar")
        if amt is None and contract and m.get("amount_percentage") and contract.value_sar:
            amt = float(contract.value_sar) * float(m["amount_percentage"]) / 100.0
        amt = float(amt or 0)
        st = m.get("status")
        if st in ("claimable", "due"):
            claimable_sar += amt
        elif st == "blocked":
            blocked_sar += amt
        elif st == "overdue":
            overdue_sar += amt
        elif st == "paid":
            paid_sar += amt
        elif st == "needs_review":
            needs_review_count += 1

    return {
        "total": total,
        "claimable_sar": round(claimable_sar, 2),
        "blocked_sar": round(blocked_sar, 2),
        "overdue_sar": round(overdue_sar, 2),
        "paid_sar": round(paid_sar, 2),
        "needs_review_count": needs_review_count,
    }


def apply_milestone_patch(milestone: PaymentMilestone, payload: dict[str, Any], today: date) -> None:
    now = datetime.now(timezone.utc)
    milestone.updated_at = now

    if "paid" in payload and payload["paid"] is not None:
        milestone.paid = bool(payload["paid"])
        milestone.paid_at = now if milestone.paid else None
        st, _, _, _ = compute_payment_status_and_readiness(milestone, today)
        milestone.status = st
        return

    pre = milestone.preconditions if isinstance(milestone.preconditions, list) else []

    if payload.get("precondition_id") is not None:
        pid = str(payload["precondition_id"])
        completed = bool(payload.get("completed"))
        found = False
        for p in pre:
            if isinstance(p, dict) and str(p.get("id")) == pid:
                p["completed"] = completed
                found = True
                break
        if not found:
            raise ValueError("invalid_precondition_id")
        milestone.preconditions = [dict(p) for p in pre]
        _mark_jsonb_dirty(milestone, "preconditions")
        st, _, _, _ = compute_payment_status_and_readiness(milestone, today)
        milestone.status = st
        return

    if payload.get("preconditions") is not None:
        incoming = payload["preconditions"]
        if not isinstance(incoming, list):
            raise ValueError("invalid_preconditions")
        by_id = {str(p.get("id")): p for p in pre if isinstance(p, dict) and p.get("id")}
        for item in incoming:
            if not isinstance(item, dict):
                continue
            iid = str(item.get("id", ""))
            if iid not in by_id:
                raise ValueError("invalid_precondition_id")
            by_id[iid]["completed"] = bool(item.get("completed"))
        milestone.preconditions = [dict(p) for p in by_id.values()]
        _mark_jsonb_dirty(milestone, "preconditions")
        st, _, _, _ = compute_payment_status_and_readiness(milestone, today)
        milestone.status = st
        return

    raise ValueError("invalid_patch")
