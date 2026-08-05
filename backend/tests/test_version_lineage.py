"""Feature 14 — version lineage aggregation tests."""
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services import version_lineage as lin_svc


def test_sanitize_metadata_strips_secrets():
    out = lin_svc.sanitize_metadata(
        {"version_number": 1, "token": "secret", "email": "a@b.com", "workflow_id": "w1"}
    )
    assert "token" not in out
    assert "email" not in out
    assert out.get("workflow_id") == "w1"


def test_version_risk_score_from_extracted():
    db = MagicMock()
    v = SimpleNamespace(
        id=uuid.uuid4(),
        contract_id=uuid.uuid4(),
        extracted_json={"risk_score": 42},
    )
    assert lin_svc.version_risk_score(v, db) == 42


def test_version_risk_score_null_when_no_signal():
    db = MagicMock()
    v = SimpleNamespace(id=uuid.uuid4(), contract_id=uuid.uuid4(), extracted_json={})
    db.query.return_value.filter_by.return_value.order_by.return_value.first.return_value = None
    db.query.return_value.filter_by.return_value.count.return_value = 0
    db.query.return_value.filter_by.return_value.all.return_value = []
    assert lin_svc.version_risk_score(v, db) is None


def test_transition_reason_signed():
    v = SimpleNamespace(source="signed")
    assert lin_svc.transition_reason(v) == "signed_document_generated"


def test_build_lineage_transition_reason_client_revision():
    v = SimpleNamespace(source="client_revision")
    assert lin_svc.transition_reason(v) == "client_requested_changes"


def test_lineage_route_requires_auth():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    cid = uuid.uuid4()
    r = client.get(f"/api/contracts/{cid}/versions/lineage")
    assert r.status_code == 401
