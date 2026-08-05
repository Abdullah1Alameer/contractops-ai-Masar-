"""Negotiation round numbering."""
import uuid
from unittest.mock import MagicMock

from app.services.negotiation_monitor.rounds import next_round_number


def test_next_round_increments():
    db = MagicMock()
    db.query.return_value.filter_by.return_value.scalar.return_value = 2
    assert next_round_number(uuid.uuid4(), db) == 3
