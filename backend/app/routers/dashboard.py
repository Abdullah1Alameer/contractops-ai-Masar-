"""F5 — dashboard aggregation. Real implementation (was a placeholder).

Aggregates: contracts by status, deadlines due within 30 days of the demo
clock (by severity), overdue obligations, and the total value of claimable
payment milestones.
"""
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Contract, Deadline, DemoSettings, Obligation, PaymentMilestone

router = APIRouter(tags=["dashboard"])

_STATUSES = ["ready", "needs_review", "processing", "failed"]
_SEVERITIES = ["critical", "warning", "info"]
_MILESTONE_STATUSES = ["blocked", "claimable", "paid"]
_OBLIGATION_STATUSES = ["pending", "overdue", "done"]


def _demo_today(db: Session) -> date:
    row = db.get(DemoSettings, 1)
    return row.today if row else date.today()


def _month_start(d: date, offset: int) -> date:
    total = d.year * 12 + (d.month - 1) + offset
    return date(total // 12, total % 12 + 1, 1)


def _month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _month_range(today: date, start_offset: int, count: int) -> list[date]:
    return [_month_start(today, start_offset + i) for i in range(count)]


@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db)):
    today = _demo_today(db)
    window_end = today + timedelta(days=30)

    by_status = dict(db.query(Contract.status, func.count(Contract.id)).group_by(Contract.status).all())

    upcoming = db.query(Deadline.severity, func.count(Deadline.id)).filter(
        Deadline.deadline_date >= today, Deadline.deadline_date <= window_end
    ).group_by(Deadline.severity).all()
    by_severity = dict(upcoming)

    overdue_obligations = db.query(func.count(Obligation.id)).filter(Obligation.status == "overdue").scalar() or 0

    claimable_sar = (
        db.query(func.coalesce(func.sum(PaymentMilestone.amount_sar), 0))
        .filter(PaymentMilestone.status == "claimable")
        .scalar()
    )

    milestones_by_status = dict(
        db.query(PaymentMilestone.status, func.count(PaymentMilestone.id)).group_by(PaymentMilestone.status).all()
    )

    # ---- deadlines forecast: monthly deadline count, current month + 5 ahead ----
    deadline_months = _month_range(today, 0, 6)
    deadline_window_end = _month_start(today, 6)
    deadline_dates = [
        d for (d,) in db.query(Deadline.deadline_date).filter(
            Deadline.deadline_date >= deadline_months[0], Deadline.deadline_date < deadline_window_end
        ).all()
    ]
    deadline_counts = {_month_key(m): 0 for m in deadline_months}
    for d in deadline_dates:
        deadline_counts[_month_key(_month_start(d, 0))] += 1
    deadlines_timeline = [{"month": _month_key(m), "count": deadline_counts[_month_key(m)]} for m in deadline_months]

    # ---- obligations workload: monthly due count by status, 2 months back + 5 ahead ----
    obligation_months = _month_range(today, -2, 8)
    obligation_window_end = _month_start(today, 6)
    obligation_rows = db.query(Obligation.due_date, Obligation.status).filter(
        Obligation.due_date >= obligation_months[0], Obligation.due_date < obligation_window_end
    ).all()
    obligation_counts = {_month_key(m): {s: 0 for s in _OBLIGATION_STATUSES} for m in obligation_months}
    for due_date, status in obligation_rows:
        key = _month_key(_month_start(due_date, 0))
        if key in obligation_counts and status in _OBLIGATION_STATUSES:
            obligation_counts[key][status] += 1
    obligations_timeline = [
        {"month": _month_key(m), **obligation_counts[_month_key(m)]} for m in obligation_months
    ]

    return {
        "contracts": {
            "total": sum(by_status.values()),
            **{s: by_status.get(s, 0) for s in _STATUSES},
        },
        "deadlines_next_30_days": sum(by_severity.values()),
        "deadlines_by_severity": {s: by_severity.get(s, 0) for s in _SEVERITIES},
        "overdue_obligations": overdue_obligations,
        "claimable_milestones_sar": float(claimable_sar),
        "milestones_by_status": {s: milestones_by_status.get(s, 0) for s in _MILESTONE_STATUSES},
        "deadlines_timeline": deadlines_timeline,
        "obligations_timeline": obligations_timeline,
    }
