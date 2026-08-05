"""Counterparty negotiation memory aggregates."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ...models import CounterpartyProfile, NegotiationReviewPackage, NegotiationThread


CLOSED_STATUSES = frozenset({"closed", "agreement_reached", "cancelled"})


def get_counterparty_memory(db: Session, *, counterparty_email: str) -> dict:
    email = counterparty_email.strip().lower()
    threads = (
        db.query(NegotiationThread)
        .filter(NegotiationThread.counterparty_email.ilike(email))
        .filter(NegotiationThread.status.in_(tuple(CLOSED_STATUSES)))
        .all()
    )
    evidence_count = len(threads)
    if evidence_count < 2:
        return {
            "counterparty_email": email,
            "evidence_count": evidence_count,
            "insufficient_history": True,
            "summary": "Insufficient history",
            "insights": [],
            "prior_thread_ids": [str(t.id) for t in threads],
        }

    pkg_ids = [t.id for t in threads]
    packages = db.query(NegotiationReviewPackage).filter(NegotiationReviewPackage.thread_id.in_(pkg_ids)).all()
    categories: Counter[str] = Counter()
    for p in packages:
        body = p.package_json if isinstance(p.package_json, dict) else {}
        for ch in body.get("changes") or []:
            cat = ch.get("clause_category")
            if cat:
                categories[cat] += 1

    insights = []
    for cat, count in categories.most_common(3):
        insights.append(f"Often negotiates {cat} ({count} prior mentions)")

    profile = db.query(CounterpartyProfile).filter_by(counterparty_email=email).first()
    if profile is None:
        profile = CounterpartyProfile(counterparty_email=email)
        db.add(profile)
    profile.memory_json = {
        "evidence_count": evidence_count,
        "insights": insights,
        "category_counts": dict(categories),
    }
    profile.computed_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "counterparty_email": email,
        "evidence_count": evidence_count,
        "insufficient_history": False,
        "summary": f"Based on {evidence_count} prior negotiations",
        "insights": insights,
        "prior_thread_ids": [str(t.id) for t in threads],
        "confidence": min(0.9, 0.3 + evidence_count * 0.15),
    }
