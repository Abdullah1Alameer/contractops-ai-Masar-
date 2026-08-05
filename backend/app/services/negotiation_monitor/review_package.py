"""Generate lawyer review packages."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ...ai.client import complete_json
from ...ai.review_package_prompt import REVIEW_PACKAGE_SCHEMA, REVIEW_PACKAGE_SYSTEM, build_review_package_prompt
from ...models import ContractVersion, NegotiationEmail, NegotiationReviewPackage, NegotiationThread
from .comparison import run_three_way
from .playbook import evaluate_playbook


def _fallback_package(
    *,
    comparison: dict[str, Any],
    playbook_deviations: list[dict[str, Any]],
    email: NegotiationEmail | None,
) -> dict[str, Any]:
    changes = []
    for dev in comparison.get("template_deviations") or []:
        pb = next((p for p in playbook_deviations if p.get("clause_category") == dev.get("clause_category")), {})
        changes.append(
            {
                "clause_category": dev.get("clause_category") or "General",
                "clause_reference": dev.get("clause_category") or "",
                "original_text": "",
                "revised_text": dev.get("client_clause") or "",
                "template_text": dev.get("template_clause") or "",
                "change_type": "modified",
                "risk_level": "high" if pb.get("deviation_level") == "unacceptable" else "medium",
                "business_impact": "May affect cash flow and exposure.",
                "legal_impact": pb.get("explanation") or "Review required.",
                "playbook_position": pb.get("deviation_level") or "needs_review",
                "required_approver": pb.get("required_approver") or "legal",
                "recommendation": pb.get("recommendation") or "Negotiate.",
                "counter_clause_en": pb.get("recommendation") or "",
                "counter_clause_ar": "يرجى مراجعة البند والرد بموقف الشركة.",
                "citations": {
                    "previous_version": {"quote": "", "location": ""},
                    "new_version": {"quote": dev.get("client_clause") or "", "location": "client draft"},
                    "template": {"quote": dev.get("template_clause") or "", "location": "standard template"},
                },
                "confidence": 0.5 if dev.get("needs_review") else 0.75,
            }
        )

    subj = email.subject if email else "Contract negotiation"
    return {
        "executive_summary": "Counterparty sent revised terms requiring legal review.",
        "counterparty_intent": email.body_text[:500] if email and email.body_text else "",
        "overall_risk_score": comparison.get("overall_risk_score") or 60,
        "recommended_strategy": comparison.get("recommended_action") or "negotiate",
        "changes": changes,
        "draft_email_subject_en": f"Re: {subj}",
        "draft_email_subject_ar": f"رد: {subj}",
        "draft_email_body_en": "Thank you for your revised draft. We propose the attached counterpositions.",
        "draft_email_body_ar": "شكرًا على مسودتكم المعدلة. نرفق مقترحاتنا التفاوضية.",
        "open_questions": [],
    }


def generate_review_package(
    db: Session,
    *,
    thread: NegotiationThread,
    email: NegotiationEmail,
    round_id: uuid.UUID | None,
    actor: str = "negotiation_monitor",
) -> NegotiationReviewPackage:
    base_id = thread.current_version_id or thread.base_version_id
    proposed_id = email.linked_version_id
    template_id = thread.standard_template_version_id

    comparison = run_three_way(
        db,
        contract_id=thread.contract_id,
        previous_version_id=base_id,
        proposed_version_id=proposed_id,
        template_version_id=template_id,
    )

    client_text = ""
    if proposed_id:
        pv = db.get(ContractVersion, proposed_id)
        if pv and pv.file_path:
            from ...services.storage import storage
            from ...services.textextract import extract_pages, build_raw_text as pages_to_raw

            try:
                data = storage.get(pv.file_path)
                if isinstance(data, bytes):
                    pages = extract_pages(data, pv.file_path)
                    client_text, _ = pages_to_raw(pages)
            except Exception:
                client_text = email.body_text or ""

    playbook_deviations = []
    if thread.playbook_id:
        playbook_deviations = evaluate_playbook(
            db,
            playbook_id=thread.playbook_id,
            client_text=client_text,
            template_deviations=comparison.get("template_deviations") or [],
        )

    context = {
        "email_subject": email.subject,
        "email_body": email.body_text,
        "comparison": comparison,
        "playbook_deviations": playbook_deviations,
    }

    try:
        package_json = complete_json(
            REVIEW_PACKAGE_SYSTEM,
            build_review_package_prompt(context),
            REVIEW_PACKAGE_SCHEMA,
        )
    except Exception:
        package_json = _fallback_package(
            comparison=comparison,
            playbook_deviations=playbook_deviations,
            email=email,
        )

    for ch in package_json.get("changes") or []:
        cites = ch.get("citations") or {}
        for key in ("previous_version", "new_version", "template"):
            c = cites.get(key) or {}
            if not (c.get("quote") or "").strip():
                ch["playbook_position"] = "needs_review"
                ch["confidence"] = min(float(ch.get("confidence") or 1), 0.4)

    pkg = NegotiationReviewPackage(
        id=uuid.uuid4(),
        thread_id=thread.id,
        email_id=email.id,
        base_version_id=base_id,
        proposed_version_id=proposed_id,
        template_version_id=template_id,
        executive_summary=package_json.get("executive_summary"),
        overall_risk_score=package_json.get("overall_risk_score"),
        recommendation=package_json.get("recommended_strategy"),
        package_json=package_json,
        status="ready",
        generated_at=datetime.now(timezone.utc),
        draft_email_subject_en=package_json.get("draft_email_subject_en"),
        draft_email_subject_ar=package_json.get("draft_email_subject_ar"),
        draft_email_body_en=package_json.get("draft_email_body_en"),
        draft_email_body_ar=package_json.get("draft_email_body_ar"),
    )
    db.add(pkg)
    thread.status = "lawyer_review"
    thread.last_analyzed_at = datetime.now(timezone.utc)
    email.processing_status = "analyzed"
    db.commit()
    db.refresh(pkg)

    from .lineage_events import log_monitor_event

    log_monitor_event(
        db,
        thread.contract_id,
        "lawyer_package_generated",
        actor=actor,
        thread_id=thread.id,
        round_id=round_id,
        email_id=email.id,
        version_id=proposed_id,
    )
    log_monitor_event(
        db,
        thread.contract_id,
        "template_comparison_completed",
        actor=actor,
        thread_id=thread.id,
        round_id=round_id,
    )
    if playbook_deviations:
        log_monitor_event(
            db,
            thread.contract_id,
            "playbook_deviation_detected",
            actor=actor,
            thread_id=thread.id,
            round_id=round_id,
        )
    return pkg
