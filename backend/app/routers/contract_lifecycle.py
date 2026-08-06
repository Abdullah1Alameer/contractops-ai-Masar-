"""Contract-level lifecycle actions (currently: draft -> ready_for_client)."""
from __future__ import annotations

import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import demo_role
from ..services.contract_lifecycle import mark_ready_for_client
from ..services.lifecycle import LifecycleError

router = APIRouter(tags=["contract-lifecycle"])


@router.post("/contracts/{contract_id}/mark-ready-for-client")
def mark_ready_for_client_route(
    contract_id: _uuid.UUID,
    db: Session = Depends(get_db),
    actor: str = Depends(demo_role),
):
    try:
        return mark_ready_for_client(contract_id, db, actor=actor)
    except LifecycleError as error:
        raise HTTPException(error.status_code, detail=error.payload)
