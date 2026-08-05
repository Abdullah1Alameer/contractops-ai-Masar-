"""Regression tests for multi-industry classifier gate (no OpenAI)."""
import pytest

from app.ai.classifier import (
    CONFIDENCE_THRESHOLD,
    GENERAL_SUPPORTED_CATEGORIES,
    LEGACY_SUPPORTED_CATEGORIES,
    PERSONAL_UNSUPPORTED,
    SUPPORTED_SET,
    category_to_type,
    is_comparison_eligible,
    is_supported_category,
    relationship_type_for_category,
)


@pytest.mark.parametrize(
    "category",
    [
        "NDA",
        "Employment Agreement",
        "Software/SaaS Agreement",
        "Lease Agreement",
        "Service Agreement",
        "Construction Contract",
        "Subcontract",
    ],
)
def test_general_categories_supported(category):
    assert category in SUPPORTED_SET
    assert is_supported_category(category, CONFIDENCE_THRESHOLD)


def test_legacy_main_construction_still_supported():
    assert "Main Construction Contract" in SUPPORTED_SET
    assert is_supported_category("Main Construction Contract", 0.95)


@pytest.mark.parametrize(
    "category",
    [
        "Marriage Contract",
        "Medical Record",
        "Personal Loan Agreement",
        "Unsupported Personal Document",
    ],
)
def test_personal_categories_not_supported(category):
    assert category not in GENERAL_SUPPORTED_CATEGORIES
    assert not is_supported_category(category, 0.99)


def test_unknown_low_confidence_blocked():
    assert not is_supported_category("NDA", CONFIDENCE_THRESHOLD - 0.01)


def test_category_to_type_mappings():
    assert category_to_type("Main Construction Contract") == "main"
    assert category_to_type("Master Service Agreement") == "main"
    assert category_to_type("Subcontract Agreement") == "subcontract"
    assert category_to_type("Statement of Work") == "subcontract"
    assert category_to_type("NDA") is None


def test_relationship_type_for_category():
    assert relationship_type_for_category("Construction Contract") == "parent"
    assert relationship_type_for_category("Subcontract") == "child"
    assert relationship_type_for_category("NDA") == "standalone"


def test_comparison_eligible_ready_commercial():
    from types import SimpleNamespace

    nda = SimpleNamespace(
        status="ready",
        contract_category="NDA",
        supported=True,
    )
    svc = SimpleNamespace(
        status="ready",
        contract_category="Service Agreement",
        supported=True,
    )
    assert is_comparison_eligible(nda)
    assert is_comparison_eligible(svc)


def test_comparison_ineligible_personal():
    from types import SimpleNamespace

    doc = SimpleNamespace(
        status="ready",
        contract_category="Marriage Contract",
        supported=False,
    )
    assert not is_comparison_eligible(doc)


def test_personal_set_matches_unsupported_gate():
    for cat in PERSONAL_UNSUPPORTED:
        assert cat not in SUPPORTED_SET
