"""F1 extraction pipeline orchestrator.

run_extraction(contract_id, db) is IDEMPOTENT: re-running deletes previous
clauses/extractions/obligations for the contract and redoes them.

Writes ONLY to: contracts, clauses, extractions, obligations.
notice_periods / payment_milestones / penalties / obligations lists are also
stored inside extractions.value_json for the F2/F3 engines to consume
(see docs/README_HANDOFF.md).
"""
from __future__ import annotations

import uuid as _uuid

from sqlalchemy.orm import Session

from ..models import Clause, Contract, Extraction, Obligation
from ..services.dates import parse_date_raw
from ..services.storage import storage
from ..services.textextract import build_raw_text, extract_pages
from .client import complete_json
from .prompts import SYSTEM_PROMPT, build_user_prompt
from .schemas import EXTRACTION_SCHEMA
from .verify import normalize, page_for_offset, validate_quote

CHUNK_LIMIT = 100_000  # chars of raw text before we switch to chunked calls
CHUNK_TARGET = 80_000
LOW_CONFIDENCE = 0.7
UNVERIFIED_CAP = 0.5
FAIL_RATIO_REVIEW = 0.4

_LIST_FIELDS = ("notice_periods", "obligations", "payment_milestones", "penalties")
_SCALAR_CONF_KEYS = {"value_sar": "value_sar", "governing_law": "governing_law", "retention_pct": "retention_pct"}
_DATE_FIELDS = {
    "start_date": "start_date_raw",
    "end_date": "end_date_raw",
    "bond_expiry": "bond_expiry_raw",
    "warranty_end": "warranty_end_raw",
}


def run_extraction(contract_id, db: Session) -> dict:
    contract = db.get(Contract, contract_id)
    if contract is None:
        raise ValueError("contract_not_found")

    # ---- Stage 1: text ----
    data = storage.get(contract.file_url)
    pages = extract_pages(data, contract.file_url)
    raw_text, page_starts = build_raw_text(pages)
    contract.raw_text = raw_text
    norm_text = normalize(raw_text)

    # ---- Stage 2: model ----
    result, n_chunks = _run_model(norm_text, pages)

    # ---- Idempotency: wipe previous output (FK order matters) ----
    db.query(Obligation).filter(Obligation.contract_id == contract.id).delete()
    db.query(Extraction).filter(Extraction.contract_id == contract.id).delete()
    db.query(Clause).filter(Clause.contract_id == contract.id).delete()
    db.flush()

    # ---- Stage 3+4: verify quotes, link clauses, persist ----
    report = {"total_items": 0, "verified_items": 0, "failed_quotes": [], "chunks": n_chunks}
    needs_review: list[dict] = []

    def link_quote(item: dict, label: str) -> tuple[Clause | None, float]:
        """Verify item['quote']; on success create a clauses row and return it.
        On failure: no link, confidence capped at UNVERIFIED_CAP."""
        report["total_items"] += 1
        conf = float(item.get("confidence") or 0)
        found, start, end = validate_quote(norm_text, normalize(item.get("quote") or ""))
        if found:
            report["verified_items"] += 1
            page = page_for_offset(page_starts, start) or item.get("page")
            clause = Clause(
                id=_uuid.uuid4(),
                contract_id=contract.id,
                clause_ref=item.get("clause_ref"),
                quote=raw_text[start:end],
                page=page,
                char_start=start,
                char_end=end,
            )
            db.add(clause)
            db.flush()
            return clause, conf
        report["failed_quotes"].append({"field": label, "quote": (item.get("quote") or "")[:120]})
        needs_review.append({"field": label, "reason": "unverified_quote"})
        return None, min(conf, UNVERIFIED_CAP)

    def add_extraction(field: str, value_json, confidence: float | None, clause: Clause | None = None):
        db.add(Extraction(
            id=_uuid.uuid4(),
            contract_id=contract.id,
            field_name=field,
            value_json=value_json,
            confidence=round(confidence, 2) if confidence is not None else None,
            clause_id=clause.id if clause else None,
            status="auto",
        ))
        if confidence is not None and confidence < LOW_CONFIDENCE:
            needs_review.append({"field": field, "reason": "low_confidence", "confidence": round(confidence, 2)})

    fc = result.get("field_confidences") or {}

    # header: language / calendar
    contract.language = result.get("language")
    contract.calendar = result.get("calendar")

    # header: parties
    parties = result.get("parties") or {}
    contract.party_a = parties.get("a")
    contract.party_b = parties.get("b")
    add_extraction("party_a", {"value": parties.get("a")}, fc.get("parties", 0))
    add_extraction("party_b", {"value": parties.get("b")}, fc.get("parties", 0))

    # header: scalar fields
    for field, conf_key in _SCALAR_CONF_KEYS.items():
        value = result.get(field)
        setattr(contract, field, value)
        add_extraction(field, {"value": value}, fc.get(conf_key, 0) if value is not None else 0)

    # header: dates (hijri converted via hijri-converter; LLM never converts)
    for field, raw_key in _DATE_FIELDS.items():
        item = result.get(raw_key)
        if not item:
            setattr(contract, field, None)
            add_extraction(field, {"raw": None, "calendar": None, "gregorian": None}, 0)
            continue
        clause, conf = link_quote(item, field)
        gregorian = parse_date_raw(item.get("value"), item.get("detected_calendar"))
        setattr(contract, field, gregorian)
        add_extraction(
            field,
            {
                "raw": item.get("value"),
                "calendar": item.get("detected_calendar"),
                "gregorian": gregorian.isoformat() if gregorian else None,
            },
            conf,
            clause,
        )

    # list fields → verify each element; per-item clause link stored in value_json
    verified_lists: dict[str, list[dict]] = {}
    for field in _LIST_FIELDS:
        items_out = []
        for i, item in enumerate(result.get(field) or []):
            clause, conf = link_quote(item, f"{field}[{i}]")
            out = {k: v for k, v in item.items()}
            out["confidence"] = round(conf, 2)
            out["clause_id"] = str(clause.id) if clause else None
            out["char_start"] = clause.char_start if clause else None
            out["char_end"] = clause.char_end if clause else None
            out["verified"] = clause is not None
            if clause:
                out["_clause"] = clause  # transient, stripped before storing
            items_out.append(out)
        verified_lists[field] = items_out

    for field, items in verified_lists.items():
        stored = [{k: v for k, v in it.items() if k != "_clause"} for it in items]
        confs = [it["confidence"] for it in items]
        add_extraction(field, stored, (sum(confs) / len(confs)) if confs else None)

    # obligations table rows (due_in_days stays inside extractions.value_json for F2)
    for item in verified_lists["obligations"]:
        due = None
        raw_due = item.get("due_date_raw")
        if raw_due:
            due = parse_date_raw(raw_due.get("value"), raw_due.get("detected_calendar"))
        db.add(Obligation(
            id=_uuid.uuid4(),
            contract_id=contract.id,
            description=item.get("description"),
            responsible_party=item.get("responsible_party"),
            due_date=due,
            penalty_text=item.get("penalty_text"),
            status="pending",
            source_clause_id=item["_clause"].id if item.get("_clause") else None,
        ))

    # ---- Status ----
    total = report["total_items"]
    fail_ratio = (total - report["verified_items"]) / total if total else 0.0
    report["fail_ratio"] = round(fail_ratio, 2)
    contract.status = "needs_review" if fail_ratio > FAIL_RATIO_REVIEW else "ready"

    db.commit()

    return {
        "status": contract.status,
        "counts": {
            "clauses": db.query(Clause).filter(Clause.contract_id == contract.id).count(),
            "obligations": len(verified_lists["obligations"]),
            "notice_periods": len(verified_lists["notice_periods"]),
            "milestones": len(verified_lists["payment_milestones"]),
        },
        "needs_review": needs_review,
        "pipeline_report": report,
    }


def _run_model(norm_text: str, pages: list[dict]) -> tuple[dict, int]:
    """Single call for normal contracts; overlapping page-range chunks for huge ones."""
    if len(norm_text) <= CHUNK_LIMIT:
        return complete_json(SYSTEM_PROMPT, build_user_prompt(norm_text), EXTRACTION_SCHEMA), 1

    chunks: list[list[dict]] = []
    current: list[dict] = []
    size = 0
    for p in pages:
        current.append(p)
        size += len(p["text"])
        if size >= CHUNK_TARGET:
            chunks.append(current)
            current = [current[-1]]  # 1-page overlap
            size = len(current[0]["text"])
    if len(current) > 1 or not chunks:
        chunks.append(current)

    results = []
    for chunk_pages in chunks:
        chunk_text, _ = build_raw_text(chunk_pages)
        note = f"This is a partial chunk covering pages {chunk_pages[0]['page']}–{chunk_pages[-1]['page']} of a larger contract."
        results.append(complete_json(SYSTEM_PROMPT, build_user_prompt(normalize(chunk_text), note), EXTRACTION_SCHEMA))
    return _merge_chunks(results), len(chunks)


def _merge_chunks(results: list[dict]) -> dict:
    """Header fields from the chunk containing page 1; on conflict/None the
    highest field confidence wins. List fields: simple concat."""
    base = results[0]
    base_fc = base.setdefault("field_confidences", {})
    for r in results[1:]:
        fc = r.get("field_confidences") or {}
        for field in _LIST_FIELDS:
            base.setdefault(field, []).extend(r.get(field) or [])
        for field, key in _SCALAR_CONF_KEYS.items():
            if r.get(field) is not None and (base.get(field) is None or fc.get(key, 0) > base_fc.get(key, 0)):
                base[field] = r[field]
                base_fc[key] = fc.get(key, 0)
        for _field, raw_key in _DATE_FIELDS.items():
            cand = r.get(raw_key)
            cur = base.get(raw_key)
            if cand and (cur is None or (cand.get("confidence") or 0) > (cur.get("confidence") or 0)):
                base[raw_key] = cand
        parties = base.get("parties") or {}
        r_parties = r.get("parties") or {}
        if (parties.get("a") is None or fc.get("parties", 0) > base_fc.get("parties", 0)) and r_parties.get("a"):
            base["parties"] = r_parties
            base_fc["parties"] = fc.get("parties", 0)
    return base
