"""F1 endpoints — fully implemented. This API surface is FROZEN for teammates."""
import re
import uuid as _uuid

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from ..ai.client import AIError
from ..ai.pipeline import run_extraction
from ..config import MAX_UPLOAD_MB
from ..db import get_db
from ..models import Clause, Contract, Extraction, Obligation
from ..services.storage import storage
from ..services.textextract import TextExtractError, extract_pages

router = APIRouter(prefix="/contracts", tags=["contracts"])

_PAGE_MARKER = re.compile(r"\n\[\[PAGE (\d+)\]\]\n")


def _num(v):
    return float(v) if v is not None else None


def _iso(d):
    return d.isoformat() if d else None


def _clause_dict(c: Clause | None):
    if c is None:
        return None
    return {
        "id": str(c.id),
        "clause_ref": c.clause_ref,
        "quote": c.quote,
        "page": c.page,
        "char_start": c.char_start,
        "char_end": c.char_end,
    }


@router.post("", status_code=201)
async def upload_contract(
    file: UploadFile,
    type: str | None = Form(default=None),
    parent_main_contract_id: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    if type is not None and type not in ("main", "subcontract"):
        raise HTTPException(422, detail={"error": "invalid_contract_type"})
    data = await file.read()
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, detail={"error": "file_too_large", "max_mb": MAX_UPLOAD_MB})
    filename = file.filename or "contract"
    if not filename.lower().endswith((".pdf", ".docx")):
        raise HTTPException(400, detail={"error": "unsupported_type"})

    # validate the text layer up-front so scanned/corrupted files fail fast
    try:
        extract_pages(data, filename)
    except TextExtractError as e:
        if e.code == "scanned_pdf_not_supported":
            raise HTTPException(400, detail={"error": "scanned_pdf_not_supported"})
        if e.code == "unsupported_type":
            raise HTTPException(400, detail={"error": "unsupported_type"})
        raise HTTPException(422, detail={"error": "corrupted_file"})

    key = storage.save(data, filename)
    contract = Contract(
        id=_uuid.uuid4(),
        title=re.sub(r"\.(pdf|docx)$", "", filename, flags=re.I),
        type=type,
        parent_main_contract_id=_uuid.UUID(parent_main_contract_id) if parent_main_contract_id else None,
        file_url=key,
        status="processing",
    )
    db.add(contract)
    db.commit()
    # client calls POST /contracts/{id}/extract next (no queues in the demo)
    return {"id": str(contract.id), "status": contract.status}


@router.post("/{contract_id}/extract")
def extract_contract(contract_id: _uuid.UUID, db: Session = Depends(get_db)):
    contract = db.get(Contract, contract_id)
    if contract is None:
        raise HTTPException(404, detail={"error": "not_found"})
    try:
        return run_extraction(contract_id, db)
    except TextExtractError as e:
        db.rollback()
        contract = db.get(Contract, contract_id)
        contract.status = "failed"
        db.commit()
        raise HTTPException(400, detail={"error": e.code})
    except AIError:
        db.rollback()
        contract = db.get(Contract, contract_id)
        contract.status = "failed"
        db.commit()
        raise HTTPException(502, detail={"error": "ai_failed", "retryable": True})


@router.get("")
def list_contracts(db: Session = Depends(get_db)):
    counts = (
        db.query(
            Obligation.contract_id,
            func.sum(case((Obligation.status == "pending", 1), else_=0)).label("pending"),
            func.sum(case((Obligation.status == "overdue", 1), else_=0)).label("overdue"),
        )
        .group_by(Obligation.contract_id)
        .all()
    )
    by_contract = {row.contract_id: {"pending": int(row.pending), "overdue": int(row.overdue)} for row in counts}
    out = []
    for c in db.query(Contract).order_by(Contract.created_at.desc()).all():
        out.append({
            "id": str(c.id),
            "title": c.title,
            "type": c.type,
            "contract_category": c.contract_category,
            "supported": c.supported,
            "classification_confidence": _num(c.classification_confidence),
            "party_b": c.party_b,
            "value_sar": _num(c.value_sar),
            "status": c.status,
            "obligation_counts": by_contract.get(c.id, {"pending": 0, "overdue": 0}),
        })
    return out


@router.get("/{contract_id}")
def get_contract(contract_id: _uuid.UUID, db: Session = Depends(get_db)):
    c = db.get(Contract, contract_id)
    if c is None:
        raise HTTPException(404, detail={"error": "not_found"})
    clauses = {cl.id: cl for cl in db.query(Clause).filter_by(contract_id=c.id)}
    extractions = []
    for e in db.query(Extraction).filter_by(contract_id=c.id):
        extractions.append({
            "field_name": e.field_name,
            "value_json": e.value_json,
            "confidence": _num(e.confidence),
            "status": e.status,
            "clause": _clause_dict(clauses.get(e.clause_id)),
        })
    return {
        "id": str(c.id),
        "title": c.title,
        "type": c.type,
        "parent_main_contract_id": str(c.parent_main_contract_id) if c.parent_main_contract_id else None,
        "party_a": c.party_a,
        "party_b": c.party_b,
        "value_sar": _num(c.value_sar),
        "start_date": _iso(c.start_date),
        "end_date": _iso(c.end_date),
        "governing_law": c.governing_law,
        "retention_pct": _num(c.retention_pct),
        "bond_expiry": _iso(c.bond_expiry),
        "warranty_end": _iso(c.warranty_end),
        "language": c.language,
        "calendar": c.calendar,
        "status": c.status,
        "contract_category": c.contract_category,
        "supported": c.supported,
        "classification_confidence": _num(c.classification_confidence),
        "classification_message": c.classification_message,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "extractions": extractions,
    }


@router.get("/{contract_id}/obligations")
def get_obligations(contract_id: _uuid.UUID, db: Session = Depends(get_db)):
    clauses = {cl.id: cl for cl in db.query(Clause).filter_by(contract_id=contract_id)}
    # confidence per obligation lives in the 'obligations' extraction row items
    extr = db.query(Extraction).filter_by(contract_id=contract_id, field_name="obligations").first()
    conf_by_clause = {}
    if extr and isinstance(extr.value_json, list):
        for item in extr.value_json:
            if item.get("clause_id"):
                conf_by_clause[item["clause_id"]] = item.get("confidence")
    out = []
    for o in db.query(Obligation).filter_by(contract_id=contract_id).order_by(Obligation.due_date.asc().nullslast()):
        clause = clauses.get(o.source_clause_id)
        out.append({
            "id": str(o.id),
            "description": o.description,
            "responsible_party": o.responsible_party,
            "due_date": _iso(o.due_date),
            "penalty_text": o.penalty_text,
            "reminder_days_before": o.reminder_days_before,
            "status": o.status,
            "source": {
                "clause_ref": clause.clause_ref,
                "quote": clause.quote,
                "page": clause.page,
                "char_start": clause.char_start,
                "char_end": clause.char_end,
            } if clause else None,
            "confidence": conf_by_clause.get(str(o.source_clause_id)) if o.source_clause_id else None,
        })
    return out


@router.delete("/{contract_id}", status_code=204)
def delete_contract(contract_id: _uuid.UUID, db: Session = Depends(get_db)):
    c = db.get(Contract, contract_id)
    if c is None:
        raise HTTPException(404, detail={"error": "not_found"})
    # Nullify any subcontracts that pointed at this main contract (no ON DELETE clause on the FK).
    db.query(Contract).filter(Contract.parent_main_contract_id == c.id).update(
        {Contract.parent_main_contract_id: None}
    )
    file_key = c.file_url
    db.delete(c)  # clauses/extractions/obligations/deadlines/... cascade via FK
    db.commit()
    storage.delete(file_key)
    return None


@router.get("/{contract_id}/raw")
def get_raw_page(contract_id: _uuid.UUID, page: int = 1, db: Session = Depends(get_db)):
    c = db.get(Contract, contract_id)
    if c is None or not c.raw_text:
        raise HTTPException(404, detail={"error": "not_found"})
    markers = list(_PAGE_MARKER.finditer(c.raw_text))
    for i, m in enumerate(markers):
        if int(m.group(1)) == page:
            start = m.end()
            end = markers[i + 1].start() if i + 1 < len(markers) else len(c.raw_text)
            # char_start = global offset in raw_text where the returned text begins,
            # so the viewer can map clause offsets: rel = clause.char_start - char_start
            return {"page": page, "text": c.raw_text[start:end], "char_start": start, "total_pages": len(markers)}
    raise HTTPException(404, detail={"error": "page_not_found"})
