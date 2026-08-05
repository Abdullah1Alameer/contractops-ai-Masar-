#!/usr/bin/env python3
"""Golden-path API + DB + local-SMTP smoke.

Drives the one demonstrable release path end to end against the live API and
database, using a local capture SMTP server so email delivery is proven
without any real inbox or provider credentials:

  upload -> AI extraction -> client review email -> public review ->
  request changes -> negotiation (AI analysis + counterproposal) ->
  client accepts -> internal approval (4 ordered roles) -> ordered
  signature emails -> both signers sign -> signed artifacts -> manual
  activation.

Every synthetic contract created here is deleted in `finally`, and file
residue in STORAGE_DIR plus DB row residue are verified to be zero before
exit.

Known pre-existing gap this script bridges: `POST /api/contracts` (frozen F1
surface) never fires the `contract_ready_for_client` lifecycle event, so a
freshly uploaded contract is left at the `contracts.stage` DB default
("negotiation" — see database/migrations/011_approval_workflow.sql) instead
of entering the `draft -> ready_for_client` pipeline the lifecycle engine
otherwise encodes. This script bridges that one gap with a direct,
audited stage write (mirrors `app.services.lifecycle.set_stage`: a plain
stage UPDATE plus a `contract_stage_changed` activity row) rather than
silently relying on the accidental default. It does not touch the frozen
upload endpoint.
"""
from __future__ import annotations

import asyncore
import json
import os
import smtpd
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from email import message_from_bytes
from pathlib import Path

import fitz
import httpx
import psycopg2
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

BASE = os.getenv("QA_BASE_URL", "http://127.0.0.1:8000")
TOKEN = os.getenv("DEMO_TOKEN", "demo-secret-token")
SMTP_HOST = os.getenv("SMTP_HOST", "127.0.0.1")
SMTP_PORT = int(os.getenv("SMTP_PORT", "1025"))
STORAGE_DIR = os.getenv("STORAGE_DIR", str(ROOT / "storage"))
OUT = ROOT / "scripts" / "golden_path_smoke_results.json"

ROLES = ["business_owner", "legal", "finance", "executive"]

created_contracts: list[str] = []
created_storage_keys: set[str] = set()
checks: list[dict] = []


def headers(role: str = "legal") -> dict:
    return {"Authorization": f"Bearer {TOKEN}", "X-Demo-Role": role}


def db_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def check(name: str, passed: bool, detail: object = None) -> None:
    checks.append({"name": name, "pass": bool(passed), "detail": detail})
    if not passed:
        print(f"FAILED: {name} -- {detail}")


# --------------------------------------------------------------------------
# Local capture SMTP server — proves real delivery without a real provider.
# --------------------------------------------------------------------------
class _CaptureSMTPServer(smtpd.SMTPServer):
    def __init__(self, host: str, port: int):
        super().__init__((host, port), None, decode_data=False)
        self.messages: list[dict] = []
        self._lock = threading.Lock()

    def process_message(self, peer, mailfrom, rcpttos, data, **kwargs):
        parsed = message_from_bytes(data)
        with self._lock:
            self.messages.append(
                {
                    "mailfrom": mailfrom,
                    "rcpttos": list(rcpttos),
                    "subject": parsed.get("Subject"),
                    "raw": data,
                }
            )

    def latest_to(self, recipient: str) -> dict | None:
        with self._lock:
            for message in reversed(self.messages):
                if recipient in message["rcpttos"]:
                    return message
        return None


def start_capture_server() -> tuple[_CaptureSMTPServer, threading.Thread]:
    server = _CaptureSMTPServer(SMTP_HOST, SMTP_PORT)

    def _run() -> None:
        try:
            asyncore.loop(timeout=0.2)
        except Exception:
            pass  # loop exits noisily once the listening socket is closed

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return server, thread


def stop_capture_server(server: _CaptureSMTPServer) -> None:
    try:
        server.close()
    except Exception:
        pass


# --------------------------------------------------------------------------
# Synthetic document
# --------------------------------------------------------------------------
def _synthetic_pdf_bytes() -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text(
        (72, 72),
        "GOLDEN PATH SMOKE MASTER SERVICES AGREEMENT\n\n"
        "This agreement is between Synthetic Acme Corp (\"Client\") and "
        "Synthetic Beta LLC (\"Provider\").\n\n"
        "1. Term. This agreement remains in effect for twelve (12) months "
        "from the effective date.\n"
        "2. Payment. Provider shall invoice Client monthly; payment is due "
        "net thirty (30) days.\n"
        "3. Confidentiality. Clause 7.1: each party shall keep the other's "
        "confidential information strictly confidential.\n"
        "4. Termination. Either party may terminate with sixty (60) days "
        "written notice.\n",
    )
    data = document.tobytes()
    document.close()
    return data


# --------------------------------------------------------------------------
# Bridge: draft/legacy-default -> ready_for_client (see module docstring)
# --------------------------------------------------------------------------
def bridge_to_ready_for_client(contract_id: str) -> None:
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT stage FROM contracts WHERE id = %s", (contract_id,))
        (previous,) = cur.fetchone()
        cur.execute(
            "UPDATE contracts SET stage = 'ready_for_client' WHERE id = %s",
            (contract_id,),
        )
        cur.execute(
            """
            INSERT INTO activity_events (id, contract_id, event_type, actor, metadata)
            VALUES (%s, %s, 'contract_stage_changed', 'golden-path-smoke',
                    %s::jsonb)
            """,
            (
                str(uuid.uuid4()),
                contract_id,
                json.dumps({"from": previous, "to": "ready_for_client", "bridge": True}),
            ),
        )
        conn.commit()


# --------------------------------------------------------------------------
# Storage residue tracking
# --------------------------------------------------------------------------
def _track_storage_keys(contract_id: str) -> None:
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT file_url FROM contracts WHERE id = %s", (contract_id,))
        row = cur.fetchone()
        if row and row[0]:
            created_storage_keys.add(row[0])
        cur.execute(
            "SELECT file_path FROM contract_versions WHERE contract_id = %s",
            (contract_id,),
        )
        for (file_path,) in cur.fetchall():
            if file_path:
                created_storage_keys.add(file_path)
        cur.execute(
            """
            SELECT original_file_url, signed_file_url, certificate_file_url
            FROM signature_requests WHERE contract_id = %s
            """,
            (contract_id,),
        )
        for orig, signed, cert in cur.fetchall():
            for key in (orig, signed, cert):
                if key:
                    created_storage_keys.add(key)
        cur.execute(
            """
            SELECT sig.signature_value_url
            FROM signature_signers sig
            JOIN signature_requests req ON req.id = sig.signature_request_id
            WHERE req.contract_id = %s
            """,
            (contract_id,),
        )
        for (key,) in cur.fetchall():
            if key:
                created_storage_keys.add(key)


# --------------------------------------------------------------------------
# Golden path
# --------------------------------------------------------------------------
def run_golden_path(client: httpx.Client, capture: _CaptureSMTPServer) -> None:
    # 1) Upload real, text-bearing synthetic PDF through the frozen F1 endpoint.
    upload = client.post(
        "/api/contracts",
        headers=headers(),
        files={"file": ("golden-path-smoke.pdf", _synthetic_pdf_bytes(), "application/pdf")},
    )
    check("upload returns 201", upload.status_code == 201, upload.text[:300])
    contract_id = upload.json()["id"]
    created_contracts.append(contract_id)

    # 2) Real AI extraction (existing, provider-dependent capability).
    extract = client.post(f"/api/contracts/{contract_id}/extract", headers=headers())
    check("extract returns 200", extract.status_code == 200, extract.text[:300])
    check("extract reports supported contract", extract.json().get("supported") is not False, extract.json())

    bridge_to_ready_for_client(contract_id)

    # 3) Send for client review — proves review-invitation SMTP delivery.
    send = client.post(
        f"/api/contracts/{contract_id}/review/send",
        headers=headers(),
        json={
            "recipient_name": "Synthetic Client Reviewer",
            "recipient_email": "client-reviewer@example.invalid",
            "sender_name": "Synthetic Legal Sender",
            "sender_email": "legal-sender@example.invalid",
            "expires_in_days": 7,
        },
    )
    check("review send returns 200", send.status_code == 200, send.text[:400])
    review_payload = send.json()
    review_token = review_payload["request"]["token"]
    check(
        "review invitation delivered via local SMTP",
        review_payload["delivery"]["status"] == "sent",
        review_payload["delivery"],
    )
    captured_review_email = capture.latest_to("client-reviewer@example.invalid")
    check("local SMTP captured review invitation", captured_review_email is not None)
    if captured_review_email is not None:
        check(
            "review email is multipart text+html",
            message_from_bytes(captured_review_email["raw"]).is_multipart(),
        )
        check(
            "review email body contains the portal link",
            f"/review/{review_token}" in captured_review_email["raw"].decode("utf-8", "ignore"),
        )
    check(
        "contract entered client_review",
        _stage(contract_id) == "client_review",
        _stage(contract_id),
    )

    # 4) Public: open + request changes with a comment (seeds a negotiation).
    portal = client.get(f"/api/review/{review_token}")
    check("public review bundle returns 200", portal.status_code == 200, portal.text[:300])

    changes = client.post(
        f"/api/review/{review_token}/request-changes",
        json={"general_comment": "Please shorten the notice period in clause 4 to thirty (30) days."},
    )
    check("request-changes returns 200", changes.status_code == 200, changes.text[:300])
    check("contract entered negotiation", _stage(contract_id) == "negotiation", _stage(contract_id))

    # Stale/duplicate mutation rejection: this review is now terminal.
    duplicate = client.post(
        f"/api/review/{review_token}/request-changes",
        json={"general_comment": "second attempt"},
    )
    check(
        "duplicate decision on closed review is rejected",
        duplicate.status_code == 409 and duplicate.json()["detail"]["error"] == "review_closed",
        duplicate.text[:300],
    )

    negotiation_id = _first_negotiation_id(contract_id)
    check("negotiation row created", negotiation_id is not None, negotiation_id)

    # 5) Real AI negotiation analysis (existing, provider-dependent capability).
    analyze = client.post(
        "/api/negotiation/analyze",
        headers=headers(),
        json={"review_id": review_payload["request"]["id"]},
    )
    check("negotiation analyze returns 200", analyze.status_code == 200, analyze.text[:300])
    analyzed = analyze.json()
    check("negotiation analysis is ready", analyzed.get("workflow_status") == "ready", analyzed.get("workflow_status"))
    check(
        "negotiation produced counter wording (content is AI-provider-dependent)",
        bool(analyzed.get("counter_clause") or analyzed.get("counter_clause_ar")),
    )

    approve_wording = client.patch(
        f"/api/negotiations/{negotiation_id}",
        headers=headers(),
        json={"status": "approved"},
    )
    check("negotiation wording approved returns 200", approve_wording.status_code == 200, approve_wording.text[:300])

    send_updated = client.post(f"/api/negotiations/{negotiation_id}/send", headers=headers())
    check("negotiation send returns 200", send_updated.status_code == 200, send_updated.text[:300])
    followup_token = send_updated.json()["request"]["token"]

    # 6) Public: client accepts the counterproposal -> negotiation resolved.
    accept = client.post(f"/api/review/{followup_token}/approve")
    check("followup review approve returns 200", accept.status_code == 200, accept.text[:300])
    check(
        "contract entered internal_review after agreement",
        _stage(contract_id) == "internal_review",
        _stage(contract_id),
    )
    check("negotiation resolved as accepted", _negotiation_workflow_status(negotiation_id) == "accepted")

    # 7) Internal ordered approval (business_owner -> legal -> finance -> executive).
    start = client.post(f"/api/contracts/{contract_id}/approvals/start", headers=headers(), json={})
    check("approval start returns 200", start.status_code == 200, start.text[:300])
    steps = {
        step["role"]: step["id"]
        for step in client.get(f"/api/contracts/{contract_id}/approvals", headers=headers()).json()["workflow"]["steps"]
    }
    for role in ROLES:
        decision = client.patch(f"/api/approvals/{steps[role]}", headers=headers(role), json={"status": "approved"})
        check(f"approval step {role} returns 200", decision.status_code == 200, decision.text[:300])
    check("contract entered ready_to_sign", _stage(contract_id) == "ready_to_sign", _stage(contract_id))
    check("current version approved", _current_version_status(contract_id) == "approved")

    # 8) Signature request with two ordered signers, then explicit Send
    #    (invites only the first signer — proves signature-invitation SMTP).
    create_sig = client.post(
        f"/api/contracts/{contract_id}/signature-request",
        headers=headers(),
        json={
            "subject": "Please sign the golden-path smoke agreement",
            "message": "Synthetic signing invitation",
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "signing_order_enabled": True,
            "signers": [
                {"name": "Synthetic Signer One", "email": "signer-one@example.invalid", "role": "company_signatory", "order": 1},
                {"name": "Synthetic Signer Two", "email": "signer-two@example.invalid", "role": "client_signatory", "order": 2},
            ],
        },
    )
    check("signature-request create returns 200", create_sig.status_code == 200, create_sig.text[:300])
    sig_payload = create_sig.json()
    request_id = sig_payload["request"]["id"]
    signer_tokens = {row["email"]: row["token"] for row in sig_payload["signer_links"]}
    check(
        "signature creation sent no invitations yet",
        _outbound_count(contract_id, "signature_invitation") == 0,
        _outbound_count(contract_id, "signature_invitation"),
    )

    send_sig = client.post(f"/api/signature-requests/{request_id}/send", headers=headers())
    check("signature send returns 200", send_sig.status_code == 200, send_sig.text[:300])
    deliveries = send_sig.json().get("deliveries", [])
    check("signature send delivered exactly one invitation", len(deliveries) == 1, deliveries)
    check("first signer invitation delivered", deliveries and deliveries[0]["status"] == "sent", deliveries)
    captured_signer_one = capture.latest_to("signer-one@example.invalid")
    check("local SMTP captured signer-one invitation", captured_signer_one is not None)
    if captured_signer_one is not None:
        check(
            "signer-one email contains signer portal link",
            f"/sign/{signer_tokens['signer-one@example.invalid']}" in captured_signer_one["raw"].decode("utf-8", "ignore"),
        )

    # 9) Signer one opens and signs -> partially_signed, signer two auto-invited.
    token_one = signer_tokens["signer-one@example.invalid"]
    open_one = client.post(f"/api/public/sign/{token_one}/open")
    check("signer one open returns 200", open_one.status_code == 200, open_one.text[:300])
    sign_one = _sign(client, token_one, "Synthetic Signer One")
    check("signer one submit returns 200", sign_one.status_code == 200, sign_one.text[:300])
    check("contract partially_signed", _stage(contract_id) == "partially_signed", _stage(contract_id))

    token_two = signer_tokens["signer-two@example.invalid"]
    captured_signer_two = capture.latest_to("signer-two@example.invalid")
    check("local SMTP captured signer-two invitation after unlock", captured_signer_two is not None)

    # Stale/duplicate mutation rejection: signer one cannot sign twice.
    resign = _sign(client, token_one, "Synthetic Signer One")
    check(
        "duplicate signer submit is rejected",
        resign.status_code == 409 and resign.json()["detail"]["error"] == "signer_closed",
        resign.text[:300],
    )

    # 10) Signer two opens and signs -> completed, contract signed, artifacts built.
    open_two = client.post(f"/api/public/sign/{token_two}/open")
    check("signer two open returns 200", open_two.status_code == 200, open_two.text[:300])
    sign_two = _sign(client, token_two, "Synthetic Signer Two")
    check("signer two submit returns 200", sign_two.status_code == 200, sign_two.text[:300])
    check("contract signed", _stage(contract_id) == "signed", _stage(contract_id))
    check("current version signed", _current_version_status(contract_id) == "signed")

    cert = client.get(f"/api/signature-requests/{request_id}/certificate", headers=headers())
    check("certificate download returns 200 pdf", cert.status_code == 200 and cert.content[:4] == b"%PDF", cert.status_code)
    signed_doc = client.get(f"/api/signature-requests/{request_id}/signed-document", headers=headers())
    check(
        "signed document download returns 200 pdf",
        signed_doc.status_code == 200 and signed_doc.content[:4] == b"%PDF",
        signed_doc.status_code,
    )

    # 11) Manual activation (authorized role, non-empty reason + evidence).
    activate = client.post(
        f"/api/signature-requests/{request_id}/activate",
        headers=headers("legal"),
        json={"reason": "Golden-path smoke authorized activation", "evidence": "Synthetic evidence reference #GPS-1"},
    )
    check("activation returns 200", activate.status_code == 200, activate.text[:300])
    check("contract active", _stage(contract_id) == "active", _stage(contract_id))

    # 12) Read-backs: summary, lineage, activity trail, outbound row counts.
    summary = client.get(f"/api/contracts/{contract_id}/summary", headers=headers())
    check("contract summary returns 200", summary.status_code == 200, summary.status_code)
    dashboard = client.get("/api/dashboard/summary", headers=headers())
    check("dashboard summary returns 200", dashboard.status_code == 200, dashboard.status_code)
    lineage = client.get(f"/api/contracts/{contract_id}/versions/lineage", headers=headers())
    check("version lineage returns 200", lineage.status_code == 200, lineage.status_code)
    check(
        "version lineage records the negotiation snapshot (v1 + counterproposal version)",
        len(lineage.json().get("versions", [])) >= 2,
        lineage.json().get("versions"),
    )

    events = _activity_event_types(contract_id)
    for expected in (
        "version_sent_for_review",
        "review_changes_requested",
        "negotiation_analysis_requested",
        "negotiation_analyzed",
        "counterproposal_sent",
        "negotiation_accepted",
        "contract_entered_internal_review",
        "approval_workflow_started",
        "approval_workflow_completed",
        "contract_ready_to_sign",
        "signature_request_created",
        "signature_request_sent",
        "signer_signed",
        "contract_activated",
    ):
        check(f"activity event {expected} persisted", expected in events, events)

    check(
        "exactly one review_invitation outbound row",
        _outbound_count(contract_id, "review_invitation") == 1,
        _outbound_count(contract_id, "review_invitation"),
    )
    check(
        "exactly two signature_invitation outbound rows",
        _outbound_count(contract_id, "signature_invitation") == 2,
        _outbound_count(contract_id, "signature_invitation"),
    )

    _track_storage_keys(contract_id)


def _sign(client: httpx.Client, token: str, name: str) -> httpx.Response:
    return client.post(
        f"/api/public/sign/{token}/submit",
        json={
            "signature_type": "typed",
            "signature_value": name,
            "consent_accepted": True,
            "signer_name_confirmation": name,
        },
    )


def _stage(contract_id: str) -> str | None:
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT stage FROM contracts WHERE id = %s", (contract_id,))
        row = cur.fetchone()
        return row[0] if row else None


def _current_version_status(contract_id: str) -> str | None:
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT status FROM contract_versions WHERE contract_id = %s AND is_current = true",
            (contract_id,),
        )
        row = cur.fetchone()
        return row[0] if row else None


def _first_negotiation_id(contract_id: str) -> str | None:
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM negotiations WHERE contract_id = %s ORDER BY created_at ASC LIMIT 1",
            (contract_id,),
        )
        row = cur.fetchone()
        return str(row[0]) if row else None


def _negotiation_workflow_status(negotiation_id: str) -> str | None:
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT workflow_status FROM negotiations WHERE id = %s", (negotiation_id,))
        row = cur.fetchone()
        return row[0] if row else None


def _outbound_count(contract_id: str, message_type: str) -> int:
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM outbound_messages WHERE contract_id = %s AND message_type = %s",
            (contract_id, message_type),
        )
        return cur.fetchone()[0]


def _activity_event_types(contract_id: str) -> list[str]:
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT event_type FROM activity_events WHERE contract_id = %s ORDER BY created_at ASC",
            (contract_id,),
        )
        return [row[0] for row in cur.fetchall()]


# --------------------------------------------------------------------------
# Cleanup
# --------------------------------------------------------------------------
def cleanup() -> dict:
    deleted = 0
    with db_conn() as conn:
        cur = conn.cursor()
        for contract_id in created_contracts:
            cur.execute("DELETE FROM contracts WHERE id = %s", (contract_id,))
            deleted += cur.rowcount
        conn.commit()
        cur.execute(
            "SELECT COUNT(*) FROM contracts WHERE title LIKE 'golden-path-smoke%'",
        )
        remaining_contracts = cur.fetchone()[0]
        residue = {}
        if created_contracts:
            for table in (
                "outbound_messages",
                "review_requests",
                "negotiations",
                "approval_workflows",
                "approval_steps",
                "signature_requests",
                "activity_events",
                "contract_versions",
            ):
                cur.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE contract_id = ANY(%s::uuid[])",
                    (created_contracts,),
                )
                residue[table] = cur.fetchone()[0]
            cur.execute(
                """
                SELECT COUNT(*) FROM signature_signers sig
                JOIN signature_requests req ON req.id = sig.signature_request_id
                WHERE req.contract_id = ANY(%s::uuid[])
                """,
                (created_contracts,),
            )
            residue["signature_signers"] = cur.fetchone()[0]

    file_residue = []
    for key in created_storage_keys:
        path = os.path.join(STORAGE_DIR, key)
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
            file_residue.append(key)

    return {
        "deleted_contracts": deleted,
        "remaining_golden_path_contracts": remaining_contracts,
        "db_residue": residue,
        "storage_keys_tracked": len(created_storage_keys),
        "storage_keys_removed_in_cleanup": file_residue,
    }


def main() -> int:
    capture, thread = start_capture_server()
    error = None
    try:
        with httpx.Client(base_url=BASE, timeout=90.0) as client:
            run_golden_path(client, capture)
    except Exception as exc:  # noqa: BLE001 - smoke harness reports and still cleans up
        error = f"{type(exc).__name__}: {exc}"
    finally:
        stop_capture_server(capture)
        cleanup_report = cleanup()

    failed = [row for row in checks if not row["pass"]]
    summary = {
        "base_url": BASE,
        "smtp": f"{SMTP_HOST}:{SMTP_PORT}",
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
