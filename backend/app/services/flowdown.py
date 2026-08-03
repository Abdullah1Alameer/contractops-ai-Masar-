"""F4 — Flow-Down X-Ray engine."""
from __future__ import annotations

import re
import uuid as _uuid
from typing import Any

from sqlalchemy.orm import Session

from ..ai.client import AIError, complete_json
from ..ai.classifier import FLOWDOWN_ELIGIBLE
from ..ai.flowdown_prompt import (
    FLOWDOWN_CATEGORIES,
    FLOWDOWN_RISKS,
    FLOWDOWN_STATUSES,
    FLOWDOWN_SYSTEM,
    FLOWDOWN_SCHEMA,
    build_flowdown_user_prompt,
)
from ..models import Clause, Contract, Extraction, FlowdownFinding

MAIN_CATEGORY = "Main Construction Contract"
SUB_CATEGORY = "Subcontract Agreement"
_READY = frozenset({"ready", "needs_review"})
_CAP = 10

_RISK_WEIGHT = {"critical": 4, "high": 3, "medium": 2, "low": 1, "informational": 0}
_RISK_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "informational": 4}

# category -> list of regex patterns (AR + EN) matched against item text
_CATEGORY_PATTERNS: dict[str, list[re.Pattern]] = {
    "scope_of_work": [re.compile(r"scope|نطاق|أعمال|works|توريد", re.I)],
    "deliverables": [re.compile(r"deliver|تسليم|مخرج", re.I)],
    "milestones": [re.compile(r"milestone|مرحلة|دفعة|payment no", re.I)],
    "completion_dates": [re.compile(r"completion|إنجاز|انتهاء|duration|مدة|end date", re.I)],
    "payment_terms": [re.compile(r"payment|دفع|مستخلص|invoice|فاتورة", re.I)],
    "retention": [re.compile(r"retention|محتجز|احتجاز|ضمان", re.I)],
    "performance_bond": [re.compile(r"bond|خطاب ضمان|performance guarantee", re.I)],
    "advance_payment": [re.compile(r"advance|مقدمة|down payment", re.I)],
    "insurance": [re.compile(r"insurance|تأمين", re.I)],
    "quality_requirements": [re.compile(r"quality|جودة|specification|مواصف", re.I)],
    "inspection_requirements": [re.compile(r"inspection|فحص|test|اختبار", re.I)],
    "hse_requirements": [re.compile(r"hse|health|safety|environment|سلامة|بيئة", re.I)],
    "liquidated_damages": [re.compile(r"liquidated|ld|غرامة|delay damages|تأخير", re.I)],
    "delay_clauses": [re.compile(r"delay|تأخير|late", re.I)],
    "extension_of_time": [re.compile(r"extension|eot|تمديد|extra time", re.I)],
    "warranty": [re.compile(r"warranty|ضمان|guarantee period", re.I)],
    "defects_liability_period": [re.compile(r"defect|عيب|dlp|liability period", re.I)],
    "termination": [re.compile(r"terminat|فسخ|إنهاء", re.I)],
    "variation_orders": [re.compile(r"variation|change order|أمر تغيير", re.I)],
    "notice_requirements": [re.compile(r"notice|إشعار|notification", re.I)],
    "dispute_resolution": [re.compile(r"dispute|arbitration|تحكيم|نزاع", re.I)],
    "governing_law": [re.compile(r"governing law|قانون|jurisdiction", re.I)],
    "force_majeure": [re.compile(r"force majeure|قوه قاهرة|fortuitous", re.I)],
}


def _match_categories(text: str) -> set[str]:
    hits: set[str] = set()
    for cat, patterns in _CATEGORY_PATTERNS.items():
        for pat in patterns:
            if pat.search(text or ""):
                hits.add(cat)
                break
    return hits


def _item_text(item: dict) -> str:
    parts = [
        str(item.get("description") or ""),
        str(item.get("purpose") or ""),
        str(item.get("label") or ""),
        str(item.get("type") or ""),
        str(item.get("rate") or ""),
        str(item.get("quote") or ""),
    ]
    return " ".join(parts)


def _bundle_item(item: dict, clause: Clause | None) -> dict | None:
    cid = item.get("clause_id")
    if cid:
        try:
            clause_id = str(_uuid.UUID(str(cid)))
        except ValueError:
            clause_id = None
    elif clause:
        clause_id = str(clause.id)
    else:
        return None
    quote = item.get("quote") or (clause.quote if clause else "")
    if not quote:
        return None
    return {
        "clause_id": clause_id,
        "clause_ref": item.get("clause_ref") or (clause.clause_ref if clause else None),
        "page": item.get("page") if item.get("page") is not None else (clause.page if clause else None),
        "quote": quote[:400],
        "summary": _item_text(item)[:200],
    }


def build_dossier(contract_id, db: Session) -> dict:
    contract = db.get(Contract, contract_id)
    if contract is None:
        raise ValueError("contract_not_found")

    clauses = {c.id: c for c in db.query(Clause).filter_by(contract_id=contract_id)}
    extractions = db.query(Extraction).filter_by(contract_id=contract_id).all()
    lists: dict[str, list] = {
        "obligations": [],
        "notice_periods": [],
        "payment_milestones": [],
        "penalties": [],
    }
    for e in extractions:
        if e.field_name in lists and isinstance(e.value_json, list):
            lists[e.field_name] = e.value_json

    categories: dict[str, list[dict]] = {c: [] for c in FLOWDOWN_CATEGORIES}
    seen: dict[str, set[str]] = {c: set() for c in FLOWDOWN_CATEGORIES}

    def add_to_cats(item: dict, clause: Clause | None):
        bundle = _bundle_item(item, clause)
        if not bundle or not bundle.get("clause_id"):
            return
        text = _item_text(item) + " " + (bundle.get("quote") or "")
        cats = _match_categories(text)
        if not cats:
            cats = {"scope_of_work"}
        for cat in cats:
            cid = bundle["clause_id"]
            if cid in seen[cat] or len(categories[cat]) >= _CAP:
                continue
            seen[cat].add(cid)
            categories[cat].append(bundle)

    for item in lists["obligations"]:
        if not isinstance(item, dict):
            continue
        clause = None
        try:
            if item.get("clause_id"):
                clause = clauses.get(_uuid.UUID(str(item["clause_id"])))
        except ValueError:
            clause = None
        add_to_cats(item, clause)

    for field in ("notice_periods", "payment_milestones", "penalties"):
        for item in lists[field]:
            if not isinstance(item, dict):
                continue
            clause = None
            try:
                if item.get("clause_id"):
                    clause = clauses.get(_uuid.UUID(str(item["clause_id"])))
            except ValueError:
                pass
            add_to_cats(item, clause)

    # Header-only signals
    header_items = []
    if contract.retention_pct is not None:
        header_items.append(("retention", f"Retention {contract.retention_pct}%"))
    if contract.governing_law:
        header_items.append(("governing_law", contract.governing_law))
    if contract.end_date:
        header_items.append(("completion_dates", f"End date {contract.end_date.isoformat()}"))
    if contract.bond_expiry:
        header_items.append(("performance_bond", f"Bond expiry {contract.bond_expiry.isoformat()}"))
    if contract.warranty_end:
        header_items.append(("warranty", f"Warranty end {contract.warranty_end.isoformat()}"))

    lang = "ar"
    for e in extractions:
        if e.field_name == "language" and isinstance(e.value_json, dict):
            lang = e.value_json.get("value") or lang
        if e.field_name == "language" and isinstance(e.value_json, str):
            lang = e.value_json

    return {
        "contract_id": str(contract_id),
        "title": contract.title,
        "contract_category": contract.contract_category,
        "language": contract.language or lang,
        "header": {
            "party_a": contract.party_a,
            "party_b": contract.party_b,
            "value_sar": float(contract.value_sar) if contract.value_sar is not None else None,
            "start_date": contract.start_date.isoformat() if contract.start_date else None,
            "end_date": contract.end_date.isoformat() if contract.end_date else None,
            "retention_pct": float(contract.retention_pct) if contract.retention_pct is not None else None,
            "bond_expiry": contract.bond_expiry.isoformat() if contract.bond_expiry else None,
            "warranty_end": contract.warranty_end.isoformat() if contract.warranty_end else None,
            "governing_law": contract.governing_law,
            "header_signals": header_items,
        },
        "categories": categories,
        "valid_clause_ids": sorted(
            {b["clause_id"] for cat in categories.values() for b in cat if b.get("clause_id")}
        ),
    }


def collect_valid_clause_ids(dossier: dict) -> set[str]:
    return set(dossier.get("valid_clause_ids") or [])


def _parse_uuid(s: str | None):
    if not s:
        return None
    try:
        return _uuid.UUID(str(s))
    except ValueError:
        return None


def _coerce_status(s: str | None) -> str:
    if s in FLOWDOWN_STATUSES:
        return s
    return "missing"


def _coerce_risk(s: str | None) -> str:
    if s in FLOWDOWN_RISKS:
        return s
    return "medium"


def validate_ai_findings(
    raw_findings: list[dict],
    main_valid: set[str],
    sub_valid: set[str],
) -> list[dict]:
    by_cat: dict[str, dict] = {}
    for item in raw_findings or []:
        if not isinstance(item, dict):
            continue
        cat = item.get("category")
        if cat not in FLOWDOWN_CATEGORIES:
            continue
        main_id = item.get("main_clause_id")
        sub_id = item.get("sub_clause_id")
        if main_id and str(main_id) not in main_valid:
            main_id = None
        if sub_id and str(sub_id) not in sub_valid:
            sub_id = None
        conf = float(item.get("confidence") or 0)
        conf = max(0.0, min(1.0, conf))
        normalized = {
            "category": cat,
            "status": _coerce_status(item.get("status")),
            "risk_level": _coerce_risk(item.get("risk_level")),
            "explanation": item.get("explanation") or "",
            "recommendation": item.get("recommendation") or "",
            "main_clause_id": str(main_id) if main_id else None,
            "sub_clause_id": str(sub_id) if sub_id else None,
            "main_citation": item.get("main_citation"),
            "sub_citation": item.get("sub_citation"),
            "confidence": round(conf, 2),
        }
        prev = by_cat.get(cat)
        if prev is None or normalized["confidence"] > prev["confidence"]:
            by_cat[cat] = normalized

    # Ensure every category present
    out = []
    for cat in FLOWDOWN_CATEGORIES:
        if cat in by_cat:
            out.append(by_cat[cat])
        else:
            out.append(
                {
                    "category": cat,
                    "status": "fully_flowed_down",
                    "risk_level": "informational",
                    "explanation": "",
                    "recommendation": "",
                    "main_clause_id": None,
                    "sub_clause_id": None,
                    "main_citation": None,
                    "sub_citation": None,
                    "confidence": 0.5,
                }
            )
    return out


def validate_and_persist(
    main_id,
    sub_id,
    findings: list[dict],
    db: Session,
) -> list[FlowdownFinding]:
    db.query(FlowdownFinding).filter_by(
        main_contract_id=main_id,
        subcontract_id=sub_id,
    ).delete(synchronize_session=False)

    rows: list[FlowdownFinding] = []
    for f in findings:
        row = FlowdownFinding(
            id=_uuid.uuid4(),
            main_contract_id=main_id,
            subcontract_id=sub_id,
            category=f["category"],
            obligation_summary=f.get("explanation", "")[:500],
            status=f["status"],
            main_clause_id=_parse_uuid(f.get("main_clause_id")),
            sub_clause_id=_parse_uuid(f.get("sub_clause_id")),
            explanation=f.get("explanation"),
            recommendation=f.get("recommendation"),
            main_citation=f.get("main_citation"),
            sub_citation=f.get("sub_citation"),
            risk_note=f.get("explanation"),
            severity=f["risk_level"],
            confidence=f.get("confidence"),
        )
        db.add(row)
        rows.append(row)
    db.flush()
    return rows


def summarize(findings: list[dict]) -> dict:
    total = len(findings)
    if total == 0:
        return {
            "overall_risk_score": 0,
            "critical_count": 0,
            "missing_count": 0,
            "conflict_count": 0,
            "coverage_pct": 0,
            "total": 0,
        }
    flowed = sum(1 for f in findings if f.get("status") in ("fully_flowed_down", "modified"))
    critical = sum(1 for f in findings if f.get("risk_level") == "critical" or f.get("severity") == "critical")
    missing = sum(1 for f in findings if f.get("status") == "missing")
    conflict = sum(1 for f in findings if f.get("status") == "conflict")
    weights = sum(_RISK_WEIGHT.get(f.get("risk_level") or f.get("severity") or "informational", 0) for f in findings)
    max_w = total * 4
    overall = round(100 * weights / max_w) if max_w else 0
    return {
        "overall_risk_score": overall,
        "critical_count": critical,
        "missing_count": missing,
        "conflict_count": conflict,
        "coverage_pct": round(100 * flowed / total),
        "total": total,
    }


def _clause_source(clause: Clause | None) -> dict | None:
    if clause is None:
        return None
    return {
        "clause_id": str(clause.id),
        "clause_ref": clause.clause_ref,
        "quote": clause.quote,
        "page": clause.page,
        "char_start": clause.char_start,
        "char_end": clause.char_end,
    }


def serialize_finding(
    row: FlowdownFinding,
    main_clauses: dict,
    sub_clauses: dict,
) -> dict:
    mc = main_clauses.get(row.main_clause_id) if row.main_clause_id else None
    sc = sub_clauses.get(row.sub_clause_id) if row.sub_clause_id else None
    return {
        "id": str(row.id),
        "category": row.category,
        "status": row.status,
        "risk_level": row.severity,
        "explanation": row.explanation,
        "recommendation": row.recommendation,
        "confidence": float(row.confidence) if row.confidence is not None else None,
        "main_citation": row.main_citation,
        "sub_citation": row.sub_citation,
        "main_source": _clause_source(mc),
        "sub_source": _clause_source(sc),
    }


def sort_findings(items: list[dict]) -> list[dict]:
    def key(f: dict):
        risk = f.get("risk_level") or "informational"
        return (_RISK_ORDER.get(risk, 99), f.get("category") or "")

    return sorted(items, key=key)


def check_eligibility(main: Contract | None, sub: Contract | None):
    if main is None or sub is None:
        raise ValueError("not_found")
    if main.status not in _READY or sub.status not in _READY:
        raise ValueError("extraction_not_complete")
    if main.contract_category not in FLOWDOWN_ELIGIBLE:
        raise ValueError("flowdown_ineligible_main")
    if sub.contract_category not in FLOWDOWN_ELIGIBLE:
        raise ValueError("flowdown_ineligible_sub")
    if main.contract_category != MAIN_CATEGORY:
        raise ValueError("flowdown_wrong_pair")
    if sub.contract_category != SUB_CATEGORY:
        raise ValueError("flowdown_wrong_pair")


def run_flowdown(main_id, sub_id, db: Session) -> dict:
    main = db.get(Contract, main_id)
    sub = db.get(Contract, sub_id)
    check_eligibility(main, sub)

    main_dossier = build_dossier(main_id, db)
    sub_dossier = build_dossier(sub_id, db)
    main_valid = collect_valid_clause_ids(main_dossier)
    sub_valid = collect_valid_clause_ids(sub_dossier)

    try:
        raw = complete_json(
            FLOWDOWN_SYSTEM,
            build_flowdown_user_prompt(main_dossier, sub_dossier),
            FLOWDOWN_SCHEMA,
        )
    except AIError as e:
        raise ValueError("ai_failed") from e

    findings = validate_ai_findings(raw.get("findings") or [], main_valid, sub_valid)
    validate_and_persist(main_id, sub_id, findings, db)
    db.commit()

    main_clauses = {c.id: c for c in db.query(Clause).filter_by(contract_id=main_id)}
    sub_clauses = {c.id: c for c in db.query(Clause).filter_by(contract_id=sub_id)}
    rows = db.query(FlowdownFinding).filter_by(main_contract_id=main_id, subcontract_id=sub_id).all()
    serialized = [serialize_finding(r, main_clauses, sub_clauses) for r in rows]
    serialized = sort_findings(serialized)
    summary = summarize(
        [
            {
                "status": s["status"],
                "risk_level": s["risk_level"],
                "severity": s["risk_level"],
            }
            for s in serialized
        ]
    )
    return {
        "main": {"id": str(main_id), "title": main.title},
        "sub": {"id": str(sub_id), "title": sub.title},
        "findings": serialized,
        "summary": summary,
    }


def list_flowdown_for_pair(main_id, sub_id, db: Session) -> dict | None:
    main = db.get(Contract, main_id)
    sub = db.get(Contract, sub_id)
    if main is None or sub is None:
        return None
    rows = (
        db.query(FlowdownFinding)
        .filter_by(main_contract_id=main_id, subcontract_id=sub_id)
        .order_by(FlowdownFinding.created_at.desc())
        .all()
    )
    if not rows:
        return None
    main_clauses = {c.id: c for c in db.query(Clause).filter_by(contract_id=main_id)}
    sub_clauses = {c.id: c for c in db.query(Clause).filter_by(contract_id=sub_id)}
    serialized = sort_findings([serialize_finding(r, main_clauses, sub_clauses) for r in rows])
    summary = summarize(
        [{"status": s["status"], "risk_level": s["risk_level"], "severity": s["risk_level"]} for s in serialized]
    )
    return {
        "main": {"id": str(main_id), "title": main.title},
        "sub": {"id": str(sub_id), "title": sub.title},
        "findings": serialized,
        "summary": summary,
    }


def list_flowdown_contracts(db: Session) -> dict:
    q = db.query(Contract).filter(
        Contract.status.in_(_READY),
        Contract.contract_category.in_(FLOWDOWN_ELIGIBLE),
    )
    main_list = []
    sub_list = []
    for c in q.order_by(Contract.title.asc()).all():
        item = {"id": str(c.id), "title": c.title or str(c.id), "contract_category": c.contract_category}
        if c.contract_category == MAIN_CATEGORY:
            main_list.append(item)
        elif c.contract_category == SUB_CATEGORY:
            sub_list.append(item)
    return {"main": main_list, "sub": sub_list}
