#!/usr/bin/env python3
"""Hackathon QA API + DB smoke. Uses disposable QA-* contracts only; cleans up at end."""
from __future__ import annotations

import io
import json
import os
import sys
import time
import uuid
from datetime import date
from pathlib import Path

import httpx
import psycopg2
from docx import Document
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

BASE = os.getenv("QA_BASE_URL", "http://127.0.0.1:8000")
TOKEN = os.getenv("DEMO_TOKEN", "demo-secret-token")
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
SUB_DOC = ROOT / "database" / "demo_contracts" / "sub_contract.docx"
OUT = ROOT / "scripts" / "qa_results.json"

results: dict = {
    "base_url": BASE,
    "endpoints": [],
    "negative": [],
    "db_integrity": [],
    "perf_ms": {},
    "ai": {},
    "errors": [],
}


def record(section: str, name: str, expected: int, resp: httpx.Response, extra: dict | None = None):
    row = {
        "name": name,
        "method": resp.request.method if resp.request else "?",
        "path": str(resp.request.url.path) if resp.request else "?",
        "expected_status": expected,
        "actual_status": resp.status_code,
        "pass": resp.status_code == expected,
        "placeholder": resp.headers.get("X-Placeholder"),
        **(extra or {}),
    }
    results[section].append(row)
    return row


def timed_get(client: httpx.Client, path: str, **kw) -> tuple[httpx.Response, float]:
    t0 = time.perf_counter()
    r = client.get(path, **kw)
    return r, (time.perf_counter() - t0) * 1000


def db_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def orphan_counts() -> dict:
    tables = [
        ("clauses", "contract_id", "contracts", "id"),
        ("extractions", "contract_id", "contracts", "id"),
        ("obligations", "contract_id", "contracts", "id"),
        ("deadlines", "contract_id", "contracts", "id"),
        ("events", "contract_id", "contracts", "id"),
        ("payment_milestones", "contract_id", "contracts", "id"),
    ]
    out = {}
    with db_conn() as conn:
        cur = conn.cursor()
        for child, fk, parent, pk in tables:
            cur.execute(
                f"SELECT COUNT(*) FROM {child} WHERE {fk} NOT IN (SELECT {pk} FROM {parent})"
            )
            out[child] = cur.fetchone()[0]
    return out


def counts_for_contract(cid: str) -> dict:
    with db_conn() as conn:
        cur = conn.cursor()
        counts = {}
        for t in ("clauses", "extractions", "obligations", "deadlines", "events", "payment_milestones"):
            cur.execute(f"SELECT COUNT(*) FROM {t} WHERE contract_id = %s", (cid,))
            counts[t] = cur.fetchone()[0]
        return counts


def make_employment_docx() -> bytes:
    doc = Document()
    doc.add_heading("Employment Contract", 0)
    doc.add_paragraph(
        "This Employment Agreement is between the Employer and the Employee for full-time employment, "
        "salary, benefits, and termination notice."
    )
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def upload_file(client: httpx.Client, filename: str, data: bytes) -> httpx.Response:
    return client.post(
        "/api/contracts",
        headers=HEADERS,
        files={"file": (filename, data, "application/octet-stream")},
    )


def main():
    run_ai = "--skip-ai" not in sys.argv
    client = httpx.Client(base_url=BASE, timeout=httpx.Timeout(300.0, connect=10.0))
    qa_id: str | None = None
    ready_id: str | None = None
    main_id: str | None = None
    sub_id: str | None = None
    arabic_upload_id: str | None = None

    try:
        # health + auth
        r = client.get("/healthz")
        record("endpoints", "GET /healthz", 200, r)
        r = client.get("/api/contracts")
        record("negative", "GET /api/contracts no auth", 401, r, {"expected_status": 401})

        # list contracts perf
        r, ms = timed_get(client, "/api/contracts", headers=HEADERS)
        record("endpoints", "GET /api/contracts", 200, r)
        results["perf_ms"]["GET /api/contracts"] = round(ms, 1)

        r = client.get("/api/dashboard", headers=HEADERS)
        record(
            "endpoints",
            "GET /api/dashboard",
            200,
            r,
            {"note": "placeholder backend; frontend uses client aggregation", "body_keys": list(r.json().keys()) if r.status_code == 200 else []},
        )

        r = client.get("/api/demo/today", headers=HEADERS)
        record("endpoints", "GET /api/demo/today", 200, r)
        demo_today = r.json().get("today", date.today().isoformat())
        r = client.post("/api/demo/today", headers={**HEADERS, "Content-Type": "application/json"}, json={"today": demo_today})
        record("endpoints", "POST /api/demo/today", 200, r)

        # negative UUID
        r = client.get("/api/contracts/not-a-uuid", headers=HEADERS)
        record("negative", "GET invalid UUID", 422, r, {"expected_status": 422})

        fake = str(uuid.uuid4())
        r = client.get(f"/api/contracts/{fake}", headers=HEADERS)
        record("negative", "GET unknown contract", 404, r, {"expected_status": 404})

        # upload negatives
        r = upload_file(client, "bad.txt", b"hello")
        record("negative", "POST unsupported .txt", 400, r, {"expected_status": 400})

        r = upload_file(client, "empty.pdf", b"")
        record("negative", "POST empty.pdf", 422, r, {"expected_status": 422})

        r = upload_file(client, "corrupt.pdf", b"%PDF-1.4\n" + os.urandom(200))
        record("negative", "POST corrupt.pdf", 422, r, {"expected_status": 422})

        big = b"x" * (21 * 1024 * 1024)
        r = upload_file(client, "big.pdf", big)
        record("negative", "POST oversized", 413, r, {"expected_status": 413})

        r = upload_file(client, "عقد_اختبار.docx", SUB_DOC.read_bytes())
        if r.status_code == 201:
            arabic_upload_id = r.json()["id"]
            record("endpoints", "POST /api/contracts Arabic filename", 201, r, {"contract_id": arabic_upload_id})
        else:
            record("endpoints", "POST /api/contracts Arabic filename", 201, r)

        # disposable upload for matrix (no AI unless run_ai)
        if SUB_DOC.exists():
            tag = f"QA-{uuid.uuid4().hex[:8]}"
            data = SUB_DOC.read_bytes()
            r = client.post(
                "/api/contracts",
                headers=HEADERS,
                files={"file": (f"{tag}_sub.docx", data)},
            )
            if r.status_code == 201:
                qa_id = r.json()["id"]
                record("endpoints", "POST /api/contracts disposable", 201, r, {"contract_id": qa_id})

        if qa_id:
            r = client.get(f"/api/contracts/{qa_id}", headers=HEADERS)
            record("endpoints", "GET /api/contracts/{id}", 200, r)
            t0 = time.perf_counter()
            r = client.get(f"/api/contracts/{qa_id}", headers=HEADERS)
            results["perf_ms"]["GET /api/contracts/{id}"] = round((time.perf_counter() - t0) * 1000, 1)

            # Arabic title round-trip via SQL (no contract PATCH API)
            with db_conn() as conn:
                cur = conn.cursor()
                ar_title = "عقد اختبار QA"
                cur.execute("UPDATE contracts SET title = %s WHERE id = %s", (ar_title, qa_id))
                conn.commit()
            r = client.get(f"/api/contracts/{qa_id}", headers=HEADERS)
            ok = r.status_code == 200 and r.json().get("title") == ar_title
            results["db_integrity"].append({"name": "Arabic title round-trip", "pass": ok, "title": r.json().get("title") if r.status_code == 200 else None})

            r = client.get(f"/api/contracts/{qa_id}/obligations", headers=HEADERS)
            record("endpoints", "GET obligations pre-extract", 200, r)

            r = client.get(f"/api/contracts/{qa_id}/deadlines", headers=HEADERS)
            record("negative", "GET deadlines not ready", 409, r, {"expected_status": 409})

            if run_ai:
                t0 = time.perf_counter()
                r = client.post(f"/api/contracts/{qa_id}/extract", headers=HEADERS)
                extract_ms = (time.perf_counter() - t0) * 1000
                record("endpoints", "POST /extract supported subcontract", 200, r, {"duration_ms": round(extract_ms, 0)})
                results["ai"]["supported_extract"] = {
                    "status": r.status_code,
                    "duration_ms": round(extract_ms, 0),
                    "body": r.json() if r.status_code == 200 else r.text[:500],
                }
                if r.status_code == 200:
                    body = r.json()
                    results["ai"]["supported_checks"] = {
                        "supported": body.get("supported"),
                        "category": body.get("contract_category"),
                        "status": body.get("status"),
                    }
                    ready_id = qa_id
            else:
                results["ai"]["supported_extract"] = {"skipped": True}

            # find a ready contract from list for deadline/milestone tests if extract skipped/failed
            if not ready_id:
                lst = client.get("/api/contracts", headers=HEADERS).json()
                for c in lst:
                    if c.get("status") in ("ready", "needs_review"):
                        ready_id = c["id"]
                        break

            if ready_id:
                r, ms = timed_get(client, f"/api/contracts/{ready_id}/deadlines", headers=HEADERS)
                record("endpoints", "GET /deadlines", 200, r)
                results["perf_ms"]["GET /deadlines"] = round(ms, 1)

                c1 = counts_for_contract(ready_id).get("deadlines", 0)
                r = client.post(f"/api/contracts/{ready_id}/deadlines/rebuild", headers=HEADERS)
                record("endpoints", "POST deadlines/rebuild", 200, r)
                c2 = counts_for_contract(ready_id).get("deadlines", 0)
                r = client.post(f"/api/contracts/{ready_id}/deadlines/rebuild", headers=HEADERS)
                c3 = counts_for_contract(ready_id).get("deadlines", 0)
                results["db_integrity"].append(
                    {"name": "deadline rebuild idempotent count", "pass": c2 == c3, "counts": [c1, c2, c3]}
                )

                r, ms = timed_get(client, f"/api/contracts/{ready_id}/milestones", headers=HEADERS)
                record("endpoints", "GET /milestones", 200, r)
                results["perf_ms"]["GET /milestones"] = round(ms, 1)

                m1 = counts_for_contract(ready_id).get("payment_milestones", 0)
                r = client.post(f"/api/contracts/{ready_id}/milestones/rebuild", headers=HEADERS)
                m2 = counts_for_contract(ready_id).get("payment_milestones", 0)
                r = client.post(f"/api/contracts/{ready_id}/milestones/rebuild", headers=HEADERS)
                m3 = counts_for_contract(ready_id).get("payment_milestones", 0)
                results["db_integrity"].append(
                    {"name": "milestone rebuild idempotent count", "pass": m2 == m3, "counts": [m1, m2, m3]}
                )

                ms_resp = client.get(f"/api/contracts/{ready_id}/milestones", headers=HEADERS).json()
                milestones = ms_resp.get("milestones") or []
                if milestones:
                    mid = milestones[0]["id"]
                    pre = milestones[0].get("preconditions") or []
                    if pre:
                        pid = pre[0]["id"]
                        r = client.patch(
                            f"/api/milestones/{mid}",
                            headers={**HEADERS, "Content-Type": "application/json"},
                            json={"precondition_id": pid, "completed": True},
                        )
                        record("endpoints", "PATCH /milestones precondition", 200, r)
                    r = client.patch(
                        f"/api/milestones/{mid}",
                        headers={**HEADERS, "Content-Type": "application/json"},
                        json={"paid": True},
                    )
                    record("endpoints", "PATCH /milestones paid", 200, r)
                    r = client.patch(
                        f"/api/milestones/{mid}",
                        headers={**HEADERS, "Content-Type": "application/json"},
                        json={"paid": False},
                    )

                obs = client.get(f"/api/contracts/{ready_id}/obligations", headers=HEADERS).json()
                if obs:
                    oid = obs[0]["id"]
                    r = client.patch(
                        f"/api/obligations/{oid}",
                        headers={**HEADERS, "Content-Type": "application/json"},
                        json={"status": "done"},
                    )
                    record("endpoints", "PATCH /obligations/{id}", 200, r)
                    client.patch(
                        f"/api/obligations/{oid}",
                        headers={**HEADERS, "Content-Type": "application/json"},
                        json={"status": "pending"},
                    )

                r = client.post(
                    f"/api/contracts/{ready_id}/events",
                    headers={**HEADERS, "Content-Type": "application/json"},
                    json={"type": "delay", "event_date": demo_today, "description": "QA event"},
                )
                record("endpoints", "POST /events", 201, r)

                r = client.get(f"/api/contracts/{ready_id}/raw?page=1", headers=HEADERS)
                record("endpoints", "GET /raw page=1", 200, r)

            # blocked employment
            if run_ai:
                emp = make_employment_docx()
                r = upload_file(client, f"QA-employment-{uuid.uuid4().hex[:6]}.docx", emp)
                record("endpoints", "POST employment docx", 201, r)
                if r.status_code == 201:
                    eid = r.json()["id"]
                    r = client.post(f"/api/contracts/{eid}/extract", headers=HEADERS)
                    record("endpoints", "POST /extract employment", 200, r)
                    body = r.json() if r.status_code == 200 else {}
                    results["ai"]["employment"] = {
                        "supported": body.get("supported"),
                        "category": body.get("contract_category"),
                    }
                    obl_count = counts_for_contract(eid).get("obligations", 0)
                    results["ai"]["employment_obligations_after_block"] = obl_count
                    client.delete(f"/api/contracts/{eid}", headers=HEADERS)

        # flowdown
        r = client.get("/api/flowdown/contracts", headers=HEADERS)
        record("endpoints", "GET /flowdown/contracts", 200, r)
        fd = r.json() if r.status_code == 200 else {}
        mains = fd.get("main") or []
        subs = fd.get("sub") or []
        if mains and subs:
            main_id, sub_id = mains[0]["id"], subs[0]["id"]
            t0 = time.perf_counter()
            r = client.get(f"/api/flowdown?main_id={main_id}&sub_id={sub_id}", headers=HEADERS)
            results["perf_ms"]["GET /flowdown cached"] = round((time.perf_counter() - t0) * 1000, 1)
            record("endpoints", "GET /flowdown cached", 200, r)
            n1 = len(r.json().get("findings") or []) if r.status_code == 200 else 0

            if run_ai:
                t0 = time.perf_counter()
                r = client.post(
                    "/api/flowdown",
                    headers={**HEADERS, "Content-Type": "application/json"},
                    json={"main_contract_id": main_id, "subcontract_id": sub_id},
                )
                fd_ms = (time.perf_counter() - t0) * 1000
                record("endpoints", "POST /flowdown", 200, r, {"duration_ms": round(fd_ms, 0)})
                results["ai"]["flowdown"] = {"status": r.status_code, "duration_ms": round(fd_ms, 0)}
                if r.status_code == 200:
                    findings = r.json().get("findings") or []
                    results["ai"]["flowdown_findings_count"] = len(findings)
                    r2 = client.post(
                        "/api/flowdown",
                        headers={**HEADERS, "Content-Type": "application/json"},
                        json={"main_contract_id": main_id, "subcontract_id": sub_id},
                    )
                    n2 = len(r2.json().get("findings") or []) if r2.status_code == 200 else -1
                    results["db_integrity"].append(
                        {"name": "flowdown rerun stable count", "pass": n2 == len(findings), "counts": [len(findings), n2]}
                    )

            r = client.post(
                "/api/flowdown",
                headers={**HEADERS, "Content-Type": "application/json"},
                json={"main_contract_id": sub_id, "subcontract_id": main_id},
            )
            record("negative", "POST flowdown wrong pair", 422, r, {"expected_status": 422})

            r = client.post(
                "/api/flowdown",
                headers={**HEADERS, "Content-Type": "application/json"},
                json={"main_contract_id": main_id, "subcontract_id": main_id},
            )
            record("negative", "POST flowdown same id", 422, r, {"expected_status": 422})

        orphans = orphan_counts()
        for table, cnt in orphans.items():
            results["db_integrity"].append({"name": f"orphan {table}", "pass": cnt == 0, "count": cnt})

        # cascade delete disposable qa_id
        if qa_id:
            before = counts_for_contract(qa_id)
            r = client.delete(f"/api/contracts/{qa_id}", headers=HEADERS)
            record("endpoints", "DELETE /api/contracts/{id}", 204, r)
            after = counts_for_contract(qa_id)
            cascade_ok = sum(after.values()) == 0 and r.status_code == 204
            results["db_integrity"].append(
                {"name": "delete cascade", "pass": cascade_ok, "before": before, "after": after}
            )
            r = client.get(f"/api/contracts/{qa_id}", headers=HEADERS)
            record("negative", "GET deleted contract", 404, r, {"expected_status": 404})

        r = client.patch(
            f"/api/milestones/{uuid.uuid4()}",
            headers={**HEADERS, "Content-Type": "application/json"},
            json={"paid": True},
        )
        record("negative", "PATCH unknown milestone", 404, r, {"expected_status": 404})

        if arabic_upload_id and arabic_upload_id != qa_id:
            client.delete(f"/api/contracts/{arabic_upload_id}", headers=HEADERS)

    except httpx.ConnectError as e:
        results["errors"].append(f"Cannot connect to {BASE}: {e}")
    except Exception as e:
        results["errors"].append(f"{type(e).__name__}: {e}")
    finally:
        client.close()

    ep_pass = sum(1 for x in results["endpoints"] if x.get("pass"))
    ep_fail = sum(1 for x in results["endpoints"] if not x.get("pass"))
    neg_pass = sum(1 for x in results["negative"] if x.get("pass"))
    db_pass = sum(1 for x in results["db_integrity"] if x.get("pass"))
    results["summary"] = {
        "endpoints_pass": ep_pass,
        "endpoints_fail": ep_fail,
        "negative_pass": neg_pass,
        "negative_total": len(results["negative"]),
        "db_integrity_pass": db_pass,
        "db_integrity_total": len(results["db_integrity"]),
    }
    OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(results["summary"], indent=2))
    if results["errors"]:
        print("ERRORS:", results["errors"])
    return 0 if not results["errors"] and ep_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
