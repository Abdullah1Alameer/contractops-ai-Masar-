"""Three-way comparison for negotiation monitor."""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from ...models import ContractVersion
from ...services import versions as ver_svc


def _extract_text_from_version(db: Session, v: ContractVersion | None) -> str:
    if v is None:
        return ""
    if v.extracted_json and isinstance(v.extracted_json, dict):
        parts = []
        for k, val in v.extracted_json.items():
            if isinstance(val, dict) and val.get("value"):
                parts.append(str(val.get("value")))
        if parts:
            return "\n".join(parts)
    if v.file_path:
        from ...services.storage import storage

        try:
            data = storage.get(v.file_path)
            from ...services.textextract import extract_pages, build_raw_text as pages_to_raw

            if isinstance(data, bytes):
                pages = extract_pages(data, v.file_path)
                raw, _ = pages_to_raw(pages)
                return raw
        except Exception:
            pass
    return v.change_summary or ""


def _template_deviations_heuristic(client_text: str, template_text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    patterns = [
        ("Payment Terms", r"payment[^\n]{0,120}", r"thirty \(30\)|30 days|ninety \(90\)|90 days"),
        ("Liability", r"liabilit[^\n]{0,120}", r"unlimited|contract value"),
        ("Governing Law", r"governing law[^\n]{0,120}", r"Saudi Arabia|England"),
    ]
    for category, client_pat, _ in patterns:
        cm = re.search(client_pat, client_text, re.I)
        tm = re.search(client_pat, template_text, re.I)
        if cm or tm:
            client_quote = cm.group(0) if cm else ""
            template_quote = tm.group(0) if tm else ""
            if client_quote and template_quote and client_quote.strip().lower() != template_quote.strip().lower():
                findings.append(
                    {
                        "clause_category": category,
                        "client_clause": client_quote[:500],
                        "template_clause": template_quote[:500],
                        "needs_review": not (client_quote and template_quote),
                    }
                )
            elif client_quote and not template_quote:
                findings.append(
                    {
                        "clause_category": category,
                        "client_clause": client_quote[:500],
                        "template_clause": "",
                        "needs_review": True,
                    }
                )
    return findings


def run_three_way(
    db: Session,
    *,
    contract_id,
    previous_version_id,
    proposed_version_id,
    template_version_id,
) -> dict[str, Any]:
    prev = db.get(ContractVersion, previous_version_id) if previous_version_id else None
    proposed = db.get(ContractVersion, proposed_version_id) if proposed_version_id else None
    template = db.get(ContractVersion, template_version_id) if template_version_id else None

    previous_comparison: dict[str, Any] | None = None
    if prev and proposed:
        try:
            previous_comparison = ver_svc.compare_versions(contract_id, prev.id, proposed.id, db)
        except Exception as exc:
            previous_comparison = {"error": str(exc)}

    client_text = _extract_text_from_version(db, proposed)
    template_text = _extract_text_from_version(db, template)
    template_deviations = _template_deviations_heuristic(client_text, template_text)

    overall_risk = 40
    if previous_comparison and isinstance(previous_comparison.get("diff"), dict):
        diff = previous_comparison["diff"]
        if isinstance(diff.get("overall_risk_score"), int):
            overall_risk = diff["overall_risk_score"]
    for d in template_deviations:
        if d.get("needs_review"):
            overall_risk = max(overall_risk, 65)

    recommended = "negotiate"
    if overall_risk >= 80:
        recommended = "reject"
    elif overall_risk <= 35:
        recommended = "accept"

    return {
        "previous_version_comparison": previous_comparison,
        "template_deviations": template_deviations,
        "overall_risk_score": overall_risk,
        "recommended_action": recommended,
    }
