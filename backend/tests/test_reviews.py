"""Client Review Portal service tests (no OpenAI, no live SMTP)."""
from datetime import datetime, timezone
from types import SimpleNamespace

from app.services import reviews as rev


def test_generate_token_unique():
    a = rev.generate_token()
    b = rev.generate_token()
    assert a != b
    assert len(a) >= 32


def test_can_respond_open_states():
    assert rev.can_respond(SimpleNamespace(status="sent"))
    assert rev.can_respond(SimpleNamespace(status="opened"))
    assert not rev.can_respond(SimpleNamespace(status="approved"))


def test_can_respond_rejects_all_terminal_statuses():
    for status in ("approved", "rejected", "changes_requested", "expired", "cancelled"):
        assert not rev.can_respond(SimpleNamespace(status=status))


def test_build_email_template_includes_link():
    req = SimpleNamespace(
        recipient_name="Client",
        message="Please review",
        expires_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    contract = SimpleNamespace(title="MSA 2026")
    link = "http://localhost:3000/review/abc"
    email = rev.build_email_template(req, contract, link)
    assert link in email["body"]
    assert "MSA 2026" in email["subject"]
    assert email["review_link"] == link


def test_review_error_preserves_http_contract():
    error = rev.ReviewError(409, "review_closed", read_only=True)

    assert str(error) == "review_closed"
    assert error.status_code == 409
    assert error.payload == {
        "error": "review_closed",
        "read_only": True,
    }


def test_build_ai_summary_includes_parties():
    contract = SimpleNamespace(
        title="Test",
        party_a="A",
        party_b="B",
        value_sar=1000,
        governing_law="KSA",
        start_date=None,
        end_date=None,
    )
    text = rev.build_ai_summary(contract, [], {}, {}, None)
    assert "A" in text and "B" in text
