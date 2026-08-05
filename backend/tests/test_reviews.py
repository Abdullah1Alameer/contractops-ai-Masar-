"""Client Review Portal service tests (no OpenAI, no live SMTP)."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

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


def test_expire_if_needed_marks_expired():
    db = MagicMock()
    req = SimpleNamespace(
        status="sent",
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    out = rev.expire_if_needed(req, db)
    assert out.status == "expired"
    db.commit.assert_called()


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


def test_record_decision_approve():
    db = MagicMock()
    import uuid

    req = SimpleNamespace(
        id="rid",
        contract_id=uuid.uuid4(),
        status="opened",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        responded_at=None,
    )
    db.query.return_value.filter_by.return_value.first.return_value = None
    from unittest.mock import patch

    with patch("app.services.versions.current_version", return_value=None):
        rev.record_decision(req, db, "approve")
    assert req.status == "approved"
    assert req.responded_at is not None
    db.add.assert_called()
    db.commit.assert_called()


def test_record_decision_rejects_when_closed():
    db = MagicMock()
    req = SimpleNamespace(
        id="rid",
        status="approved",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    with pytest.raises(ValueError, match="review_closed"):
        rev.record_decision(req, db, "approve")


def test_add_comment_blocked_after_decision():
    db = MagicMock()
    req = SimpleNamespace(
        id="rid",
        status="rejected",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    with pytest.raises(ValueError, match="review_closed"):
        rev.add_comment(req, db, "note")


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
