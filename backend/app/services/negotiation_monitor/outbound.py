"""Outbound response send — never automatic without lawyer approval."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ...integrations.email import get_email_connector
from ...integrations.email.base import OutboundEmailRequest
from ...models import NegotiationEmail, NegotiationReviewPackage, NegotiationThread
from ...services import approvals as appr_svc
from .lineage_events import log_monitor_event
from .rounds import close_round, open_round


def _required_approvers_from_package(pkg: NegotiationReviewPackage) -> set[str]:
    roles: set[str] = set()
    body = pkg.package_json if isinstance(pkg.package_json, dict) else {}
    for ch in body.get("changes") or []:
        role = ch.get("required_approver") or "none"
        if role and role not in ("none", ""):
            roles.add(role)
    edited = pkg.lawyer_edited_json if isinstance(pkg.lawyer_edited_json, dict) else {}
    override = edited.get("approval_override")
    if override and override.get("reason"):
        return set()
    return roles


def _finance_or_executive_approved(db: Session, contract_id, roles: set[str]) -> tuple[bool, str | None]:
    if not roles:
        return True, None
    wf = appr_svc.get_active_workflow(contract_id, db)
    if wf is None:
        missing = ", ".join(sorted(roles))
        return False, f"required_approval_missing:{missing}"
    if wf.status != "approved":
        return False, "approval_workflow_not_complete"
    return True, None


def approve_response(
    db: Session,
    pkg: NegotiationReviewPackage,
    *,
    actor: str,
    edited: dict | None = None,
) -> NegotiationReviewPackage:
    if edited:
        pkg.lawyer_edited_json = edited
        if edited.get("draft_email_body_en"):
            pkg.draft_email_body_en = edited["draft_email_body_en"]
        if edited.get("draft_email_body_ar"):
            pkg.draft_email_body_ar = edited["draft_email_body_ar"]
        if edited.get("draft_email_subject_en"):
            pkg.draft_email_subject_en = edited["draft_email_subject_en"]
        if edited.get("draft_email_subject_ar"):
            pkg.draft_email_subject_ar = edited["draft_email_subject_ar"]
    pkg.status = "approved"
    pkg.reviewed_by = actor
    pkg.reviewed_at = datetime.now(timezone.utc)
    thread = db.get(NegotiationThread, pkg.thread_id)
    if thread:
        thread.status = "response_ready"
    db.commit()
    db.refresh(pkg)
    if thread:
        log_monitor_event(
            db,
            thread.contract_id,
            "response_approved",
            actor=actor,
            thread_id=thread.id,
            email_id=pkg.email_id,
        )
    return pkg


def send_approved_response(
    db: Session,
    pkg: NegotiationReviewPackage,
    *,
    actor: str,
    override_reason: str | None = None,
) -> NegotiationEmail:
    if pkg.status not in ("approved", "edited", "ready"):
        raise ValueError("package_not_approved")

    thread = db.get(NegotiationThread, pkg.thread_id)
    if thread is None:
        raise ValueError("thread_not_found")

    roles = _required_approvers_from_package(pkg)
    if override_reason:
        pkg.lawyer_edited_json = {**(pkg.lawyer_edited_json or {}), "approval_override": {"reason": override_reason}}
        db.commit()
        roles = set()
    ok, err = _finance_or_executive_approved(db, thread.contract_id, roles)
    if not ok:
        raise ValueError(err or "approval_required")

    connector = get_email_connector()
    subject = pkg.draft_email_subject_en or "Contract negotiation response"
    body = pkg.draft_email_body_en or ""
    to = [thread.counterparty_email] if thread.counterparty_email else []
    if not to:
        raise ValueError("counterparty_email_missing")

    result = connector.send_message(
        OutboundEmailRequest(
            thread_id=str(thread.id),
            external_thread_id=thread.external_thread_id,
            to=to,
            cc=[],
            subject=subject,
            body_text=body,
            reply_reference=str(uuid.uuid4()),
        )
    )

    outbound = NegotiationEmail(
        id=uuid.uuid4(),
        thread_id=thread.id,
        external_message_id=result.external_message_id,
        external_thread_id=thread.external_thread_id,
        provider=result.provider,
        direction="outbound",
        sender_name="Legal Team",
        sender_email="legal@yourcompany.example",
        recipients_json={"to": to},
        subject=subject,
        body_text=body,
        sent_at=datetime.fromisoformat(result.sent_at.replace("Z", "+00:00")),
        classification="counterproposal",
        processing_status="completed",
        requires_response=False,
    )
    db.add(outbound)
    pkg.status = "response_sent"
    thread.status = "awaiting_counterparty"
    thread.last_message_at = outbound.sent_at
    db.commit()
    db.refresh(outbound)

    from ...models import NegotiationRound

    rnd = (
        db.query(NegotiationRound)
        .filter_by(thread_id=thread.id, review_package_id=pkg.id)
        .order_by(NegotiationRound.round_number.desc())
        .first()
    )
    if rnd:
        rnd.outbound_email_id = outbound.id
        close_round(rnd, db, status="sent")
        log_monitor_event(
            db,
            thread.contract_id,
            "response_sent",
            actor=actor,
            thread_id=thread.id,
            round_id=rnd.id,
            email_id=outbound.id,
        )
        log_monitor_event(
            db,
            thread.contract_id,
            "negotiation_round_closed",
            actor=actor,
            thread_id=thread.id,
            round_id=rnd.id,
        )
    open_round(db, thread=thread, inbound_email_id=None, base_version_id=thread.current_version_id)
    return outbound
