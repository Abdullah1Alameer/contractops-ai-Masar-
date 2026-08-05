"""Public API must not expose internal negotiation strategy."""
import json


def test_public_review_dossier_shape_has_no_playbook_fields():
    sample = {
        "contract_title": "MSA",
        "message": "Please review",
        "clauses": [],
    }
    blob = json.dumps(sample)
    forbidden = ("playbook", "template_deviation", "overall_risk_score", "package_json", "negotiation_memory")
    for term in forbidden:
        assert term not in blob
