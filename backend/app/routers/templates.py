"""Contract templates — real "Use Template" creation flow."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import demo_role
from ..services import templates as tpl_svc

router = APIRouter(prefix="/templates", tags=["templates"])


def _map_err(e: Exception) -> HTTPException:
    if isinstance(e, tpl_svc.TemplateError):
        return HTTPException(e.status_code, detail=e.payload)
    return HTTPException(400, detail={"error": str(e)})


class VariablesBody(BaseModel):
    variables: dict[str, str | int | float | None] = {}


@router.get("")
def list_templates(db: Session = Depends(get_db)):
    return {"templates": tpl_svc.list_templates(db)}


@router.get("/{template_id}")
def get_template(template_id: str, db: Session = Depends(get_db)):
    try:
        return tpl_svc.serialize_template_detail(tpl_svc.get_template_or_404(template_id, db))
    except tpl_svc.TemplateError as e:
        raise _map_err(e)


@router.post("/{template_id}/preview")
def preview_template(template_id: str, body: VariablesBody, db: Session = Depends(get_db)):
    try:
        return tpl_svc.preview_contract(template_id, db, variables=body.variables)
    except tpl_svc.TemplateError as e:
        raise _map_err(e)


@router.post("/{template_id}/create-contract", status_code=201)
def create_contract_from_template(
    template_id: str,
    body: VariablesBody,
    db: Session = Depends(get_db),
    role: str = Depends(demo_role),
):
    try:
        return tpl_svc.create_contract_from_template(template_id, db, variables=body.variables, actor=role)
    except tpl_svc.TemplateError as e:
        raise _map_err(e)
