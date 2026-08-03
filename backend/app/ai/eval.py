"""Day-1 GO/NO-GO gate.

Runs the full pipeline over database/demo_contracts/* and grades the output
against database/seed/ground_truth.json.

    cd backend
    python -m app.ai.eval           # grade + clean up test rows
    python -m app.ai.eval --keep    # keep the contracts in the DB

GO criteria: 100% of planted notice periods found, >=90% of planted
obligations found, all quotes verified.
"""
import json
import sys
import uuid

from ..config import DEMO_CONTRACTS_DIR, GROUND_TRUTH_PATH
from ..db import SessionLocal
from ..models import Clause, Contract, Extraction, Obligation
from ..services.storage import storage
from .pipeline import run_extraction


def _get_extr(db, contract_id, field):
    row = db.query(Extraction).filter_by(contract_id=contract_id, field_name=field).first()
    return row.value_json if row else None


def grade_one(db, gt: dict) -> dict:
    path = DEMO_CONTRACTS_DIR / gt["file"]
    data = path.read_bytes()
    key = storage.save(data, gt["file"])
    contract = Contract(id=uuid.uuid4(), title=gt["title"], type=gt["type"], file_url=key, status="processing")
    db.add(contract)
    db.commit()

    result = run_extraction(contract.id, db)
    db.refresh(contract)

    def contains(actual, expected):
        return bool(actual) and expected in actual

    parties_ok = contains(contract.party_a, gt["party_a_contains"]) and contains(contract.party_b, gt["party_b_contains"])
    value_ok = contract.value_sar is not None and float(contract.value_sar) == gt["value_sar"]
    dates_ok = (
        (contract.start_date.isoformat() if contract.start_date else None) == gt["start_date"]
        and (contract.end_date.isoformat() if contract.end_date else None) == gt["end_date"]
    )

    notices = _get_extr(db, contract.id, "notice_periods") or []
    found_days = {n.get("days") for n in notices}
    notice_hits = sum(1 for n in gt["notice_periods"] if n["days"] in found_days)

    descriptions = " || ".join((o.description or "") for o in db.query(Obligation).filter_by(contract_id=contract.id))
    obligation_hits = sum(1 for kws in gt["obligations_keywords"] if any(kw in descriptions for kw in kws))

    rep = result["pipeline_report"]
    confs = [row.confidence for row in db.query(Extraction).filter_by(contract_id=contract.id) if row.confidence is not None]

    return {
        "title": gt["title"][:38],
        "contract_id": contract.id,
        "parties": parties_ok,
        "value": value_ok,
        "dates": dates_ok,
        "notice": f"{notice_hits}/{len(gt['notice_periods'])}",
        "notice_ok": notice_hits == len(gt["notice_periods"]),
        "oblig": f"{obligation_hits}/{len(gt['obligations_keywords'])}",
        "oblig_ok": obligation_hits >= 0.9 * len(gt["obligations_keywords"]),
        "quotes": f"{rep['verified_items']}/{rep['total_items']}",
        "quotes_ok": rep["verified_items"] == rep["total_items"],
        "mean_conf": round(sum(map(float, confs)) / len(confs), 2) if confs else 0.0,
    }


def main():
    keep = "--keep" in sys.argv
    ground_truth = json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))
    db = SessionLocal()
    rows = []
    try:
        for gt in ground_truth["contracts"]:
            print(f"running pipeline: {gt['file']} ...")
            rows.append(grade_one(db, gt))

        cols = ["title", "parties", "value", "dates", "notice", "oblig", "quotes", "mean_conf"]
        widths = {c: max(len(c), *(len(str(r[c])) for r in rows)) for c in cols}
        line = " | ".join(c.ljust(widths[c]) for c in cols)
        print("\n" + line)
        print("-" * len(line))
        for r in rows:
            print(" | ".join(str(r[c]).ljust(widths[c]) for c in cols))

        go = all(r["parties"] and r["value"] and r["dates"] and r["notice_ok"] and r["oblig_ok"] and r["quotes_ok"] for r in rows)
        print(f"\n{'GO ✅' if go else 'NO-GO ❌'}")
        if not keep:
            for r in rows:
                cid = r["contract_id"]
                db.query(Obligation).filter_by(contract_id=cid).delete()
                db.query(Extraction).filter_by(contract_id=cid).delete()
                db.query(Clause).filter_by(contract_id=cid).delete()
                db.query(Contract).filter_by(id=cid).delete()
            db.commit()
        sys.exit(0 if go else 1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
