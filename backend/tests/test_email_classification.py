"""Email classification tests."""
from app.services.negotiation_monitor.classification import classify_email


def test_approval_vs_changes():
    approval = classify_email(subject="Approved", body_text="We approve and proceed as written.")
    assert approval["classification"] == "approval"
    changes = classify_email(subject="Changes", body_text="We revised clause 8 and request 90 day payment.")
    assert changes["classification"] == "revised_contract" or changes["classification"] == "request_changes"


def test_attachment_implies_revision():
    out = classify_email(subject="Draft", body_text="Please see attached.", has_attachment=True)
    assert out["classification"] == "revised_contract"
