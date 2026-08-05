"""Contract version control — immutable revision log."""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..ai.client import complete_json
from ..models import (
    ActivityEvent,
    ApprovalWorkflow,
    Contract,
    ContractVersion,
    Extraction,
    ReviewRequest,
    SignatureRequest,
    VersionComparison,
)
from .approvals import log_activity
from .storage import storage

ALLOWED_SOURCES = frozenset(
    {
        "initial_upload",
        "manual_upload",
        "negotiation_counter",
        "client_revision",
        "internal_revision",
        "approved",
        "signed",
    }
)

COMPARE_SCHEMA_VERSION = 2

_CHANGE_SECTION = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "items": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "items"],
    "additionalProperties": False,
}

_CLAUSE_ITEM = {
    "type": "object",
    "properties": {
        "clause_ref": {"type": "string"},
        "note": {"type": "string"},
    },
    "required": ["clause_ref", "note"],
    "additionalProperties": False,
}

COMPARE_SCHEMA = {
    "name": "version_compare_v2",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "executive_summary": {"type": "string"},
            "overall_risk_score": {"type": "integer"},
            "recommendation": {"type": "string"},
            "risk_changes": _CHANGE_SECTION,
            "financial_changes": _CHANGE_SECTION,
            "legal_changes": _CHANGE_SECTION,
            "liability_changes": _CHANGE_SECTION,
            "termination_changes": _CHANGE_SECTION,
            "confidentiality_changes": _CHANGE_SECTION,
            "timeline_changes": _CHANGE_SECTION,
            "payment_changes": _CHANGE_SECTION,
            "added_clauses": {"type": "array", "items": _CLAUSE_ITEM},
            "removed_clauses": {"type": "array", "items": _CLAUSE_ITEM},
            "modified_clauses": {"type": "array", "items": _CLAUSE_ITEM},
        },
        "required": [
            "executive_summary",
            "overall_risk_score",
            "recommendation",
            "risk_changes",
            "financial_changes",
            "legal_changes",
            "liability_changes",
            "termination_changes",
            "confidentiality_changes",
            "timeline_changes",
            "payment_changes",
            "added_clauses",
            "removed_clauses",
            "modified_clauses",
        ],
        "additionalProperties": False,
    },
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def current_version(contract_id, db: Session) -> ContractVersion | None:
    return (
        db.query(ContractVersion)
        .filter_by(contract_id=contract_id, is_current=True)
        .order_by(ContractVersion.version_number.desc())
        .first()
    )


def _next_version_number(contract_id, db: Session) -> int:
    max_num = db.query(func.max(ContractVersion.version_number)).filter_by(contract_id=contract_id).scalar()
    return int(max_num or 0) + 1


def _build_extracted_json(contract_id, db: Session) -> dict[str, Any]:
    rows = db.query(Extraction).filter_by(contract_id=contract_id).all()
    out: dict[str, Any] = {}
    for r in rows:
        out[r.field_name] = r.value_json
    return out


def _build_ai_summary(contract: Contract, extracted: dict) -> str:
    parts = [contract.title or "Contract"]
    if contract.party_a or contract.party_b:
        parts.append(f"{contract.party_a or '—'} / {contract.party_b or '—'}")
    if contract.value_sar:
        parts.append(f"Value SAR: {contract.value_sar}")
    return " · ".join(parts)


def sync_version_snapshot(contract_id, db: Session) -> ContractVersion | None:
    """After extraction, copy live extractions onto the current version row."""
    contract = db.get(Contract, contract_id)
    v = current_version(contract_id, db)
    if contract is None or v is None:
        return v
    extracted = _build_extracted_json(contract_id, db)
    v.extracted_json = extracted
    v.ai_summary = _build_ai_summary(contract, extracted)
    v.status = contract.status if contract.status in ("ready", "needs_review") else v.status
    if contract.file_url and not v.file_path:
        v.file_path = contract.file_url
    db.commit()
    db.refresh(v)
    return v


def log_version_activity(db: Session, contract_id, event_type: str, *, actor: str | None = None, metadata: dict | None = None):
    log_activity(db, contract_id, event_type, actor=actor, metadata=metadata)


def create_initial_version(contract: Contract, db: Session, *, actor: str = "system") -> ContractVersion:
    existing = db.query(ContractVersion).filter_by(contract_id=contract.id, version_number=1).first()
    if existing:
        return existing
    file_hash = None
    if contract.file_url:
        try:
            file_hash = _sha256(storage.get(contract.file_url))
        except Exception:
            pass
    v = ContractVersion(
        id=uuid.uuid4(),
        contract_id=contract.id,
        version_number=1,
        version_label="v1",
        source="initial_upload",
        status="processing",
        file_path=contract.file_url,
        hash_sha256=file_hash,
        is_current=True,
        created_by=actor,
        change_summary="Initial upload",
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    log_version_activity(db, contract.id, "version_created", actor=actor, metadata={"version_number": 1})
    return v


def stage_negotiation_snapshot(
    contract: Contract,
    current: ContractVersion,
    db: Session,
    *,
    actor: str,
    negotiation_id,
    change_summary: str,
) -> ContractVersion:
    """Stage a metadata-backed negotiation revision without committing."""
    current.is_current = False
    version = ContractVersion(
        id=uuid.uuid4(),
        contract_id=contract.id,
        version_number=_next_version_number(contract.id, db),
        version_label=None,
        parent_version_id=current.id,
        source="negotiation_counter",
        status="ready",
        change_summary=change_summary,
        file_path=current.file_path or contract.file_url,
        extracted_json=current.extracted_json,
        ai_summary=current.ai_summary,
        created_by=actor,
        negotiation_id=negotiation_id,
        hash_sha256=current.hash_sha256,
        is_current=True,
    )
    version.version_label = f"v{version.version_number}"
    db.add(version)
    log_version_activity(
        db,
        contract.id,
        "version_created",
        actor=actor,
        metadata={
            "version_id": str(version.id),
            "version_number": version.version_number,
            "source": version.source,
            "negotiation_id": str(negotiation_id),
        },
    )
    log_version_activity(
        db,
        contract.id,
        "current_version_changed",
        actor=actor,
        metadata={
            "from_version_id": str(current.id),
            "to_version_id": str(version.id),
            "from": current.version_number,
            "to": version.version_number,
            "negotiation_id": str(negotiation_id),
        },
    )
    return version


def create_new_version(
    contract_id,
    db: Session,
    *,
    source: str,
    actor: str,
    file_bytes: bytes,
    filename: str,
    change_summary: str | None = None,
    parent_version_id=None,
    make_current: bool = True,
    version_status: str | None = None,
    run_pipeline: bool = True,
    commit: bool = True,
) -> ContractVersion:
    if not commit and run_pipeline:
        raise ValueError("pipeline_requires_committed_version")
    if source not in ALLOWED_SOURCES:
        raise ValueError("invalid_source")
    contract = db.get(Contract, contract_id)
    if contract is None:
        raise ValueError("not_found")

    parent = current_version(contract_id, db)
    key = storage.save(file_bytes, filename)
    file_hash = _sha256(file_bytes)
    num = _next_version_number(contract_id, db)

    if parent and make_current:
        db.query(ContractVersion).filter_by(contract_id=contract_id, is_current=True).update({"is_current": False})

    status = version_status or "processing"
    v = ContractVersion(
        id=uuid.uuid4(),
        contract_id=contract_id,
        version_number=num,
        version_label=f"v{num}",
        parent_version_id=parent_version_id or (parent.id if parent else None),
        source=source,
        status=status,
        change_summary=change_summary,
        file_path=key,
        hash_sha256=file_hash,
        is_current=make_current,
        created_by=actor,
    )
    db.add(v)
    if make_current:
        contract.file_url = key
        contract.status = "processing"
    db.flush()

    if make_current and parent and parent.id != v.id:
        from .negotiation import supersede_version_negotiations

        supersede_version_negotiations(
            contract,
            parent.id,
            v.id,
            db,
            actor=actor,
        )

    log_version_activity(
        db,
        contract_id,
        "version_created",
        actor=actor,
        metadata={"version_number": num, "source": source},
    )
    if source == "negotiation_counter":
        log_version_activity(
            db,
            contract_id,
            "counter_version_created",
            actor=actor,
            metadata={"version_number": num, "source": source},
        )

    # The version row and its creation events commit together, before the
    # pipeline runs, so a later extraction failure cannot lose the audit trail.
    if commit:
        db.commit()
        db.refresh(v)

    if run_pipeline and make_current:
        from ..ai.pipeline import run_extraction

        run_extraction(contract_id, db)
        sync_version_snapshot(contract_id, db)
        db.refresh(v)
    return v


def set_current(version_id, db: Session, *, actor: str = "demo") -> ContractVersion:
    v = db.get(ContractVersion, version_id)
    if v is None:
        raise ValueError("not_found")
    contract = db.get(Contract, v.contract_id)
    if contract is None:
        raise ValueError("not_found")
    prior = current_version(v.contract_id, db)
    prior_num = prior.version_number if prior else None
    db.query(ContractVersion).filter_by(contract_id=v.contract_id, is_current=True).update({"is_current": False})
    v.is_current = True
    if v.file_path:
        contract.file_url = v.file_path
    log_version_activity(db, v.contract_id, "version_set_current", actor=actor, metadata={"version_number": v.version_number})
    if prior and prior.id != v.id:
        from .negotiation import supersede_version_negotiations

        supersede_version_negotiations(
            contract,
            prior.id,
            v.id,
            db,
            actor=actor,
        )
        log_version_activity(
            db,
            v.contract_id,
            "version_restored",
            actor=actor,
            metadata={"version_number": v.version_number},
        )
        log_version_activity(
            db,
            v.contract_id,
            "current_version_changed",
            actor=actor,
            metadata={"from": prior_num, "to": v.version_number},
        )
    db.commit()
    db.refresh(v)
    return v


def _workflow_status_for_version(version: ContractVersion, db: Session) -> dict[str, Any]:
    rr = (
        db.query(ReviewRequest)
        .filter_by(version_id=version.id)
        .order_by(ReviewRequest.created_at.desc())
        .first()
    )
    aw = (
        db.query(ApprovalWorkflow)
        .filter_by(version_id=version.id)
        .order_by(ApprovalWorkflow.created_at.desc())
        .first()
    )
    sr = (
        db.query(SignatureRequest)
        .filter_by(version_id=version.id)
        .order_by(SignatureRequest.created_at.desc())
        .first()
    )
    restored_by: str | None = None
    restored_at: str | None = None
    events = (
        db.query(ActivityEvent)
        .filter_by(contract_id=version.contract_id, event_type="version_restored")
        .order_by(ActivityEvent.created_at.desc())
        .all()
    )
    for ev in events:
        meta = ev.event_metadata or {}
        if meta.get("version_number") == version.version_number:
            restored_by = ev.actor
            restored_at = ev.created_at.isoformat() if ev.created_at else None
            break
    return {
        "review_status": rr.status if rr else None,
        "approval_status": aw.status if aw else None,
        "signature_status": sr.status if sr else None,
        "restored_by": restored_by,
        "restored_at": restored_at,
    }


def serialize_version(v: ContractVersion, db: Session | None = None) -> dict:
    out = {
        "id": str(v.id),
        "contract_id": str(v.contract_id),
        "version_number": v.version_number,
        "version_label": v.version_label or f"v{v.version_number}",
        "parent_version_id": str(v.parent_version_id) if v.parent_version_id else None,
        "source": v.source,
        "status": v.status,
        "change_summary": v.change_summary,
        "file_path": v.file_path,
        "ai_summary": v.ai_summary,
        "created_by": v.created_by,
        "hash_sha256": v.hash_sha256,
        "is_current": v.is_current,
        "created_at": v.created_at.isoformat() if v.created_at else None,
        "version_id": str(v.id),
        "extracted_json": v.extracted_json,
    }
    if db is not None:
        out.update(_workflow_status_for_version(v, db))
        from .version_lineage import enrich_version_fields

        out.update(enrich_version_fields(v, db))
    return out


def serialize_history(contract_id, db: Session) -> dict:
    rows = (
        db.query(ContractVersion)
        .filter_by(contract_id=contract_id)
        .order_by(ContractVersion.version_number.desc())
        .all()
    )
    cur = current_version(contract_id, db)
    return {
        "versions": [serialize_version(r, db) for r in rows],
        "current_version_number": cur.version_number if cur else None,
        "total_versions": len(rows),
    }


def is_stale_version(version_id, contract_id, db: Session) -> bool:
    if version_id is None:
        return False
    cur = current_version(contract_id, db)
    if cur is None:
        return False
    return str(version_id) != str(cur.id)


def is_stale_workflow(workflow, contract_id, db: Session) -> bool:
    vid = getattr(workflow, "version_id", None)
    return is_stale_version(vid, contract_id, db)


def _diff_json(a: dict | None, b: dict | None) -> dict:
    a = a or {}
    b = b or {}
    keys = set(a.keys()) | set(b.keys())
    added, removed, modified = [], [], []
    for k in sorted(keys):
        if k not in a:
            added.append(k)
        elif k not in b:
            removed.append(k)
        elif json.dumps(a[k], sort_keys=True, default=str) != json.dumps(b[k], sort_keys=True, default=str):
            modified.append(k)
    return {
        "added_fields": added,
        "removed_fields": removed,
        "modified_fields": modified,
        "added_clauses": [],
        "removed_clauses": [],
        "modified_clauses": modified,
        "changed_obligations": "obligations" in modified,
        "changed_payment": "payment_milestones" in modified,
        "changed_liability": any(x in modified for x in ("penalties", "retention_pct")),
        "changed_termination": "notice_periods" in modified,
        "changed_governing_law": "governing_law" in modified,
        "changed_confidentiality": False,
        "changed_deadlines": any(x in modified for x in ("start_date", "end_date", "bond_expiry", "warranty_end")),
    }


def _empty_section() -> dict:
    return {"summary": "No significant changes detected.", "items": []}


def _section_from_fields(changed: bool, fields: list[str], *, label: str, from_num: int, to_num: int) -> dict:
    if not changed or not fields:
        return _empty_section()
    return {
        "summary": f"{label} changed between v{from_num} and v{to_num}.",
        "items": fields[:8],
    }


def _fallback_rich(diff: dict, from_num: int, to_num: int) -> dict:
    added = diff.get("added_fields") or []
    removed = diff.get("removed_fields") or []
    modified = diff.get("modified_fields") or []
    score = min(100, 15 + len(modified) * 10 + len(added) * 6 + len(removed) * 6)
    if diff.get("changed_liability") or diff.get("changed_payment"):
        score = min(100, score + 15)
    return {
        "executive_summary": (
            f"Version {from_num} and version {to_num} differ in {len(modified)} field(s), "
            f"{len(added)} added, {len(removed)} removed."
        ),
        "overall_risk_score": score,
        "recommendation": "Review modified extraction fields and re-run approval on the current version if material.",
        "risk_changes": _section_from_fields(bool(modified), modified, label="Risk-related fields", from_num=from_num, to_num=to_num),
        "financial_changes": _section_from_fields(
            diff.get("changed_payment"), [f for f in modified if "payment" in f or "value" in f],
            label="Financial terms", from_num=from_num, to_num=to_num,
        ),
        "legal_changes": _section_from_fields(
            diff.get("changed_governing_law"), [f for f in modified if "law" in f or "jurisdiction" in f],
            label="Legal terms", from_num=from_num, to_num=to_num,
        ),
        "liability_changes": _section_from_fields(
            diff.get("changed_liability"), [f for f in modified if "penalt" in f or "retention" in f],
            label="Liability", from_num=from_num, to_num=to_num,
        ),
        "termination_changes": _section_from_fields(
            diff.get("changed_termination"), [f for f in modified if "notice" in f or "termin" in f],
            label="Termination", from_num=from_num, to_num=to_num,
        ),
        "confidentiality_changes": _section_from_fields(
            diff.get("changed_confidentiality"), [], label="Confidentiality", from_num=from_num, to_num=to_num,
        ),
        "timeline_changes": _section_from_fields(
            diff.get("changed_deadlines"), [f for f in modified if "date" in f or "deadline" in f],
            label="Timeline", from_num=from_num, to_num=to_num,
        ),
        "payment_changes": _section_from_fields(
            diff.get("changed_payment"), [f for f in modified if "payment" in f or "milestone" in f],
            label="Payment", from_num=from_num, to_num=to_num,
        ),
        "added_clauses": [{"clause_ref": f, "note": "New field in later version."} for f in added[:10]],
        "removed_clauses": [{"clause_ref": f, "note": "Removed from later version."} for f in removed[:10]],
        "modified_clauses": [{"clause_ref": f, "note": "Value changed between versions."} for f in modified[:10]],
    }


def _derived_flags(diff: dict) -> dict:
    keys = (
        "changed_obligations",
        "changed_payment",
        "changed_liability",
        "changed_termination",
        "changed_governing_law",
        "changed_confidentiality",
        "changed_deadlines",
    )
    return {k: diff.get(k) for k in keys}


def _build_compare_payload(diff: dict, rich: dict) -> dict:
    payload = dict(diff)
    payload["schema_version"] = COMPARE_SCHEMA_VERSION
    payload["rich"] = rich
    payload["derived_flags"] = _derived_flags(diff)
    return payload


def _compare_response(fv, tv, payload: dict, ai_explanation: str, *, cached: bool) -> dict:
    return {
        "from_version_id": str(fv.id),
        "to_version_id": str(tv.id),
        "from_version_number": fv.version_number,
        "to_version_number": tv.version_number,
        "from_extracted_json": fv.extracted_json,
        "to_extracted_json": tv.extracted_json,
        "diff": payload,
        "ai_explanation": ai_explanation,
        "cached": cached,
    }


def compare_versions(contract_id, from_id, to_id, db: Session) -> dict:
    fv = db.get(ContractVersion, from_id)
    tv = db.get(ContractVersion, to_id)
    if fv is None or tv is None or fv.contract_id != contract_id or tv.contract_id != contract_id:
        raise ValueError("not_found")

    cached = (
        db.query(VersionComparison)
        .filter_by(from_version_id=from_id, to_version_id=to_id)
        .first()
    )
    if cached and cached.diff_json is not None and cached.diff_json.get("schema_version") == COMPARE_SCHEMA_VERSION:
        return _compare_response(fv, tv, cached.diff_json, cached.ai_explanation or "", cached=True)

    base_diff = _diff_json(fv.extracted_json, tv.extracted_json)
    prompt = (
        f"Compare contract version {fv.version_number} to version {tv.version_number}. "
        f"Structural diff: {json.dumps(base_diff, default=str)[:4000]}. "
        f"Populate all rubric sections. Cite both version numbers."
    )
    rich = _fallback_rich(base_diff, fv.version_number, tv.version_number)
    try:
        raw = complete_json(
            "You explain contract version differences for legal reviewers.",
            prompt,
            COMPARE_SCHEMA,
        )
        if raw.get("executive_summary"):
            rich = raw
    except Exception:
        pass

    payload = _build_compare_payload(base_diff, rich)
    ai_text = rich.get("executive_summary") or "AI comparison unavailable."

    if cached:
        cached.diff_json = payload
        cached.ai_explanation = ai_text
    else:
        row = VersionComparison(
            id=uuid.uuid4(),
            contract_id=contract_id,
            from_version_id=from_id,
            to_version_id=to_id,
            diff_json=payload,
            ai_explanation=ai_text,
        )
        db.add(row)
    db.commit()
    log_version_activity(
        db,
        contract_id,
        "version_compared",
        metadata={"from": fv.version_number, "to": tv.version_number},
    )
    log_version_activity(
        db,
        contract_id,
        "ai_comparison_generated",
        metadata={"from": fv.version_number, "to": tv.version_number},
    )
    return _compare_response(fv, tv, payload, ai_text, cached=False)


def stamp_version_id(entity, contract_id, db: Session) -> None:
    cur = current_version(contract_id, db)
    if cur and getattr(entity, "version_id", None) is None:
        entity.version_id = cur.id


def mark_version_approved(contract_id, workflow_id, db: Session, *, commit: bool = True) -> None:
    w = db.get(ApprovalWorkflow, workflow_id)
    v = current_version(contract_id, db)
    if v:
        v.status = "approved"
        v.approval_workflow_id = workflow_id
        if w:
            w.version_id = v.id
        if commit:
            db.commit()
        log_version_activity(
            db,
            contract_id,
            "version_approved",
            metadata={"version_number": v.version_number, "workflow_id": str(workflow_id)},
        )


def mark_version_signed(contract_id, signature_request_id, db: Session, *, commit: bool = True) -> None:
    v = current_version(contract_id, db)
    if v:
        v.status = "signed"
        v.signature_request_id = signature_request_id
        if commit:
            db.commit()
        log_version_activity(
            db,
            contract_id,
            "version_signed",
            metadata={"version_number": v.version_number, "signature_request_id": str(signature_request_id)},
        )
