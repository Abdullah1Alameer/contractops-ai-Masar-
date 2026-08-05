"""Feature 14 — aggregate contract version lineage from workflows + activity."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ..models import (
    ActivityEvent,
    ApprovalStep,
    ApprovalWorkflow,
    Clause,
    ContractVersion,
    Extraction,
    Negotiation,
    Obligation,
    ReviewRequest,
    SignatureRequest,
    VersionComparison,
)
from . import versions as ver_svc

METADATA_WHITELIST = frozenset(
    {
        "version_number",
        "from",
        "to",
        "role",
        "step_order",
        "signer_order",
        "request_id",
        "workflow_id",
        "signature_request_id",
        "negotiation_id",
        "review_request_id",
        "thread_id",
        "round_id",
        "email_id",
        "version_id",
        "reason",
        "source",
    }
)

EVENT_TYPE_ALIASES: dict[str, str] = {
    "approval_workflow_started": "approval_started",
    "approval_workflow_completed": "approval_completed",
    "approval_workflow_cancelled": "approval_cancelled",
    "approval_step_approved": "approval_step_approved",
    "approval_step_rejected": "approval_step_rejected",
    "version_sent_for_review": "review_sent",
    "version_sent_for_approval": "approval_started",
    "version_sent_for_signature": "signature_request_sent",
    "version_compared": "versions_compared",
    "ai_comparison_generated": "ai_comparison_generated",
    "signature_request_created": "signature_request_created",
    "signature_request_sent": "signature_request_sent",
    "signature_request_completed": "signature_completed",
    "signed_document_generated": "signed_version_created",
    "negotiation_generated": "negotiation_analyzed",
}

TRANSITION_REASON_MAP: dict[str, str] = {
    "signed": "signed_document_generated",
    "approved": "final_approved_snapshot",
    "manual_upload": "manual_revision",
    "client_revision": "client_requested_changes",
    "negotiation_counter": "negotiation_counterproposal",
    "internal_revision": "internal_legal_revision",
    "initial_upload": "manual_revision",
}

MONITOR_LINEAGE_EVENTS = frozenset(
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


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def canonical_event_type(raw: str) -> str:
    return EVENT_TYPE_ALIASES.get(raw, raw)


def event_category(event_type: str) -> str:
    t = canonical_event_type(event_type)
    if t.startswith("version_") or t in ("signed_version_created", "counter_version_created"):
        return "version"
    if t.startswith("extraction_") or t.startswith("ai_") or t == "negotiation_analyzed":
        return "ai"
    if t.startswith("review_") or t == "review_sent":
        return "review"
    if t.startswith("negotiation_") or t in MONITOR_LINEAGE_EVENTS:
        return "negotiation"
    if t.startswith("approval_"):
        return "approval"
    if t.startswith("signature_") or t.startswith("signer_") or t.startswith("signed_"):
        return "signature"
    if t.startswith("contract_"):
        return "lifecycle"
    if t.startswith("versions_") or t.startswith("risk_"):
        return "comparison"
    return "version"


def sanitize_metadata(meta: dict | None) -> dict:
    if not meta:
        return {}
    out: dict[str, Any] = {}
    for k, v in meta.items():
        if k in ("token", "token_hash", "email", "signature_image"):
            continue
        if k in METADATA_WHITELIST:
            out[k] = v
    return out


def version_risk_score(version: ContractVersion, db: Session) -> int | None:
    """Priority: stored extracted_json.risk_score → comparison rich score → heuristic → null."""
    extracted = version.extracted_json if isinstance(version.extracted_json, dict) else {}
    stored = extracted.get("risk_score")
    if isinstance(stored, (int, float)) and 0 <= int(stored) <= 100:
        return int(stored)

    cmp_row = (
        db.query(VersionComparison)
        .filter_by(to_version_id=version.id)
        .order_by(VersionComparison.created_at.desc())
        .first()
    )
    if cmp_row and isinstance(cmp_row.diff_json, dict):
        rich = cmp_row.diff_json.get("rich") or {}
        rs = rich.get("overall_risk_score")
        if isinstance(rs, (int, float)) and 0 <= int(rs) <= 100:
            return int(rs)

    high_risk = int(
        db.query(Clause).filter(Clause.contract_id == version.contract_id).count() or 0
    )
    missing = 0
    extr = db.query(Extraction).filter_by(contract_id=version.contract_id).all()
    for e in extr:
        if e.value_json is None or e.value_json == {} or e.value_json == {"value": None}:
            missing += 1
    overdue = int(db.query(Obligation).filter_by(contract_id=version.contract_id, status="overdue").count() or 0)

    if high_risk == 0 and missing == 0 and overdue == 0 and not extr:
        return None

    score = min(100, 20 + overdue * 5 + missing * 6 + max(0, high_risk - 5) * 2)
    return score if score > 20 else None


def _version_at_time(versions: list[ContractVersion], when: datetime | None) -> ContractVersion | None:
    if not versions or when is None:
        return versions[-1] if versions else None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    chosen = versions[0]
    for v in versions:
        created = v.created_at
        if created is None:
            continue
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if created <= when:
            chosen = v
    return chosen


def _resolve_version_id_for_activity(
    ev: ActivityEvent,
    versions: list[ContractVersion],
    by_id: dict,
    db: Session,
) -> Any:
    meta = ev.event_metadata or {}
    vn = meta.get("version_number")
    if vn is not None:
        for v in versions:
            if v.version_number == int(vn):
                return v.id

    rid = meta.get("request_id") or meta.get("signature_request_id")
    if rid:
        try:
            import uuid as _uuid

            sr = db.get(SignatureRequest, _uuid.UUID(str(rid)))
        except (ValueError, TypeError):
            sr = None
        if sr and sr.version_id:
            return sr.version_id

    wid = meta.get("workflow_id")
    if wid:
        aw = db.get(ApprovalWorkflow, wid)
        if aw and aw.version_id:
            return aw.version_id

    v = _version_at_time(versions, ev.created_at)
    return v.id if v else None


def _workflow_summary_for_version(version: ContractVersion, db: Session, cur_id) -> dict[str, str | None]:
    def status_or_none(latest, not_started="not_started"):
        if latest is None:
            return not_started
        return latest

    rr = (
        db.query(ReviewRequest)
        .filter_by(version_id=version.id)
        .order_by(ReviewRequest.created_at.desc())
        .first()
    )
    neg = (
        db.query(Negotiation)
        .filter_by(version_id=version.id)
        .order_by(Negotiation.updated_at.desc())
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

    review_s = rr.status if rr else "not_started"
    neg_s = neg.workflow_status if neg else "not_started"
    appr_s = aw.status if aw else "not_started"
    sig_s = sr.status if sr else "not_started"

    return {
        "review": review_s,
        "negotiation": neg_s,
        "approval": appr_s,
        "signature": sig_s,
    }


def workflow_stale_count(version: ContractVersion, db: Session) -> int:
    cur = ver_svc.current_version(version.contract_id, db)
    if cur is None or cur.id == version.id:
        return 0
    n = 0
    for rr in db.query(ReviewRequest).filter_by(version_id=version.id).all():
        if ver_svc.is_stale_workflow(rr, version.contract_id, db):
            n += 1
    for neg in db.query(Negotiation).filter_by(version_id=version.id).all():
        if ver_svc.is_stale_workflow(neg, version.contract_id, db):
            n += 1
    for aw in db.query(ApprovalWorkflow).filter_by(version_id=version.id).all():
        if ver_svc.is_stale_workflow(aw, version.contract_id, db):
            n += 1
    for sr in db.query(SignatureRequest).filter_by(version_id=version.id).all():
        if ver_svc.is_stale_workflow(sr, version.contract_id, db):
            n += 1
    return n


def enrich_version_fields(version: ContractVersion, db: Session) -> dict[str, Any]:
    """Extra serializer fields without full lineage build."""
    wf = _workflow_status_for_version_light(version, db)
    neg = (
        db.query(Negotiation)
        .filter_by(version_id=version.id)
        .order_by(Negotiation.updated_at.desc())
        .first()
    )
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

    last_at = version.created_at
    for ts in (
        rr.responded_at if rr else None,
        neg.updated_at if neg else None,
        aw.completed_at if aw else None,
        sr.updated_at if sr else None,
    ):
        if isinstance(ts, datetime) and (last_at is None or (isinstance(last_at, datetime) and ts > last_at)):
            last_at = ts

    event_count = 0
    all_v = (
        db.query(ContractVersion)
        .filter_by(contract_id=version.contract_id)
        .order_by(ContractVersion.version_number.asc())
        .all()
    )
    by_all = {x.id: x for x in all_v}
    for ev in db.query(ActivityEvent).filter_by(contract_id=version.contract_id).all():
        vid = _resolve_version_id_for_activity(ev, all_v, by_all, db)
        if vid == version.id:
            event_count += 1

    children = int(db.query(ContractVersion).filter_by(parent_version_id=version.id).count() or 0)
    is_superseded = not version.is_current and children > 0
    display_status = version.status
    if version.is_current:
        display_status = version.status
    elif is_superseded:
        display_status = "superseded"

    return {
        **wf,
        "risk_score": version_risk_score(version, db),
        "negotiation_status": neg.workflow_status if neg else None,
        "workflow_stale_count": workflow_stale_count(version, db),
        "event_count": event_count,
        "last_activity_at": _iso(last_at),
        "created_by_display": version.created_by or "—",
        "signed_at": _iso(sr.completed_at) if sr and sr.status == "completed" else None,
        "approved_at": _iso(aw.completed_at) if aw and aw.status == "completed" else None,
        "review_completed_at": _iso(rr.responded_at) if rr and rr.status in ("approved", "rejected", "changes_requested") else None,
        "negotiation_completed_at": _iso(neg.updated_at)
        if neg and neg.workflow_status in ("accepted", "closed", "client_responded")
        else None,
        "is_superseded": is_superseded,
        "is_signed": bool(sr and sr.status == "completed"),
        "is_approved": bool(aw and aw.status == "completed"),
        "display_status": display_status,
        "workflow_summary": _workflow_summary_for_version(version, db, None),
    }


def _workflow_status_for_version_light(version: ContractVersion, db: Session) -> dict:
    return ver_svc._workflow_status_for_version(version, db)


def _lineage_event_from_activity(ev: ActivityEvent, version_id, versions: list) -> dict:
    et = canonical_event_type(ev.event_type)
    meta = sanitize_metadata(ev.event_metadata)
    return {
        "event_id": str(ev.id),
        "version_id": str(version_id),
        "version_number": next((v.version_number for v in versions if v.id == version_id), None),
        "event_type": et,
        "event_category": event_category(ev.event_type),
        "title_key": f"activity.{et}",
        "description": ev.comment,
        "actor": ev.actor,
        "actor_role": ev.role,
        "timestamp": _iso(ev.created_at),
        "status": None,
        "related_entity_type": None,
        "related_entity_id": None,
        "metadata": meta,
        "source_version_id": None,
        "target_version_id": None,
        "_sort_ts": ev.created_at,
        "_dedupe_key": (str(version_id), et, ev.actor, _iso(ev.created_at)),
    }


def _dedupe_events(events: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    out: list[dict] = []
    for e in sorted(events, key=lambda x: x.get("_sort_ts") or datetime.min.replace(tzinfo=timezone.utc)):
        key = e.get("_dedupe_key") or (e.get("version_id"), e.get("event_type"))
        if key in seen:
            continue
        seen.add(key)
        clean = {k: v for k, v in e.items() if not k.startswith("_")}
        out.append(clean)
    return out


def transition_reason(version: ContractVersion) -> str:
    src = version.source or "manual_revision"
    return TRANSITION_REASON_MAP.get(src, src)


def build_lineage(contract_id, db: Session) -> dict:
    versions = (
        db.query(ContractVersion)
        .filter_by(contract_id=contract_id)
        .order_by(ContractVersion.version_number.asc())
        .all()
    )
    by_id = {v.id: v for v in versions}
    cur = ver_svc.current_version(contract_id, db)
    activity = (
        db.query(ActivityEvent)
        .filter_by(contract_id=contract_id)
        .order_by(ActivityEvent.created_at.asc())
        .all()
    )

    events_by_version: dict[Any, list[dict]] = {v.id: [] for v in versions}

    for ev in activity:
        vid = _resolve_version_id_for_activity(ev, versions, by_id, db)
        if vid is None or vid not in events_by_version:
            continue
        events_by_version[vid].append(_lineage_event_from_activity(ev, vid, versions))

    for v in versions:
        if not any(e["event_type"] == "version_created" for e in events_by_version[v.id]):
            events_by_version[v.id].insert(
                0,
                {
                    "event_id": f"synthetic-created-{v.id}",
                    "version_id": str(v.id),
                    "version_number": v.version_number,
                    "event_type": "version_created",
                    "event_category": "version",
                    "title_key": "activity.version_created",
                    "description": v.change_summary,
                    "actor": v.created_by,
                    "actor_role": None,
                    "timestamp": _iso(v.created_at),
                    "status": v.status,
                    "related_entity_type": "contract_version",
                    "related_entity_id": str(v.id),
                    "metadata": {"version_number": v.version_number, "source": v.source},
                    "source_version_id": None,
                    "target_version_id": None,
                },
            )

        for rr in db.query(ReviewRequest).filter_by(version_id=v.id).all():
            events_by_version[v.id].append(
                {
                    "event_id": f"review-{rr.id}",
                    "version_id": str(v.id),
                    "version_number": v.version_number,
                    "event_type": "review_sent",
                    "event_category": "review",
                    "title_key": "activity.review_sent",
                    "description": rr.message,
                    "actor": rr.sender_name,
                    "actor_role": None,
                    "timestamp": _iso(rr.created_at),
                    "status": rr.status,
                    "related_entity_type": "review_request",
                    "related_entity_id": str(rr.id),
                    "metadata": {"review_request_id": str(rr.id), "version_number": v.version_number},
                    "source_version_id": None,
                    "target_version_id": None,
                    "_sort_ts": rr.created_at,
                    "_dedupe_key": (str(v.id), "review_sent", str(rr.id)),
                }
            )

        for neg in db.query(Negotiation).filter_by(version_id=v.id).all():
            if neg.ai_summary:
                events_by_version[v.id].append(
                    {
                        "event_id": f"neg-{neg.id}",
                        "version_id": str(v.id),
                        "version_number": v.version_number,
                        "event_type": "negotiation_analyzed",
                        "event_category": "negotiation",
                        "title_key": "activity.negotiation_analyzed",
                        "description": neg.ai_summary[:200] if neg.ai_summary else None,
                        "actor": None,
                        "actor_role": None,
                        "timestamp": _iso(neg.updated_at or neg.created_at),
                        "status": neg.workflow_status,
                        "related_entity_type": "negotiation",
                        "related_entity_id": str(neg.id),
                        "metadata": {"negotiation_id": str(neg.id), "version_number": v.version_number},
                        "source_version_id": None,
                        "target_version_id": None,
                        "_sort_ts": neg.updated_at or neg.created_at,
                        "_dedupe_key": (str(v.id), "negotiation_analyzed", str(neg.id)),
                    }
                )

        aw = (
            db.query(ApprovalWorkflow)
            .filter_by(version_id=v.id)
            .order_by(ApprovalWorkflow.created_at.desc())
            .first()
        )
        if aw:
            events_by_version[v.id].append(
                {
                    "event_id": f"aw-{aw.id}",
                    "version_id": str(v.id),
                    "version_number": v.version_number,
                    "event_type": "approval_started",
                    "event_category": "approval",
                    "title_key": "activity.approval_started",
                    "description": None,
                    "actor": aw.started_by,
                    "actor_role": None,
                    "timestamp": _iso(aw.started_at or aw.created_at),
                    "status": aw.status,
                    "related_entity_type": "approval_workflow",
                    "related_entity_id": str(aw.id),
                    "metadata": {"workflow_id": str(aw.id), "version_number": v.version_number},
                    "source_version_id": None,
                    "target_version_id": None,
                    "_sort_ts": aw.started_at or aw.created_at,
                    "_dedupe_key": (str(v.id), "approval_started", str(aw.id)),
                }
            )
            for step in db.query(ApprovalStep).filter_by(workflow_id=aw.id).order_by(ApprovalStep.step_order).all():
                if step.status == "approved":
                    events_by_version[v.id].append(
                        {
                            "event_id": f"step-{step.id}",
                            "version_id": str(v.id),
                            "version_number": v.version_number,
                            "event_type": "approval_step_approved",
                            "event_category": "approval",
                            "title_key": "activity.approval_step_approved",
                            "description": step.comment,
                            "actor": step.approver_name,
                            "actor_role": step.role,
                            "timestamp": _iso(step.decided_at),
                            "status": step.status,
                            "related_entity_type": "approval_step",
                            "related_entity_id": str(step.id),
                            "metadata": {
                                "workflow_id": str(aw.id),
                                "step_order": step.step_order,
                                "role": step.role,
                                "version_number": v.version_number,
                            },
                            "source_version_id": None,
                            "target_version_id": None,
                            "_sort_ts": step.decided_at,
                            "_dedupe_key": (str(v.id), "approval_step_approved", str(step.id)),
                        }
                    )

    version_payloads = []
    for v in versions:
        enriched = enrich_version_fields(v, db)
        evs = _dedupe_events(events_by_version.get(v.id, []))
        evs.sort(key=lambda e: e.get("timestamp") or "")
        version_payloads.append(
            {
                "id": str(v.id),
                "version_number": v.version_number,
                "version_label": v.version_label or f"v{v.version_number}",
                "source": v.source,
                "status": enriched.get("display_status", v.status),
                "is_current": v.is_current,
                "is_approved": enriched["is_approved"],
                "is_signed": enriched["is_signed"],
                "is_superseded": enriched["is_superseded"],
                "created_by": v.created_by,
                "created_by_display": enriched["created_by_display"],
                "created_at": _iso(v.created_at),
                "change_summary": v.change_summary,
                "parent_version_id": str(v.parent_version_id) if v.parent_version_id else None,
                "risk_score": enriched["risk_score"],
                "workflow_summary": enriched["workflow_summary"],
                "workflow_stale_count": enriched["workflow_stale_count"],
                "event_count": len(evs),
                "last_activity_at": enriched["last_activity_at"],
                "signed_at": enriched["signed_at"],
                "approved_at": enriched["approved_at"],
                "review_completed_at": enriched["review_completed_at"],
                "negotiation_completed_at": enriched["negotiation_completed_at"],
                "review_status": enriched.get("review_status"),
                "approval_status": enriched.get("approval_status"),
                "signature_status": enriched.get("signature_status"),
                "negotiation_status": enriched.get("negotiation_status"),
                "events": evs,
            }
        )

    transitions = []
    for v in versions:
        if not v.parent_version_id or v.parent_version_id not in by_id:
            continue
        parent = by_id[v.parent_version_id]
        transitions.append(
            {
                "from_version_id": str(parent.id),
                "to_version_id": str(v.id),
                "reason": transition_reason(v),
                "created_at": _iso(v.created_at),
                "actor": v.created_by,
            }
        )

    return {
        "contract_id": str(contract_id),
        "current_version_id": str(cur.id) if cur else None,
        "current_version_number": cur.version_number if cur else None,
        "versions": version_payloads,
        "transitions": transitions,
    }
