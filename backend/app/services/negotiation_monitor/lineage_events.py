"""Lineage and activity helpers for negotiation monitor."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from ...services.approvals import log_activity

MONITOR_EVENT_TYPES = frozenset(
    {
        "email_received",
        "negotiation_thread_started",
        "negotiation_round_started",
        "revised_document_detected",
        "proposed_version_created",
        "template_comparison_completed",
        "playbook_deviation_detected",
        "lawyer_package_generated",
        "lawyer_package_reviewed",
        "counterproposal_prepared",
        "response_approved",
        "response_sent",
        "counterparty_accepted",
        "negotiation_round_closed",
        "agreement_reached",
    }
)


def log_monitor_event(
    db: Session,
    contract_id: uuid.UUID,
    event_type: str,
    *,
    actor: str | None = None,
    thread_id: uuid.UUID | None = None,
    round_id: uuid.UUID | None = None,
    email_id: uuid.UUID | None = None,
    version_id: uuid.UUID | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    meta: dict[str, Any] = {}
    if thread_id:
        meta["thread_id"] = str(thread_id)
    if round_id:
        meta["round_id"] = str(round_id)
    if email_id:
        meta["email_id"] = str(email_id)
    if version_id:
        meta["version_id"] = str(version_id)
    if extra:
        meta.update(extra)
    log_activity(db, contract_id, event_type, actor=actor, metadata=meta)
    db.commit()
