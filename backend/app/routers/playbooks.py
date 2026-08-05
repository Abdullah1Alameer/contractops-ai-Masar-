"""Read-only legal playbook API."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..services.negotiation_monitor import service as mon_svc

router = APIRouter(prefix="/playbooks", tags=["playbooks"])


@router.get("")
def list_playbooks(db: Session = Depends(get_db)):
    return {"playbooks": mon_svc.list_playbooks(db)}


@router.get("/{playbook_id}")
def get_playbook(playbook_id: uuid.UUID, db: Session = Depends(get_db)):
    try:
        return mon_svc.get_playbook(playbook_id, db)
    except ValueError:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
