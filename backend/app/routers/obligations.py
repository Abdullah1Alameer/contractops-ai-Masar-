import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Literal

from ..db import get_db
from ..models import Obligation

router = APIRouter(prefix="/obligations", tags=["obligations"])


class ObligationPatch(BaseModel):
    status: Literal["pending", "done", "overdue"]


@router.patch("/{obligation_id}")
def patch_obligation(obligation_id: _uuid.UUID, body: ObligationPatch, db: Session = Depends(get_db)):
    o = db.get(Obligation, obligation_id)
    if o is None:
        raise HTTPException(404, detail={"error": "not_found"})
    o.status = body.status
    db.commit()
    return {"id": str(o.id), "status": o.status}
