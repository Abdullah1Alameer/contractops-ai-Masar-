"""Negotiation memory tests."""
from app.services.negotiation_monitor.memory import get_counterparty_memory


def test_insufficient_history():
    db = __import__("unittest").mock.MagicMock()
    db.query.return_value.filter.return_value.filter.return_value.all.return_value = []
    out = get_counterparty_memory(db, counterparty_email="new@vendor.com")
    assert out["insufficient_history"] is True
    assert out["evidence_count"] < 2
