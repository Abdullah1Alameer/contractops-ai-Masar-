"""Reset the DB and push both demo contracts through the REAL API.

Prereq: backend running on http://localhost:8000 (uvicorn app.main:app).

    python database/seed/make_contracts.py   # once, to generate the .docx files
    python database/seed/seed.py
"""
import os
import sys
from pathlib import Path

import httpx
import psycopg2
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

API = os.getenv("API_URL", "http://localhost:8000")
TOKEN = os.getenv("DEMO_TOKEN", "demo-secret-token")
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
DOCS = ROOT / "database" / "demo_contracts"

TABLES = [
    "flowdown_findings", "payment_milestones", "deadlines", "events",
    "obligations", "extractions", "clauses", "contracts",
]


def reset_db():
    url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/contractops")
    conn = psycopg2.connect(url.replace("postgresql+psycopg2://", "postgresql://"))
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(f"TRUNCATE {', '.join(TABLES)} CASCADE")
    conn.close()
    print("DB reset.")


def upload(client: httpx.Client, filename: str, ctype: str, parent_id: str | None = None) -> str:
    data = {"type": ctype}
    if parent_id:
        data["parent_main_contract_id"] = parent_id
    with open(DOCS / filename, "rb") as f:
        r = client.post(
            f"{API}/api/contracts",
            headers=HEADERS,
            data=data,
            files={"file": (filename, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
    r.raise_for_status()
    cid = r.json()["id"]
    print(f"uploaded {filename} -> {cid}")
    r = client.post(f"{API}/api/contracts/{cid}/extract", headers=HEADERS, timeout=300)
    r.raise_for_status()
    body = r.json()
    print(f"  extracted: status={body['status']} counts={body['counts']}")
    return cid


def main():
    if not (DOCS / "main_contract.docx").exists():
        print("demo contracts missing — run: python database/seed/make_contracts.py")
        sys.exit(1)
    reset_db()
    with httpx.Client(timeout=300) as client:
        main_id = upload(client, "main_contract.docx", "main")
        upload(client, "sub_contract.docx", "subcontract", parent_id=main_id)
    print("seed complete.")


if __name__ == "__main__":
    main()
