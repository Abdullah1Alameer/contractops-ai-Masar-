"""Review package fallback shape."""
from unittest.mock import MagicMock

from app.services.negotiation_monitor.review_package import _fallback_package


def test_bilingual_fields_present():
    pkg = _fallback_package(
        comparison={"template_deviations": [], "overall_risk_score": 50, "recommended_action": "negotiate"},
        playbook_deviations=[],
        email=MagicMock(subject="MSA", body_text="revise"),
    )
    assert pkg["draft_email_body_en"]
    assert pkg["draft_email_body_ar"]
    assert "executive_summary" in pkg
