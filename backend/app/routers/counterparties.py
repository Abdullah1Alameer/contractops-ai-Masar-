"""Counterparty negotiation memory API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import CounterpartyProfile
from ..services.negotiation_monitor.memory import get_counterparty_memory

router = APIRouter(prefix="/counterparties", tags=["counterparties"])


@router.get("/{counterparty_id}/negotiation-memory")
def negotiation_memory(counterparty_id: str, db: Session = Depends(get_db)):
    profile = db.get(CounterpartyProfile, counterparty_id)
    email = None
    if profile:
        email = profile.counterparty_email
    else:
        # allow lookup by email slug id or raw email in path
        if "@" in counterparty_id:
            email = counterparty_id
        else:
            raise HTTPException(status_code=404, detail={"code": "not_found"})
    return get_counterparty_memory(db, counterparty_email=email or counterparty_id)
