"""Outbound send gating tests."""
import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.services.negotiation_monitor import outbound as outbound_svc


def test_send_requires_explicit_human_package_approval():
    package = MagicMock(status="ready")
    with pytest.raises(ValueError, match="package_not_approved"):
        outbound_svc.send_approved_response(MagicMock(), package, actor="legal")


def test_send_blocked_without_approval():
    pkg = MagicMock()
    pkg.status = "approved"
    pkg.package_json = {
        "changes": [{"required_approver": "finance"}],
    }
    pkg.lawyer_edited_json = None
    pkg.thread_id = uuid.uuid4()
    pkg.email_id = uuid.uuid4()
    pkg.draft_email_subject_en = "Re:"
    pkg.draft_email_body_en = "Body"
    thread = MagicMock()
    thread.id = pkg.thread_id
    thread.contract_id = uuid.uuid4()
    thread.counterparty_email = "c@example.com"
    thread.external_thread_id = "x"
    thread.current_version_id = None
    db = MagicMock()
    db.get.side_effect = lambda model, pk: thread if pk == pkg.thread_id else None
    with patch.object(outbound_svc.appr_svc, "get_active_workflow", return_value=None):
        with pytest.raises(ValueError, match="required_approval"):
            outbound_svc.send_approved_response(db, pkg, actor="legal")


@patch("app.services.negotiation_monitor.outbound.get_email_connector")
def test_send_with_override(mock_connector):
    mock_connector.return_value.send_message.return_value = MagicMock(
        external_message_id="out-1",
        sent_at="2026-08-01T12:00:00+00:00",
        provider="simulated",
    )
    pkg = MagicMock()
    pkg.status = "approved"
    pkg.package_json = {"changes": []}
    pkg.lawyer_edited_json = None
    pkg.thread_id = uuid.uuid4()
    pkg.email_id = uuid.uuid4()
    pkg.draft_email_subject_en = "Re:"
    pkg.draft_email_body_en = "Body"
    pkg.id = uuid.uuid4()
    thread = MagicMock()
    thread.id = pkg.thread_id
    thread.contract_id = uuid.uuid4()
    thread.counterparty_email = "c@example.com"
    thread.external_thread_id = "x"
    thread.current_version_id = None
    db = MagicMock()
    db.get.side_effect = lambda model, pk: thread if pk == pkg.thread_id else None
    db.query.return_value.filter_by.return_value.order_by.return_value.first.return_value = None
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()
    with patch.object(outbound_svc.appr_svc, "get_active_workflow", return_value=None):
        with patch.object(outbound_svc, "close_round"):
            with patch.object(outbound_svc, "log_monitor_event"):
                outbound_svc.send_approved_response(db, pkg, actor="legal", override_reason="demo")
    assert db.add.called
