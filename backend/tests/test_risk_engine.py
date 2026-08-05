"""Risk engine tests."""
from app.services.risk_engine import CALCULATION_VERSION, _level


def test_level_bands():
    assert _level(0) == "low"
    assert _level(16) == "low"
    assert _level(25) == "medium"


def test_calculation_version_constant():
    assert CALCULATION_VERSION == "risk-v2"
