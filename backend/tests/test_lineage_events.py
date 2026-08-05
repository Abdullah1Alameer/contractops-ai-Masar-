"""Lineage event types for negotiation monitor."""
from app.services.version_lineage import MONITOR_LINEAGE_EVENTS, event_category


def test_monitor_events_categorized_negotiation():
    assert "email_received" in MONITOR_LINEAGE_EVENTS
    assert event_category("lawyer_package_generated") == "negotiation"
    assert len(MONITOR_LINEAGE_EVENTS) >= 15
