"""Revision detection tests."""
import uuid
from unittest.mock import MagicMock, patch

from app.services.negotiation_monitor.revision_detection import RevisionKind, detect_revision


def test_same_hash_is_same():
    db = MagicMock()
    cid = uuid.uuid4()
    contract = MagicMock(id=cid, title="Vendor MSA")
    cur = MagicMock(hash_sha256="abc", version_number=1)
    db.query.return_value.filter_by.return_value.order_by.return_value.first.return_value = cur
    db.query.return_value.filter_by.return_value.first.return_value = None
    kind, h, _ = detect_revision(db, contract=contract, file_bytes=b"data", filename="a.txt")
    assert h != "abc" or kind != RevisionKind.same


def test_revised_txt():
    db = MagicMock()
    contract = MagicMock(id=uuid.uuid4(), title="Vendor MSA — Al-Falak")
    cur = MagicMock(hash_sha256="other", version_number=1)
    db.query.return_value.filter_by.return_value.order_by.return_value.first.return_value = cur
    db.query.return_value.filter_by.return_value.first.return_value = None
    text = b"MASTER SERVICE AGREEMENT\nParties: Your Company / Al-Falak\nPayment ninety days"
    kind, _, snippet = detect_revision(db, contract=contract, file_bytes=text, filename="rev.txt")
    assert kind == RevisionKind.revised
    assert snippet
