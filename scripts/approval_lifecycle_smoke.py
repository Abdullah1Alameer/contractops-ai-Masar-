#!/usr/bin/env python3
"""Approval lifecycle API + DB smoke.

Seeds synthetic redacted contracts, drives every approval transition through the
live HTTP API, verifies persisted state, reads it back through the API, and
deletes every synthetic record before exiting.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
import psycopg2
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

BASE = os.getenv("QA_BASE_URL", "http://127.0.0.1:8000")
TOKEN = os.getenv("DEMO_TOKEN", "demo-secret-token")
ROLES = ["business_owner", "legal", "finance", "executive"]
OUT = ROOT / "scripts" / "approval_smoke_results.json"

created_contracts: list[str] = []
checks: list[dict] = []


def headers(role: str = "legal") -> dict:
    return {"Authorization": f"Bearer {TOKEN}", "X-Demo-Role": role}


def db_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def check(name: str, passed: bool, detail: object = None) -> None:
    checks.append({"name": name, "pass": bool(passed), "detail": detail})


def seed_contract(*, stage: str = "internal_review", with_version: bool = True, with_evidence: bool = True) -> dict:
    contract_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4()) if with_version else None
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO contracts (id, title, status, stage, supported, file_url, start_date)
            VALUES (%s, %s, 'ready', %s, true, %s, %s)
            """,
            (contract_id, "QA-approval-smoke", stage, "synthetic/qa-approval.pdf", date.today()),
        )
        if version_id:
            cur.execute(
                """
                INSERT INTO contract_versions
                    (id, contract_id, version_number, version_label, source, status, file_path, is_current, created_by)
                VALUES (%s, %s, 1, 'v1', 'initial_upload', 'ready', %s, true, 'qa-smoke')
                """,
                (version_id, contract_id, "synthetic/qa-approval.pdf"),
            )
        if with_evidence and version_id:
            cur.execute(
                """
                INSERT INTO review_requests
                    (id, contract_id, version_id, token, recipient_name, recipient_email, status, expires_at, responded_at)
                VALUES (%s, %s, %s, %s, 'QA Reviewer', 'reviewer@example.invalid', 'approved', %s, now())
                """,
                (
                    str(uuid.uuid4()),
                    contract_id,
                    version_id,
                    f"qa-smoke-{uuid.uuid4().hex}",
                    datetime.now(timezone.utc) + timedelta(days=7),
                ),
            )
        conn.commit()
    created_contracts.append(contract_id)
    return {"contract_id": contract_id, "version_id": version_id}


def seed_negotiation(contract_id: str, version_id: str) -> str:
    negotiation_id = str(uuid.uuid4())
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO negotiations
                (id, contract_id, version_id, clause_ref, reviewer_comment, reviewer_decision, status, workflow_status)
            VALUES (%s, %s, %s, '7.1', 'QA redacted comment', 'changes_requested', 'draft', 'pending_analysis')
            """,
            (negotiation_id, contract_id, version_id),
        )
        conn.commit()
    return negotiation_id


def seed_signature_request(contract_id: str, version_id: str) -> None:
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO signature_requests
                (id, contract_id, version_id, provider, status, subject, expires_at)
            VALUES (%s, %s, %s, 'simulated', 'sent', 'QA signature', %s)
            """,
            (str(uuid.uuid4()), contract_id, version_id, datetime.now(timezone.utc) + timedelta(days=7)),
        )
        conn.commit()


def supersede_version(contract_id: str) -> None:
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE contract_versions SET is_current = false WHERE contract_id = %s", (contract_id,))
        cur.execute(
            """
            INSERT INTO contract_versions
                (id, contract_id, version_number, version_label, source, status, file_path, is_current, created_by)
            VALUES (%s, %s, 2, 'v2', 'internal_revision', 'ready', %s, true, 'qa-smoke')
            """,
            (str(uuid.uuid4()), contract_id, "synthetic/qa-approval.pdf"),
        )
        conn.commit()


def db_state(contract_id: str) -> dict:
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT stage FROM contracts WHERE id = %s", (contract_id,))
        stage = (cur.fetchone() or [None])[0]
        cur.execute(
            "SELECT status, current_step_order FROM approval_workflows WHERE contract_id = %s ORDER BY created_at DESC LIMIT 1",
            (contract_id,),
        )
        workflow = cur.fetchone()
        cur.execute(
            """
            SELECT s.step_order, s.role, s.status
            FROM approval_steps s
            JOIN approval_workflows w ON w.id = s.workflow_id
            WHERE w.contract_id = %s
            ORDER BY w.created_at DESC, s.step_order ASC
            """,
            (contract_id,),
        )
        steps = [{"step_order": r[0], "role": r[1], "status": r[2]} for r in cur.fetchall()]
        cur.execute(
            "SELECT status FROM contract_versions WHERE contract_id = %s AND is_current = true",
            (contract_id,),
        )
        version_status = (cur.fetchone() or [None])[0]
        cur.execute("SELECT COUNT(*) FROM negotiations WHERE contract_id = %s", (contract_id,))
        negotiation_count = cur.fetchone()[0]
        cur.execute(
            "SELECT event_type FROM activity_events WHERE contract_id = %s ORDER BY created_at ASC",
            (contract_id,),
        )
        events = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT COUNT(*) FROM approval_workflows WHERE contract_id = %s", (contract_id,))
        workflow_count = cur.fetchone()[0]
    return {
        "stage": stage,
        "workflow_status": workflow[0] if workflow else None,
        "current_step_order": workflow[1] if workflow else None,
        "workflow_count": workflow_count,
        "steps": steps,
        "version_status": version_status,
        "negotiation_count": negotiation_count,
        "events": events,
    }


def start(client: httpx.Client, contract_id: str, *, role: str = "legal", body: dict | None = None) -> httpx.Response:
    return client.post(
        f"/api/contracts/{contract_id}/approvals/start",
        headers=headers(role),
        json=body or {},
    )


def step_map(client: httpx.Client, contract_id: str) -> dict:
    response = client.get(f"/api/contracts/{contract_id}/approvals", headers=headers())
    workflow = response.json()["workflow"]
    return {step["role"]: step["id"] for step in workflow["steps"]}


def decide(client: httpx.Client, step_id: str, *, role: str, status: str, comment: str | None = None) -> httpx.Response:
    body: dict = {"status": status}
    if comment:
        body["comment"] = comment
    return client.patch(f"/api/approvals/{step_id}", headers=headers(role), json=body)


def scenario_full_approval(client: httpx.Client) -> None:
    seed = seed_contract()
    contract_id = seed["contract_id"]
    response = start(client, contract_id)
    check("start returns 200", response.status_code == 200, response.text[:200])
    payload = response.json()
    check("start keeps internal_review", payload.get("contract_stage") == "internal_review", payload.get("contract_stage"))
    check("start requires business_owner first", payload.get("current_required_role") == "business_owner")
    state = db_state(contract_id)
    check(
        "start locks all but first step",
        [s["status"] for s in state["steps"]] == ["pending", "locked", "locked", "locked"],
        state["steps"],
    )

    steps = step_map(client, contract_id)
    for index, role in enumerate(ROLES):
        decision = decide(client, steps[role], role=role, status="approved")
        check(f"{role} approval returns 200", decision.status_code == 200, decision.text[:200])
        interim = db_state(contract_id)
        if index < len(ROLES) - 1:
            check(
                f"stage stays internal_review after {role}",
                interim["stage"] == "internal_review",
                interim["stage"],
            )
            check(
                f"only next step unlocked after {role}",
                interim["steps"][index + 1]["status"] == "pending",
                interim["steps"],
            )

    final = db_state(contract_id)
    check("final approval sets ready_to_sign", final["stage"] == "ready_to_sign", final["stage"])
    check("workflow approved", final["workflow_status"] == "approved", final["workflow_status"])
    check("current version approved", final["version_status"] == "approved", final["version_status"])
    check("all steps approved", all(s["status"] == "approved" for s in final["steps"]), final["steps"])
    check("no negotiation seed on approval", final["negotiation_count"] == 0, final["negotiation_count"])
    for event in ("approval_workflow_started", "approval_workflow_completed", "contract_ready_to_sign"):
        check(f"event {event} persisted", event in final["events"], final["events"])

    readback = client.get(f"/api/contracts/{contract_id}/approvals", headers=headers())
    check(
        "API read-back is canonical",
        readback.json()["workflow"]["contract_stage"] == "ready_to_sign"
        and readback.json()["workflow"]["actionable"] is False,
        readback.json()["workflow"].get("contract_stage"),
    )


def scenario_guards(client: httpx.Client) -> None:
    seed = seed_contract()
    contract_id = seed["contract_id"]
    start(client, contract_id)
    steps = step_map(client, contract_id)

    wrong_role = decide(client, steps["business_owner"], role="legal", status="approved")
    check(
        "wrong role denied",
        wrong_role.status_code == 403 and wrong_role.json()["detail"]["error"] == "approval_role_required",
        wrong_role.text[:200],
    )
    out_of_order = decide(client, steps["finance"], role="finance", status="approved")
    check(
        "out of order denied",
        out_of_order.status_code == 409 and out_of_order.json()["detail"]["error"] == "approval_out_of_order",
        out_of_order.text[:200],
    )
    duplicate = start(client, contract_id)
    check(
        "duplicate start denied",
        duplicate.status_code == 409 and duplicate.json()["detail"]["error"] == "approval_already_active",
        duplicate.text[:200],
    )
    state = db_state(contract_id)
    check("guards left workflow untouched", state["steps"][0]["status"] == "pending", state["steps"])
    check("guards created no extra workflow", state["workflow_count"] == 1, state["workflow_count"])


def scenario_request_changes(client: httpx.Client) -> None:
    seed = seed_contract()
    contract_id = seed["contract_id"]
    start(client, contract_id)
    steps = step_map(client, contract_id)

    missing_reason = decide(client, steps["business_owner"], role="business_owner", status="changes_requested")
    check(
        "change request without reason denied",
        missing_reason.status_code == 422
        and missing_reason.json()["detail"]["error"] == "approval_reason_required",
        missing_reason.text[:200],
    )
    response = decide(
        client,
        steps["business_owner"],
        role="business_owner",
        status="changes_requested",
        comment="QA redacted change request",
    )
    check("change request returns 200", response.status_code == 200, response.text[:200])
    state = db_state(contract_id)
    check("stage moves to negotiation", state["stage"] == "negotiation", state["stage"])
    check("workflow changes_requested", state["workflow_status"] == "changes_requested", state["workflow_status"])
    check("exactly one negotiation seed", state["negotiation_count"] == 1, state["negotiation_count"])
    for event in ("approval_changes_requested", "contract_entered_negotiation", "negotiation_analysis_requested"):
        check(f"event {event} persisted", event in state["events"], state["events"])


def scenario_rejection(client: httpx.Client) -> None:
    seed = seed_contract()
    contract_id = seed["contract_id"]
    start(client, contract_id)
    steps = step_map(client, contract_id)

    response = decide(
        client,
        steps["business_owner"],
        role="business_owner",
        status="rejected",
        comment="QA redacted rejection",
    )
    check("rejection returns 200", response.status_code == 200, response.text[:200])
    state = db_state(contract_id)
    check("stage rejected", state["stage"] == "rejected", state["stage"])
    check("workflow rejected", state["workflow_status"] == "rejected", state["workflow_status"])
    check("rejection creates no negotiation", state["negotiation_count"] == 0, state["negotiation_count"])
    for event in ("approval_step_rejected", "approval_rejected", "contract_rejected"):
        check(f"event {event} persisted", event in state["events"], state["events"])
    duplicate = decide(
        client,
        steps["business_owner"],
        role="business_owner",
        status="rejected",
        comment="QA redacted rejection",
    )
    check(
        "duplicate rejection denied",
        duplicate.status_code == 409 and duplicate.json()["detail"]["error"] == "approval_step_closed",
        duplicate.text[:200],
    )


def scenario_cancellation(client: httpx.Client) -> None:
    seed = seed_contract()
    contract_id = seed["contract_id"]
    start(client, contract_id)

    missing_reason = client.post(
        f"/api/contracts/{contract_id}/approvals/cancel",
        headers=headers(),
        json={},
    )
    check(
        "cancel without reason denied",
        missing_reason.status_code == 422
        and missing_reason.json()["detail"]["error"] == "approval_reason_required",
        missing_reason.text[:200],
    )
    response = client.post(
        f"/api/contracts/{contract_id}/approvals/cancel",
        headers=headers(),
        json={"reason": "QA redacted cancellation"},
    )
    check("cancel returns 200", response.status_code == 200, response.text[:200])
    state = db_state(contract_id)
    check("cancel keeps internal_review", state["stage"] == "internal_review", state["stage"])
    check("workflow cancelled", state["workflow_status"] == "cancelled", state["workflow_status"])
    check("cancel locks steps", all(s["status"] == "locked" for s in state["steps"]), state["steps"])
    check("event approval_workflow_cancelled persisted", "approval_workflow_cancelled" in state["events"])
    restart = start(client, contract_id)
    check("restart allowed after cancel", restart.status_code == 200, restart.text[:200])
    check("restart created second workflow", db_state(contract_id)["workflow_count"] == 2)


def scenario_unresolved_and_override(client: httpx.Client) -> None:
    seed = seed_contract()
    contract_id, version_id = seed["contract_id"], seed["version_id"]
    negotiation_id = seed_negotiation(contract_id, version_id)

    blocked = start(client, contract_id)
    check(
        "unresolved negotiation blocks start",
        blocked.status_code == 409 and blocked.json()["detail"]["error"] == "unresolved_negotiations",
        blocked.text[:200],
    )
    check("blocked start created no workflow", db_state(contract_id)["workflow_count"] == 0)

    legacy_force = start(client, contract_id, body={"force": True})
    check(
        "legacy force denied",
        legacy_force.status_code == 422
        and legacy_force.json()["detail"]["error"] == "approval_reason_required",
        legacy_force.text[:200],
    )

    override_body = {
        "override": {"reason": "QA redacted override", "negotiation_ids": [negotiation_id]}
    }
    unauthorized = start(client, contract_id, role="finance", body=override_body)
    check(
        "override denied for finance",
        unauthorized.status_code == 403
        and unauthorized.json()["detail"]["error"] == "approval_role_required",
        unauthorized.text[:200],
    )
    no_reason = start(
        client,
        contract_id,
        body={"override": {"negotiation_ids": [negotiation_id]}},
    )
    check(
        "override without reason denied",
        no_reason.status_code == 422 and no_reason.json()["detail"]["error"] == "approval_reason_required",
        no_reason.text[:200],
    )

    approved_override = start(client, contract_id, body=override_body)
    check("legal override accepted", approved_override.status_code == 200, approved_override.text[:200])
    check("override flagged on workflow", approved_override.json().get("override_used") is True)
    state = db_state(contract_id)
    check("override kept every step", len(state["steps"]) == len(ROLES), state["steps"])
    check("override_used event persisted", "approval_override_used" in state["events"], state["events"])
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT workflow_status, final_summary->'lifecycle'->>'closure_outcome' FROM negotiations WHERE id = %s",
            (negotiation_id,),
        )
        row = cur.fetchone()
        cur.execute(
            "SELECT metadata FROM activity_events WHERE contract_id = %s AND event_type = 'approval_override_used'",
            (contract_id,),
        )
        override_metadata = cur.fetchone()[0]
    check("overridden item closed with outcome", row == ("closed", "approval_overridden"), row)
    check(
        "override audit records ids without reason text",
        override_metadata.get("overridden_negotiation_ids") == [negotiation_id]
        and override_metadata.get("reason_present") is True
        and "QA redacted override" not in json.dumps(override_metadata),
        override_metadata,
    )


def scenario_stale_and_signature(client: httpx.Client) -> None:
    seed = seed_contract()
    contract_id = seed["contract_id"]
    start(client, contract_id)
    steps = step_map(client, contract_id)
    supersede_version(contract_id)

    stale = decide(client, steps["business_owner"], role="business_owner", status="approved")
    check(
        "stale workflow decision denied",
        stale.status_code == 409 and stale.json()["detail"]["error"] == "workflow_stale",
        stale.text[:200],
    )
    state = db_state(contract_id)
    check("stale attempt left step pending", state["steps"][0]["status"] == "pending", state["steps"])
    check("stale attempt kept internal_review", state["stage"] == "internal_review", state["stage"])

    signature_seed = seed_contract()
    seed_signature_request(signature_seed["contract_id"], signature_seed["version_id"])
    blocked = start(client, signature_seed["contract_id"])
    check(
        "active signature blocks start",
        blocked.status_code == 409 and blocked.json()["detail"]["error"] == "signature_request_active",
        blocked.text[:200],
    )
    check(
        "signature block created no workflow",
        db_state(signature_seed["contract_id"])["workflow_count"] == 0,
    )


def cleanup() -> dict:
    deleted = 0
    with db_conn() as conn:
        cur = conn.cursor()
        for contract_id in created_contracts:
            cur.execute("DELETE FROM contracts WHERE id = %s", (contract_id,))
            deleted += cur.rowcount
        conn.commit()
        cur.execute(
            "SELECT COUNT(*) FROM contracts WHERE title = 'QA-approval-smoke'",
        )
        remaining = cur.fetchone()[0]
        residue = {}
        for table in ("approval_workflows", "approval_steps", "activity_events", "negotiations"):
            cur.execute(
                f"SELECT COUNT(*) FROM {table} WHERE contract_id = ANY(%s::uuid[])",
                (created_contracts,),
            )
            residue[table] = cur.fetchone()[0]
    return {"deleted": deleted, "remaining_qa_contracts": remaining, "residue": residue}


def main() -> int:
    scenarios = (
        scenario_full_approval,
        scenario_guards,
        scenario_request_changes,
        scenario_rejection,
        scenario_cancellation,
        scenario_unresolved_and_override,
        scenario_stale_and_signature,
    )
    error = None
    try:
        with httpx.Client(base_url=BASE, timeout=60.0) as client:
            for scenario in scenarios:
                scenario(client)
    except Exception as exc:  # noqa: BLE001 - smoke harness reports and still cleans up
        error = f"{type(exc).__name__}: {exc}"
    finally:
        cleanup_report = cleanup()

    failed = [row for row in checks if not row["pass"]]
    summary = {
        "base_url": BASE,
        "checks_total": len(checks),
        "checks_passed": len(checks) - len(failed),
        "checks_failed": len(failed),
        "cleanup": cleanup_report,
        "error": error,
    }
    OUT.write_text(json.dumps({"summary": summary, "checks": checks}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    for row in failed:
        print("FAILED:", row["name"], row["detail"])
    return 0 if not failed and error is None else 1


if __name__ == "__main__":
    sys.exit(main())
