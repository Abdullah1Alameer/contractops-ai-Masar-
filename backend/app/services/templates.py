"""Real, backend-backed "Use Template" contract creation flow.

Replaces the prior frontend-only TEMPLATE_SEED list whose "Use Template"
button simply redirected to /upload with no template ID, no variables, and
no generated document. See docs/signature-placement-and-template-flow-report.md.
"""
from __future__ import annotations

import re
import uuid as _uuid

import fitz
from sqlalchemy.orm import Session

from ..models import Contract, ContractTemplate
from .approvals import log_activity
from .storage import storage


class TemplateError(ValueError):
    """Stable service error contract for the templates API."""

    def __init__(self, status_code: int, code: str, **payload):
        self.status_code = status_code
        self.code = code
        self.payload = {"error": code, **payload}
        super().__init__(code)


def _raise(status_code: int, code: str, **payload) -> None:
    raise TemplateError(status_code, code, **payload)


def _resolve(template_id_or_key: str, db: Session) -> ContractTemplate | None:
    try:
        return db.query(ContractTemplate).filter_by(id=_uuid.UUID(str(template_id_or_key))).first()
    except (ValueError, AttributeError):
        return db.query(ContractTemplate).filter_by(key=str(template_id_or_key)).first()


def get_template_or_404(template_id_or_key: str, db: Session) -> ContractTemplate:
    row = _resolve(template_id_or_key, db)
    if row is None:
        _raise(404, "template_not_found")
    return row


def serialize_template_summary(t: ContractTemplate) -> dict:
    return {
        "id": str(t.id),
        "key": t.key,
        "title_en": t.title_en,
        "title_ar": t.title_ar,
        "category": t.category,
        "language": t.language,
        "industry": t.industry,
        "usage_count": t.usage_count,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


def serialize_template_detail(t: ContractTemplate) -> dict:
    return {
        **serialize_template_summary(t),
        "description_en": t.description_en,
        "description_ar": t.description_ar,
        "variables": (t.variables or {}).get("fields", []),
        "clauses": [
            {"title_en": s.get("title_en"), "title_ar": s.get("title_ar")}
            for s in (t.clauses or {}).get("sections", [])
        ],
    }


def list_templates(db: Session) -> list[dict]:
    rows = db.query(ContractTemplate).order_by(ContractTemplate.title_en.asc()).all()
    return [serialize_template_summary(t) for t in rows]


_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


def _substitute(text: str, variables: dict) -> str:
    def repl(m: re.Match) -> str:
        key = m.group(1)
        val = variables.get(key)
        return str(val) if val not in (None, "") else f"[{key}]"

    return _PLACEHOLDER.sub(repl, text or "")


def _required_variable_keys(template: ContractTemplate) -> list[str]:
    return [f["key"] for f in (template.variables or {}).get("fields", []) if f.get("required")]


def render_sections(template: ContractTemplate, variables: dict, *, lang: str) -> list[dict]:
    """Same rendering used for the preview step and the final generated PDF
    — the preview the user approves is exactly what gets created."""
    sections = (template.clauses or {}).get("sections", [])
    out = []
    for s in sections:
        title = s.get(f"title_{lang}") or s.get("title_en") or ""
        body = _substitute(s.get(f"body_{lang}") or s.get("body_en") or "", variables)
        out.append({"title": title, "body": body})
    return out


def preview_contract(template_id_or_key: str, db: Session, *, variables: dict) -> dict:
    template = get_template_or_404(template_id_or_key, db)
    missing = [k for k in _required_variable_keys(template) if not str(variables.get(k) or "").strip()]
    return {
        "template": serialize_template_summary(template),
        "missing_variables": missing,
        "sections_en": render_sections(template, variables, lang="en"),
        "sections_ar": render_sections(template, variables, lang="ar"),
    }


def _build_document_bytes(template: ContractTemplate, variables: dict) -> bytes:
    doc = fitz.open()
    for lang in ("ar", "en"):
        page = doc.new_page(width=595, height=842)
        title = template.title_ar if lang == "ar" else template.title_en
        page.insert_text((50, 50), title[:200], fontsize=16)
        y = 90
        for section in render_sections(template, variables, lang=lang):
            if y > 740:
                page = doc.new_page(width=595, height=842)
                y = 50
            page.insert_textbox(fitz.Rect(50, y, 545, y + 18), section["title"], fontsize=12)
            y += 22
            box_height = 150
            page.insert_textbox(fitz.Rect(50, y, 545, y + box_height), section["body"], fontsize=9)
            y += box_height + 14
    out = doc.tobytes()
    doc.close()
    return out


def create_contract_from_template(
    template_id_or_key: str,
    db: Session,
    *,
    variables: dict,
    actor: str = "demo",
) -> dict:
    template = get_template_or_404(template_id_or_key, db)
    missing = [k for k in _required_variable_keys(template) if not str(variables.get(k) or "").strip()]
    if missing:
        _raise(422, "template_variables_missing", missing=missing)

    pdf_bytes = _build_document_bytes(template, variables)
    key = storage.save(pdf_bytes, f"template_{template.key}_{_uuid.uuid4()}.pdf")
    try:
        party_a = (variables.get("party_a") or "").strip() or None
        party_b = (variables.get("party_b") or "").strip() or None
        label = party_b or party_a
        contract = Contract(
            id=_uuid.uuid4(),
            title=f"{template.title_en} — {label}" if label else template.title_en,
            file_url=key,
            status="processing",
            stage="draft",
            template_id=template.id,
            party_a=party_a,
            party_b=party_b,
            governing_law=(variables.get("governing_law") or "").strip() or None,
        )
        db.add(contract)
        db.flush()

        from .versions import create_initial_version

        version = create_initial_version(contract, db, actor=actor)
        version.source = "template_generated"
        db.add(version)

        log_activity(
            db,
            contract.id,
            "contract_created_from_template",
            actor=actor,
            metadata={
                "template_id": str(template.id),
                "template_key": template.key,
                "version_id": str(version.id),
            },
        )
        template.usage_count = (template.usage_count or 0) + 1
        db.add(template)
        db.commit()
        db.refresh(contract)
        db.refresh(version)
    except Exception:
        db.rollback()
        storage.delete(key)
        raise

    return {
        "id": str(contract.id),
        "stage": contract.stage,
        "status": contract.status,
        "template_id": str(template.id),
        "version_id": str(version.id),
        "version_number": version.version_number,
    }
