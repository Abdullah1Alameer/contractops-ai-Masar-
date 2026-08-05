"""Typed contract dates and inconsistency findings."""
from __future__ import annotations

import re
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from ..models import Contract
from .dates import parse_date_raw

_EXEC = re.compile(
    r"Contract execution date:\s*(\d{1,4}\s*[/\-.]\s*\d{1,2}\s*[/\-.]\s*\d{1,4})",
    re.I,
)
_COMM = re.compile(
    r"Commencement date:\s*(\d{1,4}\s*[/\-.]\s*\d{1,2}\s*[/\-.]\s*\d{1,4})",
    re.I,
)
_START = re.compile(
    r"Starting date:\s*(\d{1,4}\s*[/\-.]\s*\d{1,2}\s*[/\-.]\s*\d{1,4})",
    re.I,
)
_END = re.compile(
    r"Contract end date:\s*(\d{1,4}\s*[/\-.]\s*\d{1,2}\s*[/\-.]\s*\d{1,4})",
    re.I,
)


def _parse_header_date(raw: str | None) -> date | None:
    if not raw:
        return None
    return parse_date_raw(raw.strip(), "gregorian")


def parse_header_dates(raw_text: str | None) -> dict[str, date | None]:
    text = raw_text or ""
    out: dict[str, date | None] = {
        "execution_date": None,
        "commencement_date": None,
        "starting_date": None,
        "contract_end_date": None,
    }
    for key, pat in (
        ("execution_date", _EXEC),
        ("commencement_date", _COMM),
        ("starting_date", _START),
        ("contract_end_date", _END),
    ):
        m = pat.search(text)
        if m:
            out[key] = _parse_header_date(m.group(1))
    return out


def build_date_inconsistencies(
    header: dict[str, date | None],
    contract: Contract,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    exec_d = header.get("execution_date")
    comm_d = header.get("commencement_date")
    start_d = header.get("starting_date") or contract.start_date
    end_d = header.get("contract_end_date") or contract.end_date

    if exec_d and comm_d and comm_d < exec_d:
        findings.append(
            {
                "type": "date_inconsistency",
                "code": "commencement_before_execution",
                "dates": [
                    {"type": "commencement_date", "value": comm_d.isoformat()},
                    {"type": "execution_date", "value": exec_d.isoformat()},
                ],
                "explanation": (
                    "Commencement date precedes contract execution date; "
                    "confirm which date governs probation and term calculations."
                ),
                "severity": "warning",
                "needs_review": True,
            }
        )

    if comm_d and end_d and start_d and start_d != comm_d:
        findings.append(
            {
                "type": "date_inconsistency",
                "code": "starting_differs_from_commencement",
                "dates": [
                    {"type": "commencement_date", "value": comm_d.isoformat()},
                    {"type": "starting_date", "value": start_d.isoformat()},
                    {"type": "contract_end_date", "value": end_d.isoformat()},
                ],
                "explanation": (
                    "Starting date differs from commencement date while clause 5.1 "
                    "may reference commencement for the contract term; verify which "
                    "date bounds the active period."
                ),
                "severity": "info",
                "needs_review": True,
            }
        )

    return findings


def sync_contract_date_semantics(contract: Contract, db: Session) -> dict[str, Any]:
    header = parse_header_dates(contract.raw_text)
    if header.get("execution_date"):
        contract.execution_date = header["execution_date"]
    if header.get("commencement_date"):
        contract.commencement_date = header["commencement_date"]
    if header.get("starting_date") and contract.start_date is None:
        contract.start_date = header["starting_date"]
    if header.get("contract_end_date") and contract.end_date is None:
        contract.end_date = header["contract_end_date"]

    inconsistencies = build_date_inconsistencies(header, contract)
    facts = {
        "execution_date": (contract.execution_date or header.get("execution_date")),
        "commencement_date": (contract.commencement_date or header.get("commencement_date")),
        "starting_date": contract.start_date or header.get("starting_date"),
        "contract_end_date": contract.end_date or header.get("contract_end_date"),
        "inconsistencies": inconsistencies,
    }
    contract.date_facts = {
        k: (v.isoformat() if isinstance(v, date) else v)
        for k, v in facts.items()
        if k != "inconsistencies"
    }
    contract.date_facts["inconsistencies"] = inconsistencies
    db.flush()
    return facts


def resolve_base_date(contract: Contract, base_date_type: str | None) -> date | None:
    if not base_date_type or base_date_type == "unknown":
        return None
    mapping = {
        "contract_end_date": contract.end_date,
        "contract_start_date": contract.start_date,
        "starting_date": contract.start_date,
        "commencement_date": contract.commencement_date,
        "execution_date": contract.execution_date,
        "termination_date": None,
        "invoice_date": None,
        "approval_date": None,
        "completion_date": None,
        "event_date": None,
        "fixed_date": None,
    }
    return mapping.get(base_date_type)
