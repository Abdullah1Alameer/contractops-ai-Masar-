"""Persisted bilingual executive summary generation."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..ai.client import AIError, complete_json
from ..ai.summary_prompt import (
    PROMPT_VERSION,
    SECTION_KEYS,
    SUMMARY_SCHEMA,
    SUMMARY_SYSTEM,
    build_summary_user_prompt,
)
from ..config import AI_MODEL
from ..models import Clause, Contract, ContractSummary, Extraction

_MAX_EXCERPT = 120_000


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def source_hash(contract: Contract) -> str:
    layout = contract.page_layout if contract.page_layout is not None else []
    payload = (contract.raw_text or "") + "\n" + json.dumps(layout, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _structured_hints(contract_id, db: Session) -> str:
    lines: list[str] = []
    c = db.get(Contract, contract_id)
    if c:
        lines.append(f"parties: {c.party_a or '—'} / {c.party_b or '—'}")
        lines.append(f"value_sar: {c.value_sar}")
        lines.append(f"start: {c.start_date} end: {c.end_date}")
    for field in ("notice_periods", "payment_milestones", "obligations", "penalties"):
        row = db.query(Extraction).filter_by(contract_id=contract_id, field_name=field).first()
        if row and row.value_json is not None:
            lines.append(f"{field}: {json.dumps(row.value_json, ensure_ascii=False)[:8000]}")
    return "\n".join(lines)


def _quote_in_raw(raw: str, quote: str) -> bool:
    if not quote or not raw:
        return False
    q = quote.strip()
    if len(q) < 8:
        return q in raw
    return q in raw


def _verify_sections(raw: str, payload: dict) -> tuple[dict, dict]:
    """Drop citations whose quote cannot be located in raw_text. Returns (ar, en) section trees."""
    ar_out: dict = {}
    en_out: dict = {}
    for key in SECTION_KEYS:
        sec = payload.get(key) or {}
        status = sec.get("status") or "not_stated"
        ar_sec = {"status": status, "overview": sec.get("overview_ar") or "", "items": []}
        en_sec = {"status": status, "overview": sec.get("overview_en") or "", "items": []}
        for item in sec.get("items") or []:
            citations = []
            for cit in item.get("citations") or []:
                quote = (cit.get("quote") or "").strip()
                if _quote_in_raw(raw, quote):
                    citations.append(
                        {
                            "clause_ref": cit.get("clause_ref") or "",
                            "page": int(cit.get("page") or 1),
                            "quote": quote,
                        }
                    )
            ar_sec["items"].append(
                {"text": item.get("text_ar") or "", "citations": citations}
            )
            en_sec["items"].append(
                {"text": item.get("text_en") or "", "citations": citations}
            )
        ar_out[key] = ar_sec
        en_out[key] = en_sec
    return ar_out, en_out


def _safe_error(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, AIError):
        return "ai_failed", "Summary generation failed. Retry later."
    msg = str(exc).lower()
    if "api key" in msg or "authentication" in msg or "rate limit" in msg:
        return "provider_unavailable", "AI provider is temporarily unavailable."
    return "ai_failed", "Summary generation failed. Retry later."


def get_or_create_row(contract_id, db: Session) -> ContractSummary:
    row = db.get(ContractSummary, contract_id)
    if row is None:
        row = ContractSummary(contract_id=contract_id, status="not_generated")
        db.add(row)
        db.flush()
    return row


def serialize_summary(contract: Contract, db: Session) -> dict:
    row = db.get(ContractSummary, contract.id)
    current_hash = source_hash(contract)
    if row is None:
        return {
            "status": "not_generated",
            "summary_ar": None,
            "summary_en": None,
            "error_code": None,
            "error_detail": None,
            "generated_at": None,
            "model": None,
            "is_stale": False,
        }
    is_stale = row.status == "ready" and row.source_hash != current_hash
    return {
        "status": row.status,
        "summary_ar": row.summary_ar,
        "summary_en": row.summary_en,
        "error_code": row.error_code,
        "error_detail": row.error_detail,
        "generated_at": row.generated_at.isoformat() if row.generated_at else None,
        "model": row.model,
        "prompt_version": row.prompt_version,
        "is_stale": is_stale,
    }


def generate_summary(contract_id, db: Session, *, force: bool = False) -> ContractSummary:
    contract = db.get(Contract, contract_id)
    if contract is None:
        raise ValueError("contract_not_found")
    if not contract.raw_text or not contract.raw_text.strip():
        row = get_or_create_row(contract_id, db)
        row.status = "failed"
        row.error_code = "no_raw_text"
        row.error_detail = "Contract text is not available."
        row.updated_at = _utcnow()
        db.commit()
        return row

    h = source_hash(contract)
    row = get_or_create_row(contract_id, db)
    if row.status == "ready" and row.source_hash == h and not force:
        return row

    row.status = "generating"
    row.error_code = None
    row.error_detail = None
    row.updated_at = _utcnow()
    db.commit()

    try:
        excerpt = contract.raw_text[:_MAX_EXCERPT]
        user = build_summary_user_prompt(
            title=contract.title,
            category=contract.contract_category,
            raw_excerpt=excerpt,
            structured_hints=_structured_hints(contract_id, db),
        )
        raw = complete_json(SUMMARY_SYSTEM, user, SUMMARY_SCHEMA)
        summary_ar, summary_en = _verify_sections(contract.raw_text, raw)
        row.summary_ar = summary_ar
        row.summary_en = summary_en
        row.status = "ready"
        row.source_hash = h
        row.model = AI_MODEL
        row.prompt_version = PROMPT_VERSION
        row.generated_at = _utcnow()
        row.updated_at = _utcnow()
        db.commit()
        db.refresh(row)
        return row
    except Exception as exc:
        code, detail = _safe_error(exc)
        row.status = "failed"
        row.error_code = code
        row.error_detail = detail
        row.updated_at = _utcnow()
        db.commit()
        db.refresh(row)
        return row


def schedule_summary_generation(contract_id, force: bool = False) -> None:
    """Background-safe entry (opens its own session)."""
    from ..db import SessionLocal

    db = SessionLocal()
    try:
        generate_summary(contract_id, db, force=force)
    finally:
        db.close()


def reextract_and_reanchor(contract_id, db: Session) -> dict:
    from ..ai.verify import page_for_offset, normalize
    from ..services.storage import storage
    from ..services.textextract import (
        build_raw_text,
        extract_pages_geometry,
        layout_from_geometry,
    )

    contract = db.get(Contract, contract_id)
    if contract is None:
        raise ValueError("contract_not_found")
    if not contract.file_url:
        raise ValueError("no_file")
    data = storage.get(contract.file_url)
    geo = extract_pages_geometry(data, contract.file_url)
    pages = [{"page": p["page"], "text": p.get("text") or ""} for p in geo]
    raw_text, page_starts = build_raw_text(pages)
    contract.raw_text = raw_text
    contract.page_layout = layout_from_geometry(geo)
    reanchored = 0
    lost = 0
    norm = normalize(raw_text)
    for cl in db.query(Clause).filter_by(contract_id=contract_id):
        quote = (cl.quote or "").strip()
        if not quote:
            lost += 1
            cl.char_start = None
            cl.char_end = None
            continue
        idx = raw_text.find(quote)
        if idx < 0:
            idx = norm.find(normalize(quote))
        if idx >= 0:
            cl.char_start = idx
            cl.char_end = idx + len(quote)
            cl.page = page_for_offset(page_starts, idx)
            reanchored += 1
        else:
            cl.char_start = None
            cl.char_end = None
            lost += 1
    db.commit()
    generate_summary(contract_id, db, force=True)
    return {"reanchored": reanchored, "unverified": lost, "pages": len(geo)}
