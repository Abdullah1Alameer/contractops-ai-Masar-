"""Unit tests for F4 flow-down engine (no database, no AI)."""
from types import SimpleNamespace

import pytest

from app.ai.flowdown_prompt import FLOWDOWN_CATEGORIES
from app.services.flowdown import (
    check_eligibility,
    summarize,
    sort_findings,
    validate_ai_findings,
)


def test_validate_drops_unknown_clause_ids():
    main_valid = {"aaa-bbbb-cccc-dddd-eeeeeeeeeeee"}
    sub_valid = set()
    raw = [
        {
            "category": "insurance",
            "status": "missing",
            "risk_level": "high",
            "explanation": "No sub insurance",
            "recommendation": "Add clause",
            "main_clause_id": "aaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "sub_clause_id": "fake-id-not-in-dossier",
            "main_citation": "12.4",
            "sub_citation": "Not Found",
            "confidence": 0.9,
        }
    ]
    out = validate_ai_findings(raw, main_valid, sub_valid)
    ins = next(x for x in out if x["category"] == "insurance")
    assert ins["main_clause_id"] == "aaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert ins["sub_clause_id"] is None


def test_validate_fills_all_categories():
    out = validate_ai_findings([], set(), set())
    assert len(out) == len(FLOWDOWN_CATEGORIES)


def test_summarize_coverage_and_risk():
    findings = [
        {"status": "fully_flowed_down", "risk_level": "informational"},
        {"status": "missing", "risk_level": "critical"},
        {"status": "conflict", "risk_level": "high"},
        {"status": "modified", "risk_level": "low"},
    ]
    s = summarize(findings)
    assert s["total"] == 4
    assert s["coverage_pct"] == 50
    assert s["missing_count"] == 1
    assert s["conflict_count"] == 1
    assert s["critical_count"] == 1
    assert s["overall_risk_score"] > 0


def test_dedupe_keeps_higher_confidence():
    main_valid = set()
    sub_valid = set()
    raw = [
        {
            "category": "retention",
            "status": "missing",
            "risk_level": "medium",
            "explanation": "a",
            "recommendation": "r",
            "main_clause_id": None,
            "sub_clause_id": None,
            "main_citation": None,
            "sub_citation": None,
            "confidence": 0.5,
        },
        {
            "category": "retention",
            "status": "modified",
            "risk_level": "low",
            "explanation": "b",
            "recommendation": "r2",
            "main_clause_id": None,
            "sub_clause_id": None,
            "main_citation": None,
            "sub_citation": None,
            "confidence": 0.95,
        },
    ]
    out = validate_ai_findings(raw, main_valid, sub_valid)
    ret = next(x for x in out if x["category"] == "retention")
    assert ret["confidence"] == 0.95
    assert ret["status"] == "modified"


def test_sort_critical_before_informational():
    items = [
        {"risk_level": "informational", "category": "z"},
        {"risk_level": "critical", "category": "a"},
    ]
    sorted_items = sort_findings(items)
    assert sorted_items[0]["risk_level"] == "critical"


def test_eligibility_wrong_pair():
    main = SimpleNamespace(
        status="ready",
        contract_category="Subcontract Agreement",
    )
    sub = SimpleNamespace(status="ready", contract_category="Subcontract Agreement")
    with pytest.raises(ValueError, match="flowdown_wrong_pair"):
        check_eligibility(main, sub)


def test_eligibility_not_found():
    with pytest.raises(ValueError, match="not_found"):
        check_eligibility(None, SimpleNamespace(status="ready", contract_category="Subcontract Agreement"))
