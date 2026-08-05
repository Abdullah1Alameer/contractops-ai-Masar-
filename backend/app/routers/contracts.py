"""F1 endpoints — fully implemented. This API surface is FROZEN for teammates."""
import re
import uuid as _uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import case, func
from sqlalchemy.orm import Session, defer

from ..ai.client import AIError
from ..ai.pipeline import run_extraction
from ..config import MAX_UPLOAD_MB
from ..db import get_db
from ..models import Clause, Contract, Extraction, Obligation
from ..services.dashboard import workflow_summaries_by_contract
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
        if e.code in {"empty_document", "no_meaningful_text", "encrypted_or_unsupported_docx"}:
            raise HTTPException(400, detail={"error": e.code})
        if e.code == "extraction_failed":
            raise HTTPException(500, detail={"error": "extraction_failed"})
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
    db.refresh(contract)
    from ..services.versions import create_initial_version

    create_initial_version(contract, db, actor="upload")
    # client calls POST /contracts/{id}/extract next (no queues in the demo)
    return {"id": str(contract.id), "status": contract.status}


@router.post("/{contract_id}/extract")
def extract_contract(
    contract_id: _uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    contract = db.get(Contract, contract_id)
    if contract is None:
        raise HTTPException(404, detail={"error": "not_found"})
    try:
        result = run_extraction(contract_id, db)
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
    if result.get("supported") is not False:
        from ..services.summary import schedule_summary_generation

        background_tasks.add_task(schedule_summary_generation, contract_id)
    return result


class ReclassifyBody(BaseModel):
    contract_category: str = Field(min_length=1, max_length=120)
    actor: str = Field(default="user", max_length=120)


@router.post("/{contract_id}/reclassify")
def reclassify_contract(contract_id: _uuid.UUID, body: ReclassifyBody, db: Session = Depends(get_db)):
    from ..ai.classifier import SUPPORTED_SET

    contract = db.get(Contract, contract_id)
    if contract is None:
        raise HTTPException(404, detail={"error": "not_found"})
    if body.contract_category not in SUPPORTED_SET:
        raise HTTPException(422, detail={"error": "invalid_category"})
    prior = contract.contract_category
    contract.contract_category = body.contract_category
    contract.supported = True
    contract.classification_confidence = None
    contract.classification_message = None
    contract.status = "processing"
    db.commit()
    from ..services.approvals import log_activity

    log_activity(
        db,
        contract.id,
        "contract_reclassified",
        actor=body.actor,
        metadata={"from": prior, "to": body.contract_category},
    )
    db.commit()
    try:
        result = run_extraction(contract_id, db)
    except Exception:
        db.rollback()
        raise
    return {"reclassified": True, "from": prior, "to": body.contract_category, "extraction": result}


@router.get("")
def list_contracts(
    include: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
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
    include_set = {p.strip() for p in (include or "").split(",") if p.strip()}
    wf_map = workflow_summaries_by_contract(db) if "workflow_summary" in include_set else {}

    from ..models import ContractVersion
    from ..services.versions import serialize_version

    contract_rows = (
        db.query(Contract)
        .options(defer(Contract.raw_text))
        .order_by(Contract.created_at.desc())
        .all()
    )
    contract_ids = [c.id for c in contract_rows]

    # Bulk version stats (total + current version number) in a single query.
    version_stats: dict = {}
    if contract_ids:
        totals = (
            db.query(
                ContractVersion.contract_id,
                func.count(ContractVersion.id).label("total"),
                func.max(ContractVersion.version_number).label("max_num"),
            )
            .filter(ContractVersion.contract_id.in_(contract_ids))
            .group_by(ContractVersion.contract_id)
            .all()
        )
        cur_rows = (
            db.query(ContractVersion.contract_id, ContractVersion.version_number)
            .filter(
                ContractVersion.contract_id.in_(contract_ids),
                ContractVersion.is_current.is_(True),
            )
            .all()
        )
        cur_map = {row.contract_id: row.version_number for row in cur_rows}
        for cid, total, max_num in totals:
            version_stats[cid] = {
                "total_versions": int(total or 0),
                "current_version_number": cur_map.get(cid, max_num),
            }

    current_versions_map: dict = {}
    if "current_version" in include_set and contract_ids:
        rows = (
            db.query(ContractVersion)
            .filter(
                ContractVersion.contract_id.in_(contract_ids),
                ContractVersion.is_current.is_(True),
            )
            .all()
        )
        current_versions_map = {row.contract_id: row for row in rows}

    out = []
    for c in contract_rows:
        vs = version_stats.get(c.id, {"total_versions": 0, "current_version_number": None})
        row = {
            "id": str(c.id),
            "title": c.title,
            "type": c.type,
            "relationship_type": c.relationship_type,
            "contract_category": c.contract_category,
            "supported": c.supported,
            "classification_confidence": _num(c.classification_confidence),
            "party_b": c.party_b,
            "value_sar": _num(c.value_sar),
            "end_date": c.end_date.isoformat() if c.end_date else None,
            "status": c.status,
            "stage": c.stage or "negotiation",
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "current_version_number": vs["current_version_number"],
            "total_versions": vs["total_versions"],
            "obligation_counts": by_contract.get(c.id, {"pending": 0, "overdue": 0}),
        }
        if "workflow_summary" in include_set:
            row["workflow_summary"] = wf_map.get(c.id, {
                "review_status": None,
                "negotiation_status": None,
                "approval_status": None,
                "signature_status": None,
            })
        if "current_version" in include_set:
            cur = current_versions_map.get(c.id)
            row["current_version"] = serialize_version(cur, db) if cur else None
        out.append(row)
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
    from ..services.versions import serialize_history
    from ..services.date_semantics import sync_contract_date_semantics
    from ..services.risk_engine import serialize_risk

    sync_contract_date_semantics(c, db)
    db.commit()
    risk = serialize_risk(c.id, db)
    hist = serialize_history(c.id, db)
    from ..services.summary import serialize_summary

    summary = serialize_summary(c, db)
    return {
        "id": str(c.id),
        "title": c.title,
        "type": c.type,
        "relationship_type": c.relationship_type,
        "parent_main_contract_id": str(c.parent_main_contract_id) if c.parent_main_contract_id else None,
        "party_a": c.party_a,
        "party_b": c.party_b,
        "value_sar": _num(c.value_sar),
        "start_date": _iso(c.start_date),
        "end_date": _iso(c.end_date),
        "execution_date": _iso(c.execution_date),
        "commencement_date": _iso(c.commencement_date),
        "date_facts": c.date_facts,
        "risk": risk,
        "governing_law": c.governing_law,
        "retention_pct": _num(c.retention_pct),
        "bond_expiry": _iso(c.bond_expiry),
        "warranty_end": _iso(c.warranty_end),
        "language": c.language,
        "calendar": c.calendar,
        "status": c.status,
        "stage": c.stage or "negotiation",
        "contract_category": c.contract_category,
        "supported": c.supported,
        "classification_confidence": _num(c.classification_confidence),
        "classification_message": c.classification_message,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "current_version_number": hist["current_version_number"],
        "total_versions": hist["total_versions"],
        "extractions": extractions,
        "summary_status": summary["status"],
        "summary_is_stale": summary.get("is_stale", False),
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
            "title": o.title,
            "description": o.description,
            "responsible_party": o.responsible_party,
            "beneficiary": o.beneficiary,
            "trigger_type": o.trigger_type,
            "trigger_event": o.trigger_event,
            "temporal_rule": o.temporal_rule,
            "dependencies": o.dependencies or [],
            "contract_required_evidence": o.contract_required_evidence or [],
            "suggested_evidence": o.suggested_evidence or [],
            "completion_criteria": o.completion_criteria,
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


class IntelligenceRebuildBody(BaseModel):
    targets: list[str] | None = None


@router.post("/{contract_id}/intelligence/rebuild")
def rebuild_contract_intelligence(
    contract_id: _uuid.UUID,
    body: IntelligenceRebuildBody,
    db: Session = Depends(get_db),
):
    c = db.get(Contract, contract_id)
    if c is None:
        raise HTTPException(404, detail={"error": "not_found"})
    if c.status not in ("ready", "needs_review"):
        raise HTTPException(409, detail={"error": "extraction_not_complete", "status": c.status})
    from ..services.intelligence import rebuild_intelligence

    try:
        summary = rebuild_intelligence(contract_id, db, body.targets)
    except ValueError as e:
        code = str(e)
        if code == "contract_not_found":
            raise HTTPException(404, detail={"error": "not_found"})
        if code == "invalid_targets":
            raise HTTPException(400, detail={"error": "invalid_targets"})
        raise
    return summary


@router.get("/{contract_id}/risk")
def get_contract_risk(contract_id: _uuid.UUID, db: Session = Depends(get_db)):
    c = db.get(Contract, contract_id)
    if c is None:
        raise HTTPException(404, detail={"error": "not_found"})
    from ..services.risk_engine import serialize_risk

    return serialize_risk(contract_id, db)


@router.get("/{contract_id}/negotiation-opportunities")
def get_negotiation_opportunities(contract_id: _uuid.UUID, db: Session = Depends(get_db)):
    c = db.get(Contract, contract_id)
    if c is None:
        raise HTTPException(404, detail={"error": "not_found"})
    from ..services.negotiation_opportunities import list_negotiation_opportunities

    return {"opportunities": list_negotiation_opportunities(contract_id, db)}


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


@router.get("/{contract_id}/file")
def get_contract_file(contract_id: _uuid.UUID, db: Session = Depends(get_db)):
    c = db.get(Contract, contract_id)
    if c is None or not c.file_url:
        raise HTTPException(404, detail={"error": "not_found"})
    try:
        data = storage.get(c.file_url)
    except FileNotFoundError:
        raise HTTPException(404, detail={"error": "not_found"})
    key = c.file_url.lower()
    if key.endswith(".pdf"):
        media = "application/pdf"
    elif key.endswith(".docx"):
        media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        media = "application/octet-stream"
    return Response(content=data, media_type=media, headers={"Content-Disposition": "inline"})


class SummaryGenerateBody(BaseModel):
    force: bool = False


@router.get("/{contract_id}/summary")
def get_contract_summary(contract_id: _uuid.UUID, db: Session = Depends(get_db)):
    c = db.get(Contract, contract_id)
    if c is None:
        raise HTTPException(404, detail={"error": "not_found"})
    from ..services.summary import serialize_summary

    return serialize_summary(c, db)


@router.post("/{contract_id}/summary/generate", status_code=202)
def generate_contract_summary(
    contract_id: _uuid.UUID,
    body: SummaryGenerateBody,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    c = db.get(Contract, contract_id)
    if c is None:
        raise HTTPException(404, detail={"error": "not_found"})
    from ..services.summary import get_or_create_row, schedule_summary_generation, source_hash

    row = get_or_create_row(contract_id, db)
    h = source_hash(c)
    if not body.force and row.status == "ready" and row.source_hash == h:
        return {"status": "ready", "contract_id": str(contract_id)}
    if row.status == "generating" and not body.force:
        return {"status": "generating", "contract_id": str(contract_id)}
    row.status = "generating"
    row.error_code = None
    row.error_detail = None
    db.commit()
    background_tasks.add_task(schedule_summary_generation, contract_id, body.force)
    return {"status": "generating", "contract_id": str(contract_id)}


@router.post("/{contract_id}/reextract-text")
def reextract_contract_text(contract_id: _uuid.UUID, db: Session = Depends(get_db)):
    c = db.get(Contract, contract_id)
    if c is None:
        raise HTTPException(404, detail={"error": "not_found"})
    from ..services.summary import reextract_and_reanchor

    try:
        return reextract_and_reanchor(contract_id, db)
    except ValueError as e:
        code = str(e)
        if code == "contract_not_found":
            raise HTTPException(404, detail={"error": "not_found"})
        if code == "no_file":
            raise HTTPException(404, detail={"error": "no_file"})
        raise


@router.get("/{contract_id}/raw")
def get_raw_page(contract_id: _uuid.UUID, page: int = 1, db: Session = Depends(get_db)):
    c = db.get(Contract, contract_id)
    if c is None or not c.raw_text:
        raise HTTPException(404, detail={"error": "not_found"})
    markers = list(_PAGE_MARKER.finditer(c.raw_text))
    layout_page = None
    if c.page_layout:
        for pg in c.page_layout:
            if pg.get("page") == page:
                layout_page = pg
                break
    for i, m in enumerate(markers):
        if int(m.group(1)) == page:
            start = m.end()
            end = markers[i + 1].start() if i + 1 < len(markers) else len(c.raw_text)
            payload = {
                "page": page,
                "text": c.raw_text[start:end],
                "char_start": start,
                "total_pages": len(markers),
                "blocks": (layout_page or {}).get("blocks") or [],
                "width": (layout_page or {}).get("width"),
                "height": (layout_page or {}).get("height"),
                "file_type": "pdf" if (c.file_url or "").lower().endswith(".pdf") else "docx",
            }
            return payload
    raise HTTPException(404, detail={"error": "page_not_found"})
