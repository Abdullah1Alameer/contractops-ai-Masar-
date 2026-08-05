"""Contract version APIs."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import demo_role
from ..services import versions as ver_svc
from ..services.storage import storage

router = APIRouter(tags=["versions"])


@router.get("/contracts/{contract_id}/versions")
def list_versions(contract_id: uuid.UUID, db: Session = Depends(get_db)):
    return ver_svc.serialize_history(contract_id, db)


@router.get("/contracts/{contract_id}/versions/lineage")
def version_lineage(contract_id: uuid.UUID, db: Session = Depends(get_db)):
    from ..models import Contract
    from ..services import version_lineage as lineage_svc

    if db.get(Contract, contract_id) is None:
        raise HTTPException(404, detail={"error": "not_found"})
    return lineage_svc.build_lineage(contract_id, db)


@router.get("/contracts/{contract_id}/versions/compare")
def compare(contract_id: uuid.UUID, from_id: uuid.UUID, to_id: uuid.UUID, db: Session = Depends(get_db)):
    try:
        return ver_svc.compare_versions(contract_id, from_id, to_id, db)
    except ValueError as e:
        if str(e) == "not_found":
            raise HTTPException(404, detail={"error": "not_found"})
        raise HTTPException(400, detail={"error": str(e)})


@router.post("/contracts/{contract_id}/versions", status_code=201)
async def upload_version(
    contract_id: uuid.UUID,
    file: UploadFile = File(...),
    source: str = Form(default="manual_upload"),
    change_summary: str | None = Form(default=None),
    parent_version_id: str | None = Form(default=None),
    db: Session = Depends(get_db),
    role: str = Depends(demo_role),
):
    data = await file.read()
    filename = file.filename or "contract.pdf"
    try:
        pid = uuid.UUID(parent_version_id) if parent_version_id else None
        v = ver_svc.create_new_version(
            contract_id,
            db,
            source=source,
            actor=role,
            file_bytes=data,
            filename=filename,
            change_summary=change_summary,
            parent_version_id=pid,
        )
        return ver_svc.serialize_version(v, db)
    except ValueError as e:
        code = str(e)
        if code == "not_found":
            raise HTTPException(404, detail={"error": code})
        raise HTTPException(400, detail={"error": code})


@router.post("/versions/{version_id}/set-current")
def set_current(version_id: uuid.UUID, db: Session = Depends(get_db), role: str = Depends(demo_role)):
    try:
        v = ver_svc.set_current(version_id, db, actor=role)
        return ver_svc.serialize_version(v, db)
    except ValueError as e:
        raise HTTPException(404, detail={"error": str(e)})


@router.post("/versions/{version_id}/extract")
def extract_version(version_id: uuid.UUID, db: Session = Depends(get_db)):
    from ..models import Contract, ContractVersion

    v = db.get(ContractVersion, version_id)
    if v is None:
        raise HTTPException(404, detail={"error": "not_found"})
    contract = db.get(Contract, v.contract_id)
    if contract and v.file_path:
        contract.file_url = v.file_path
        db.commit()
    from ..ai.pipeline import run_extraction

    run_extraction(v.contract_id, db)
    ver_svc.sync_version_snapshot(v.contract_id, db)
    return {"ok": True}


@router.get("/versions/{version_id}/download")
def download_version(version_id: uuid.UUID, db: Session = Depends(get_db)):
    from ..models import ContractVersion

    v = db.get(ContractVersion, version_id)
    if v is None or not v.file_path:
        raise HTTPException(404, detail={"error": "not_found"})
    data = storage.get(v.file_path)
    return Response(content=data, media_type="application/pdf")
