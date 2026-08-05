"""Negotiation round state machine."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from ...models import NegotiationRound, NegotiationThread


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def next_round_number(thread_id, db: Session) -> int:
    mx = db.query(func.max(NegotiationRound.round_number)).filter_by(thread_id=thread_id).scalar()
    return int(mx or 0) + 1


def open_round(
    db: Session,
    *,
    thread: NegotiationThread,
    inbound_email_id: uuid.UUID | None,
    base_version_id: uuid.UUID | None,
    proposed_version_id: uuid.UUID | None = None,
) -> NegotiationRound:
    if inbound_email_id is not None:
        existing = (
            db.query(NegotiationRound)
            .filter_by(thread_id=thread.id, inbound_email_id=inbound_email_id)
            .with_for_update()
            .first()
        )
        if existing is not None:
            return existing
    r = NegotiationRound(
        id=uuid.uuid4(),
        thread_id=thread.id,
        round_number=next_round_number(thread.id, db),
        inbound_email_id=inbound_email_id,
        base_version_id=base_version_id,
        proposed_version_id=proposed_version_id,
        status="received",
        opened_at=_utcnow(),
    )
    db.add(r)
    thread.status = "counterparty_responded"
    db.flush()
    return r


def set_round_status(round_row: NegotiationRound, status: str, db: Session) -> None:
    round_row.status = status


def close_round(round_row: NegotiationRound, db: Session, *, status: str = "sent") -> None:
    round_row.status = status
    round_row.closed_at = _utcnow()
