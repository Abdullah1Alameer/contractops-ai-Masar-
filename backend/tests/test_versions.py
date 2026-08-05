"""Contract version control tests."""
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services import versions as ver_svc


def test_diff_json_added_removed():
    diff = ver_svc._diff_json({"a": 1}, {"b": 2})
    assert "a" in diff["removed_fields"]
    assert "b" in diff["added_fields"]


def test_is_stale_when_version_differs():
    db = MagicMock()
    cur = SimpleNamespace(id=uuid.uuid4())
    with patch.object(ver_svc, "current_version", return_value=cur):
        assert ver_svc.is_stale_version(uuid.uuid4(), uuid.uuid4(), db) is True
        assert ver_svc.is_stale_version(cur.id, uuid.uuid4(), db) is False


def test_is_stale_workflow():
    db = MagicMock()
    wid = uuid.uuid4()
    w = SimpleNamespace(version_id=wid)
    with patch.object(ver_svc, "is_stale_version", return_value=True):
        assert ver_svc.is_stale_workflow(w, uuid.uuid4(), db) is True


@patch("app.services.versions.storage")
def test_create_initial_version(mock_storage):
    mock_storage.get.side_effect = Exception("skip")
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = None
    cid = uuid.uuid4()
    contract = SimpleNamespace(id=cid, file_url="key", title="T")
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()
    with patch.object(ver_svc, "log_version_activity"):
        v = ver_svc.create_initial_version(contract, db)
    assert v.version_number == 1
    assert v.is_current is True


def test_next_version_number():
    db = MagicMock()
    db.query.return_value.filter_by.return_value.scalar.return_value = 2
    assert ver_svc._next_version_number(uuid.uuid4(), db) == 3


@patch("app.services.versions.log_version_activity")
@patch("app.ai.pipeline.run_extraction")
@patch("app.services.versions.sync_version_snapshot")
@patch("app.services.versions.storage")
def test_only_one_current(mock_storage, mock_sync, mock_extract, mock_log):
    mock_storage.save.return_value = "newkey"
    cid = uuid.uuid4()
    parent = SimpleNamespace(id=uuid.uuid4(), version_number=1)
    contract = SimpleNamespace(id=cid, file_url="old", status="ready")
    db = MagicMock()
    db.get.return_value = contract
    db.query.return_value.filter_by.return_value.update = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock(side_effect=lambda x: x)
    with patch.object(ver_svc, "current_version", return_value=parent):
        with patch.object(ver_svc, "_next_version_number", return_value=2):
            ver_svc.create_new_version(
                    cid,
                    db,
                    source="manual_upload",
                    actor="demo",
                    file_bytes=b"%PDF",
                    filename="c.pdf",
                    change_summary="Update",
                )
    db.query.return_value.filter_by.return_value.update.assert_called()


def test_compare_cached():
    db = MagicMock()
    fv = SimpleNamespace(id=uuid.uuid4(), contract_id=uuid.uuid4(), version_number=1, extracted_json={})
    tv = SimpleNamespace(id=uuid.uuid4(), contract_id=fv.contract_id, version_number=2, extracted_json={"x": 1})
    db.get.side_effect = lambda model, pk: fv if pk == fv.id else tv
    cached = SimpleNamespace(diff_json={"added_fields": ["x"], "schema_version": 2}, ai_explanation="cached")
    db.query.return_value.filter_by.return_value.first.return_value = cached
    out = ver_svc.compare_versions(fv.contract_id, fv.id, tv.id, db)
    assert out["cached"] is True


def test_compare_cache_miss_on_old_schema():
    db = MagicMock()
    fv = SimpleNamespace(id=uuid.uuid4(), contract_id=uuid.uuid4(), version_number=1, extracted_json={})
    tv = SimpleNamespace(id=uuid.uuid4(), contract_id=fv.contract_id, version_number=2, extracted_json={"x": 1})
    db.get.side_effect = lambda model, pk: fv if pk == fv.id else tv
    cached = SimpleNamespace(diff_json={"added_fields": ["x"], "schema_version": 1}, ai_explanation="old")
    db.query.return_value.filter_by.return_value.first.return_value = cached
    db.add = MagicMock()
    db.commit = MagicMock()
    with patch.object(ver_svc, "log_version_activity"):
        with patch("app.services.versions.complete_json", side_effect=Exception("offline")):
            out = ver_svc.compare_versions(fv.contract_id, fv.id, tv.id, db)
    assert out["diff"].get("schema_version") == 2
    assert "rich" in out["diff"]


@patch("app.services.versions.log_version_activity")
def test_set_current_emits_restore_events(mock_log):
    db = MagicMock()
    cid = uuid.uuid4()
    prior_id = uuid.uuid4()
    new_id = uuid.uuid4()
    prior = SimpleNamespace(id=prior_id, contract_id=cid, version_number=1, file_path="a.pdf")
    target = SimpleNamespace(id=new_id, contract_id=cid, version_number=2, file_path="b.pdf", is_current=False)
    contract = SimpleNamespace(id=cid, file_url="a.pdf")

    def get_side(model, pk):
        if pk == new_id:
            return target
        if pk == cid:
            return contract
        return None

    db.get.side_effect = get_side
    db.query.return_value.filter_by.return_value.update = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()

    with patch.object(ver_svc, "current_version", return_value=prior):
        ver_svc.set_current(new_id, db, actor="legal")

    types = [c.args[2] for c in mock_log.call_args_list]
    assert "version_set_current" in types
    assert "version_restored" in types
    assert "current_version_changed" in types


def test_serialize_version_includes_workflow_status():
    vid = uuid.uuid4()
    v = SimpleNamespace(
        id=vid,
        contract_id=uuid.uuid4(),
        version_number=1,
        version_label="v1",
        parent_version_id=None,
        source="initial_upload",
        status="ready",
        change_summary=None,
        file_path="k",
        ai_summary=None,
        created_by="demo",
        hash_sha256=None,
        is_current=True,
        created_at=None,
        extracted_json={},
    )
    with patch.object(
        ver_svc,
        "_workflow_status_for_version",
        return_value={
            "review_status": "sent",
            "approval_status": "in_progress",
            "signature_status": None,
            "restored_by": None,
            "restored_at": None,
        },
    ):
        with patch("app.services.version_lineage.enrich_version_fields", return_value={"workflow_stale_count": 0}):
            out = ver_svc.serialize_version(v, MagicMock())
    assert out["review_status"] == "sent"
    assert out["approval_status"] == "in_progress"


def test_compare_builds_diff():
    db = MagicMock()
    fv = SimpleNamespace(id=uuid.uuid4(), contract_id=uuid.uuid4(), version_number=1, extracted_json={"a": 1})
    tv = SimpleNamespace(id=uuid.uuid4(), contract_id=fv.contract_id, version_number=2, extracted_json={"b": 2})
    db.get.side_effect = lambda model, pk: fv if pk == fv.id else tv
    db.query.return_value.filter_by.return_value.first.return_value = None
    db.add = MagicMock()
    db.commit = MagicMock()
    with patch.object(ver_svc, "log_version_activity"):
        with patch("app.services.versions.complete_json", side_effect=Exception("offline")):
            out = ver_svc.compare_versions(fv.contract_id, fv.id, tv.id, db)
    assert out["diff"].get("schema_version") == 2
    assert "rich" in out["diff"]
