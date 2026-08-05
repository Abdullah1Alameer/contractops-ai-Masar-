"""Negotiation monitor orchestration API."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ...integrations.email import get_email_connector
from ...models import (
    Contract,
    NegotiationAttachment,
    NegotiationEmail,
    NegotiationReviewPackage,
    NegotiationRound,
    NegotiationThread,
    PlaybookRule,
    LegalPlaybook,
)
from ...services import versions as ver_svc
from ...services.storage import storage
from .classification import classify_email
from .demo_seed import ensure_demo_data
from .lineage_events import log_monitor_event
from .matching import link_email_to_thread
from .outbound import approve_response, send_approved_response
from .review_package import generate_review_package
from .rounds import open_round, set_round_status
from .version_bridge import create_proposed_version_from_attachment


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def serialize_thread(t: NegotiationThread, db: Session) -> dict[str, Any]:
    contract = db.get(Contract, t.contract_id)
    latest_pkg = (
        db.query(NegotiationReviewPackage)
        .filter_by(thread_id=t.id)
        .order_by(NegotiationReviewPackage.created_at.desc())
        .first()
    )
    return {
        "id": str(t.id),
        "contract_id": str(t.contract_id),
        "contract_title": contract.title if contract else None,
        "counterparty_name": t.counterparty_name,
        "counterparty_email": t.counterparty_email,
        "subject": t.subject,
        "status": t.status,
        "monitoring_enabled": t.monitoring_enabled,
        "assigned_lawyer": t.assigned_lawyer,
        "overall_risk_score": latest_pkg.overall_risk_score if latest_pkg else None,
        "detected_action": latest_pkg.recommendation if latest_pkg else None,
        "requires_attention": t.status in ("lawyer_review", "counterparty_responded", "response_ready"),
        "last_message_at": _iso(t.last_message_at),
        "last_analyzed_at": _iso(t.last_analyzed_at),
        "external_thread_id": t.external_thread_id,
        "standard_template_version_id": str(t.standard_template_version_id) if t.standard_template_version_id else None,
        "playbook_id": str(t.playbook_id) if t.playbook_id else None,
        "base_version_id": str(t.base_version_id) if t.base_version_id else None,
        "current_version_id": str(t.current_version_id) if t.current_version_id else None,
        "created_at": _iso(t.created_at),
    }


def serialize_email(e: NegotiationEmail) -> dict[str, Any]:
    return {
        "id": str(e.id),
        "thread_id": str(e.thread_id) if e.thread_id else None,
        "direction": e.direction,
        "sender_name": e.sender_name,
        "sender_email": e.sender_email,
        "recipients_json": e.recipients_json,
        "subject": e.subject,
        "body_text": e.body_text,
        "classification": e.classification,
        "processing_status": e.processing_status,
        "linked_version_id": str(e.linked_version_id) if e.linked_version_id else None,
        "requires_response": e.requires_response,
        "reply_reference": e.reply_reference,
        "received_at": _iso(e.received_at),
        "sent_at": _iso(e.sent_at),
        "needs_manual_link": e.needs_manual_link,
        "match_confidence": float(e.match_confidence) if e.match_confidence is not None else None,
        "provider": e.provider,
        "external_message_id": e.external_message_id,
    }


def serialize_attachment(a: NegotiationAttachment) -> dict[str, Any]:
    return {
        "id": str(a.id),
        "email_id": str(a.email_id),
        "filename": a.filename,
        "mime_type": a.mime_type,
        "size_bytes": a.size_bytes,
        "file_hash_sha256": a.file_hash_sha256,
        "document_type": a.document_type,
        "processing_status": a.processing_status,
        "created_version_id": str(a.created_version_id) if a.created_version_id else None,
    }


def serialize_package(p: NegotiationReviewPackage) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "thread_id": str(p.thread_id),
        "email_id": str(p.email_id) if p.email_id else None,
        "status": p.status,
        "executive_summary": p.executive_summary,
        "overall_risk_score": p.overall_risk_score,
        "recommendation": p.recommendation,
        "package_json": p.package_json,
        "draft_email_subject_en": p.draft_email_subject_en,
        "draft_email_subject_ar": p.draft_email_subject_ar,
        "draft_email_body_en": p.draft_email_body_en,
        "draft_email_body_ar": p.draft_email_body_ar,
        "lawyer_edited_json": p.lawyer_edited_json,
        "reviewed_by": p.reviewed_by,
        "reviewed_at": _iso(p.reviewed_at),
        "generated_at": _iso(p.generated_at),
    }


def list_threads(db: Session, *, status: str | None = None) -> list[dict]:
    ensure_demo_data(db)
    q = db.query(NegotiationThread).order_by(NegotiationThread.updated_at.desc())
    if status:
        q = q.filter(NegotiationThread.status == status)
    return [serialize_thread(t, db) for t in q.limit(200).all()]


def get_thread_detail(thread_id, db: Session) -> dict:
    t = db.get(NegotiationThread, thread_id)
    if t is None:
        raise ValueError("not_found")
    emails = (
        db.query(NegotiationEmail)
        .filter_by(thread_id=t.id)
        .order_by(NegotiationEmail.created_at.asc())
        .all()
    )
    email_payload = []
    for e in emails:
        atts = db.query(NegotiationAttachment).filter_by(email_id=e.id).all()
        email_payload.append({**serialize_email(e), "attachments": [serialize_attachment(a) for a in atts]})
    rounds = db.query(NegotiationRound).filter_by(thread_id=t.id).order_by(NegotiationRound.round_number.asc()).all()
    return {
        **serialize_thread(t, db),
        "emails": email_payload,
        "rounds": [
            {
                "id": str(r.id),
                "round_number": r.round_number,
                "status": r.status,
                "inbound_email_id": str(r.inbound_email_id) if r.inbound_email_id else None,
                "outbound_email_id": str(r.outbound_email_id) if r.outbound_email_id else None,
                "review_package_id": str(r.review_package_id) if r.review_package_id else None,
                "opened_at": _iso(r.opened_at),
                "closed_at": _iso(r.closed_at),
            }
            for r in rounds
        ],
    }


def create_thread(db: Session, payload: dict, *, actor: str = "demo") -> dict:
    contract_id = payload.get("contract_id")
    if not contract_id:
        raise ValueError("contract_id_required")
    contract = db.get(Contract, uuid.UUID(str(contract_id)))
    if contract is None:
        raise ValueError("contract_not_found")
    cur = ver_svc.current_version(contract.id, db)
    t = NegotiationThread(
        id=uuid.uuid4(),
        contract_id=contract.id,
        base_version_id=cur.id if cur else None,
        current_version_id=cur.id if cur else None,
        counterparty_name=payload.get("counterparty_name"),
        counterparty_email=payload.get("counterparty_email"),
        subject=payload.get("subject"),
        status="monitoring" if payload.get("monitoring_enabled", True) else "draft",
        monitoring_enabled=bool(payload.get("monitoring_enabled", True)),
        standard_template_version_id=uuid.UUID(str(payload["standard_template_version_id"]))
        if payload.get("standard_template_version_id")
        else None,
        playbook_id=uuid.UUID(str(payload["playbook_id"])) if payload.get("playbook_id") else None,
        external_thread_id=payload.get("external_thread_id"),
        assigned_lawyer=payload.get("assigned_lawyer"),
        created_by=actor,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    log_monitor_event(db, contract.id, "negotiation_thread_started", actor=actor, thread_id=t.id)
    return serialize_thread(t, db)


def patch_thread(thread_id, db: Session, payload: dict) -> dict:
    t = db.get(NegotiationThread, thread_id)
    if t is None:
        raise ValueError("not_found")
    for key in ("status", "assigned_lawyer", "monitoring_enabled", "subject", "counterparty_name"):
        if key in payload:
            setattr(t, key, payload[key])
    db.commit()
    db.refresh(t)
    return serialize_thread(t, db)


def import_email_to_thread(
    thread_id,
    db: Session,
    *,
    payload: dict,
    actor: str = "demo",
) -> dict:
    t = db.get(NegotiationThread, thread_id)
    if t is None:
        raise ValueError("not_found")

    connector = get_email_connector()
    msg_dto = None
    if payload.get("simulated_message_id"):
        msg_dto = connector.get_message(payload["simulated_message_id"])
    elif payload.get("manual"):
        manual = payload["manual"]
        msg_dto = None
        email = NegotiationEmail(
            id=uuid.uuid4(),
            thread_id=t.id,
            provider=payload.get("provider") or "manual",
            direction="inbound",
            sender_name=manual.get("sender_name"),
            sender_email=manual.get("sender_email") or t.counterparty_email,
            recipients_json=manual.get("recipients_json"),
            subject=manual.get("subject") or t.subject,
            body_text=manual.get("body_text"),
            received_at=datetime.now(timezone.utc),
            processing_status="received",
        )
        db.add(email)
        db.commit()
        db.refresh(email)
        return _process_inbound_email(db, t, email, manual.get("attachments") or [], actor=actor)

    if msg_dto is None:
        raise ValueError("message_not_found")

    email = NegotiationEmail(
        id=uuid.uuid4(),
        thread_id=t.id,
        external_message_id=msg_dto.external_message_id,
        external_thread_id=msg_dto.external_thread_id,
        provider=connector.name,
        direction="inbound",
        sender_name=msg_dto.sender_name,
        sender_email=msg_dto.sender_email,
        recipients_json={"to": msg_dto.recipients},
        subject=msg_dto.subject,
        body_text=msg_dto.body_text,
        received_at=datetime.fromisoformat(msg_dto.received_at.replace("Z", "+00:00"))
        if msg_dto.received_at
        else datetime.now(timezone.utc),
        reply_reference=msg_dto.reply_reference,
        processing_status="received",
    )
    db.add(email)
    db.commit()
    db.refresh(email)

    att_payloads = []
    for att in msg_dto.attachments:
        content = att.content or b""
        key = storage.save(content, att.filename) if content else None
        att_payloads.append({"filename": att.filename, "mime_type": att.mime_type, "file_url": key, "content": content})
    return _process_inbound_email(db, t, email, att_payloads, actor=actor)


def _process_inbound_email(db: Session, t: NegotiationThread, email: NegotiationEmail, attachments: list, *, actor: str) -> dict:
    file_hash = None
    att_rows: list[NegotiationAttachment] = []
    for raw in attachments:
        content = raw.get("content") or b""
        if not content and raw.get("file_url"):
            try:
                content = storage.get(raw["file_url"])
            except Exception:
                content = b""
        if isinstance(content, str):
            content = content.encode("utf-8")
        from hashlib import sha256

        h = sha256(content).hexdigest() if content else None
        file_hash = file_hash or h
        row = NegotiationAttachment(
            id=uuid.uuid4(),
            email_id=email.id,
            filename=raw.get("filename") or "attachment.bin",
            mime_type=raw.get("mime_type"),
            size_bytes=len(content) if content else None,
            file_url=raw.get("file_url"),
            file_hash_sha256=h,
        )
        db.add(row)
        att_rows.append((row, content))

    match = link_email_to_thread(
        db,
        email=email,
        external_thread_id=email.external_thread_id,
        reply_reference=email.reply_reference,
        sender_email=email.sender_email,
        subject=email.subject,
        file_hash=file_hash,
        explicit_thread_id=t.id,
    )
    email.match_confidence = match.confidence
    email.needs_manual_link = match.needs_review and match.thread_id is None
    if match.thread_id and email.thread_id is None:
        email.thread_id = match.thread_id

    cls = classify_email(subject=email.subject, body_text=email.body_text, has_attachment=bool(att_rows))
    email.classification = cls.get("classification")
    email.requires_response = bool(cls.get("requires_response"))
    email.processing_status = "needs_review" if cls.get("needs_review") else "parsing"
    t.last_message_at = email.received_at or datetime.now(timezone.utc)
    db.commit()

    log_monitor_event(
        db,
        t.contract_id,
        "email_received",
        actor=actor,
        thread_id=t.id,
        email_id=email.id,
    )

    contract = db.get(Contract, t.contract_id)
    proposed_version_id = None
    for row, content in att_rows:
        db.refresh(row)
        if content and contract:
            kind, ver = create_proposed_version_from_attachment(db, contract=contract, attachment=row, file_bytes=content, actor=actor)
            if ver:
                proposed_version_id = ver.id
                email.linked_version_id = ver.id
                log_monitor_event(
                    db,
                    t.contract_id,
                    "proposed_version_created",
                    actor=actor,
                    thread_id=t.id,
                    email_id=email.id,
                    version_id=ver.id,
                )
                log_monitor_event(
                    db,
                    t.contract_id,
                    "revised_document_detected",
                    actor=actor,
                    thread_id=t.id,
                    email_id=email.id,
                    version_id=ver.id,
                )

    rnd = open_round(
        db,
        thread=t,
        inbound_email_id=email.id,
        base_version_id=t.current_version_id,
        proposed_version_id=proposed_version_id,
    )
    log_monitor_event(
        db,
        t.contract_id,
        "negotiation_round_started",
        actor=actor,
        thread_id=t.id,
        round_id=rnd.id,
        email_id=email.id,
    )
    db.commit()
    return {"email": serialize_email(email), "round_id": str(rnd.id), "match": {"confidence": match.confidence}}


def analyze_thread(thread_id, db: Session, *, email_id: uuid.UUID | None = None, actor: str = "demo") -> dict:
    t = db.get(NegotiationThread, thread_id)
    if t is None:
        raise ValueError("not_found")
    email = None
    if email_id:
        email = db.get(NegotiationEmail, email_id)
    if email is None:
        email = (
            db.query(NegotiationEmail)
            .filter_by(thread_id=t.id, direction="inbound")
            .order_by(NegotiationEmail.created_at.desc())
            .first()
        )
    if email is None:
        raise ValueError("no_email")

    rnd = (
        db.query(NegotiationRound)
        .filter_by(thread_id=t.id, inbound_email_id=email.id)
        .order_by(NegotiationRound.round_number.desc())
        .first()
    )
    set_round_status(rnd, "analyzing", db) if rnd else None
    pkg = generate_review_package(db, thread=t, email=email, round_id=rnd.id if rnd else None, actor=actor)
    if rnd:
        rnd.review_package_id = pkg.id
        rnd.proposed_version_id = email.linked_version_id
        rnd.status = "lawyer_review"
        db.commit()
    return serialize_package(pkg)


def link_email_contract(email_id, db: Session, *, thread_id: uuid.UUID) -> dict:
    email = db.get(NegotiationEmail, email_id)
    t = db.get(NegotiationThread, thread_id)
    if email is None or t is None:
        raise ValueError("not_found")
    email.thread_id = t.id
    email.needs_manual_link = False
    email.processing_status = "received"
    db.commit()
    return serialize_email(email)


def create_version_from_attachment(email_id, attachment_id, db: Session, *, actor: str = "demo") -> dict:
    email = db.get(NegotiationEmail, email_id)
    att = db.get(NegotiationAttachment, attachment_id)
    if email is None or att is None or att.email_id != email.id:
        raise ValueError("not_found")
    t = db.get(NegotiationThread, email.thread_id) if email.thread_id else None
    if t is None:
        raise ValueError("thread_not_linked")
    contract = db.get(Contract, t.contract_id)
    content = b""
    if att.file_url:
        content = storage.get(att.file_url)
    kind, ver = create_proposed_version_from_attachment(db, contract=contract, attachment=att, file_bytes=content, actor=actor)
    if ver:
        email.linked_version_id = ver.id
        db.commit()
    return {"kind": kind, "version_id": str(ver.id) if ver else None}


def list_simulated_inbox(db: Session) -> list[dict]:
    ensure_demo_data(db)
    connector = get_email_connector()
    out = []
    for th in connector.list_threads():
        for m in th.messages:
            out.append(
                {
                    "external_thread_id": th.external_thread_id,
                    "external_message_id": m.external_message_id,
                    "subject": m.subject,
                    "sender_email": m.sender_email,
                    "preview": (m.body_text or "")[:160],
                }
            )
    return out


def list_playbooks(db: Session) -> list[dict]:
    rows = db.query(LegalPlaybook).filter_by(status="active").all()
    return [{"id": str(r.id), "name": r.name, "contract_category": r.contract_category, "language": r.language}]


def get_playbook(playbook_id, db: Session) -> dict:
    pb = db.get(LegalPlaybook, playbook_id)
    if pb is None:
        raise ValueError("not_found")
    rules = db.query(PlaybookRule).filter_by(playbook_id=pb.id).order_by(PlaybookRule.clause_category.asc()).all()
    return {
        "id": str(pb.id),
        "name": pb.name,
        "contract_category": pb.contract_category,
        "rules": [
            {
                "id": str(r.id),
                "clause_category": r.clause_category,
                "rule_name": r.rule_name,
                "preferred_position": r.preferred_position,
                "fallback_position": r.fallback_position,
                "unacceptable_position": r.unacceptable_position,
                "approval_required_role": r.approval_required_role,
                "severity": r.severity,
                "guidance": r.guidance,
            }
            for r in rules
        ],
    }
