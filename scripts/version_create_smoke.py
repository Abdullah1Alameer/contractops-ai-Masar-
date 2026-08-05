#!/usr/bin/env python3
"""Create-New-Version end-to-end smoke (upload -> extract -> new version).

Runs the real Contract Versions flow against a live API and Postgres on a
disposable contract, verifies version rows, lineage, activity and relinked
engine rows, then deletes the synthetic contract.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
import psycopg2
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

BASE = os.getenv("QA_BASE_URL", "http://127.0.0.1:8000")
TOKEN = os.getenv("DEMO_TOKEN", "demo-secret-token")
DOCX = ROOT / "database" / "demo_contracts" / "sub_contract.docx"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "X-Demo-Role": "legal"}
OUT = ROOT / "scripts" / "version_create_smoke_results.json"

checks: list[dict] = []


def check(name: str, passed: bool, detail: object = None) -> None:
    checks.append({"name": name, "pass": bool(passed), "detail": detail})


def db_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def snapshot(contract_id: str) -> dict:
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT status, stage FROM contracts WHERE id=%s", (contract_id,))
        contract = cur.fetchone()
        cur.execute(
            "SELECT version_number, source, status, is_current, change_summary, file_path"
            " FROM contract_versions WHERE contract_id=%s ORDER BY version_number",
            (contract_id,),
        )
        versions = cur.fetchall()
        counts = {}
        for table, column in (
            ("clauses", None),
            ("deadlines", "source_clause_id"),
            ("payment_milestones", "source_clause_id"),
            ("obligations", "source_clause_id"),
            ("extractions", "clause_id"),
        ):
            if column:
                cur.execute(f"SELECT COUNT(*), COUNT({column}) FROM {table} WHERE contract_id=%s", (contract_id,))
                counts[table] = cur.fetchone()
            else:
                cur.execute(f"SELECT COUNT(*) FROM {table} WHERE contract_id=%s", (contract_id,))
                counts[table] = (cur.fetchone()[0], None)
        cur.execute(
            "SELECT event_type, metadata->>'version_number' FROM activity_events"
            " WHERE contract_id=%s ORDER BY created_at",
            (contract_id,),
        )
        events = cur.fetchall()
        cur.execute(
            """
            SELECT COUNT(*) FROM deadlines d
            WHERE d.contract_id=%s AND d.source_clause_id IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM clauses c WHERE c.id = d.source_clause_id)
            """,
            (contract_id,),
        )
        dangling_deadlines = cur.fetchone()[0]
    return {
        "contract": contract,
        "versions": versions,
        "counts": counts,
        "events": events,
        "dangling_deadline_links": dangling_deadlines,
    }


def main() -> int:
    if not DOCX.exists():
        print(f"missing fixture {DOCX}")
        return 1
    payload = DOCX.read_bytes()
    contract_id = None
    error = None

    try:
        with httpx.Client(base_url=BASE, timeout=300.0) as client:
            upload = client.post(
                "/api/contracts",
                headers=HEADERS,
                files={"file": ("qa-version-smoke.docx", payload, "application/octet-stream")},
            )
            check("upload returns 201", upload.status_code == 201, upload.text[:200])
            contract_id = upload.json()["id"]

            extract = client.post(f"/api/contracts/{contract_id}/extract", headers=HEADERS)
            check("initial extraction succeeds", extract.status_code == 200, extract.text[:300])

            before = snapshot(contract_id)
            check("v1 exists after upload", [r[0] for r in before["versions"]] == [1], before["versions"])
            check("v1 produced clauses", before["counts"]["clauses"][0] > 0, before["counts"])
            check(
                "engine rows reference clauses before revision",
                before["counts"]["deadlines"][1] > 0 or before["counts"]["payment_milestones"][1] > 0,
                {k: before["counts"][k] for k in ("deadlines", "payment_milestones")},
            )

            create = client.post(
                f"/api/contracts/{contract_id}/versions",
                headers=HEADERS,
                files={"file": ("qa-version-smoke-v2.docx", payload, "application/octet-stream")},
                data={"source": "client_revision", "change_summary": "Client Review"},
            )
            check("create new version returns 201", create.status_code == 201, create.text[:400])
            if create.status_code != 201:
                raise RuntimeError(f"create version failed: {create.status_code} {create.text[:400]}")
            created = create.json()
            check("response reports v2", created.get("version_number") == 2, created.get("version_number"))

            after = snapshot(contract_id)
            check("exactly two versions, no duplicates", [r[0] for r in after["versions"]] == [1, 2], after["versions"])
            check("v2 is current", after["versions"][1][3] is True, after["versions"][1])
            check("v1 is no longer current", after["versions"][0][3] is False, after["versions"][0])
            check("v2 records the change reason", after["versions"][1][4] == "Client Review", after["versions"][1][4])
            check("v2 source is client_revision", after["versions"][1][1] == "client_revision", after["versions"][1][1])
            check(
                "v2 finished processing",
                after["versions"][1][2] in ("ready", "needs_review"),
                after["versions"][1][2],
            )
            check(
                "contract left processing state",
                after["contract"][0] in ("ready", "needs_review"),
                after["contract"],
            )
            check("re-extraction produced clauses", after["counts"]["clauses"][0] > 0, after["counts"])
            check("no dangling clause links", after["dangling_deadline_links"] == 0, after["dangling_deadline_links"])
            check(
                "engine rows relinked to new clauses",
                after["counts"]["deadlines"][1] > 0 or after["counts"]["payment_milestones"][1] > 0,
                {k: after["counts"][k] for k in ("deadlines", "payment_milestones")},
            )

            version_events = [e for e in after["events"] if e[0] == "version_created"]
            check(
                "version_created activity recorded for v2",
                any(e[1] == "2" for e in version_events),
                after["events"],
            )
            check(
                "no duplicate version_created events",
                len(version_events) == len({e[1] for e in version_events}),
                version_events,
            )

            listing = client.get(f"/api/contracts/{contract_id}/versions", headers=HEADERS)
            check(
                "versions API shows both versions",
                [v["version_number"] for v in listing.json()["versions"]] == [2, 1]
                or [v["version_number"] for v in listing.json()["versions"]] == [1, 2],
                [v["version_number"] for v in listing.json()["versions"]],
            )
            check("versions API current is 2", listing.json()["current_version_number"] == 2)

            lineage = client.get(f"/api/contracts/{contract_id}/versions/lineage", headers=HEADERS)
            check("lineage returns 200", lineage.status_code == 200, lineage.text[:200])
            nodes = lineage.json().get("versions") or lineage.json().get("nodes") or []
            numbers = [n.get("version_number") for n in nodes]
            check("lineage includes v2", 2 in numbers, numbers)
            v2_node = next((n for n in nodes if n.get("version_number") == 2), {})
            lineage_events = [e.get("event_type") for e in (v2_node.get("events") or [])]
            check("lineage v2 has version_created", "version_created" in lineage_events, lineage_events)
            v1_node = next((n for n in nodes if n.get("version_number") == 1), {})
            check(
                "lineage links v2 to its parent",
                v2_node.get("parent_version_id") == v1_node.get("id") and v1_node.get("id") is not None,
                {"parent": v2_node.get("parent_version_id"), "v1": v1_node.get("id")},
            )

            activity = client.get(f"/api/contracts/{contract_id}/activity", headers=HEADERS)
            types = [e["event_type"] for e in activity.json()["events"]]
            check("activity API exposes version_created", "version_created" in types, types[:12])
    except Exception as exc:  # noqa: BLE001 - smoke harness reports and still cleans up
        error = f"{type(exc).__name__}: {exc}"
    finally:
        cleanup = {"deleted": None, "remaining": None}
        if contract_id:
            with httpx.Client(base_url=BASE, timeout=60.0) as client:
                delete = client.delete(f"/api/contracts/{contract_id}", headers=HEADERS)
                cleanup["deleted"] = delete.status_code
            with db_conn() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM contracts WHERE id=%s", (contract_id,))
                cleanup["remaining"] = cur.fetchone()[0]
                residue = {}
                for table in ("contract_versions", "clauses", "deadlines", "payment_milestones", "activity_events"):
                    cur.execute(f"SELECT COUNT(*) FROM {table} WHERE contract_id=%s", (contract_id,))
                    residue[table] = cur.fetchone()[0]
                cleanup["residue"] = residue

    failed = [row for row in checks if not row["pass"]]
    summary = {
        "base_url": BASE,
        "contract_id": contract_id,
        "checks_total": len(checks),
        "checks_passed": len(checks) - len(failed),
        "checks_failed": len(failed),
        "cleanup": cleanup,
        "error": error,
    }
    OUT.write_text(json.dumps({"summary": summary, "checks": checks}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    for row in failed:
        print("FAILED:", row["name"], row["detail"])
    return 0 if not failed and error is None else 1


if __name__ == "__main__":
    sys.exit(main())
