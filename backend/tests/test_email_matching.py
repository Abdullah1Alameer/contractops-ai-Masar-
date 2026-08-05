"""Email-to-thread matching tests."""
import uuid
from unittest.mock import MagicMock

from app.models import NegotiationThread
from app.services.negotiation_monitor.matching import link_email_to_thread, _is_generic_subject


def test_generic_subject_not_linked_alone():
    assert _is_generic_subject("Re: Contract") is True
    assert _is_generic_subject("Re: Master Service Agreement — Al-Falak Ltd") is False


def test_external_thread_id_match():
    tid = uuid.uuid4()
    email = MagicMock(external_thread_id="ext-1", reply_reference=None, subject="Hi", sender_email=None, thread_id=None)
    thread = MagicMock(id=tid, contract_id=uuid.uuid4())
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = thread
    res = link_email_to_thread(db, email=email, external_thread_id="ext-1")
    assert res.thread_id == tid
    assert res.needs_review is False


def test_ambiguous_counterparty_needs_review():
    email = MagicMock(
        external_thread_id=None,
        reply_reference=None,
        subject="Hello there",
        sender_email="a@b.com",
        thread_id=None,
    )
    t1 = MagicMock(id=uuid.uuid4(), contract_id=uuid.uuid4())
    t2 = MagicMock(id=uuid.uuid4(), contract_id=uuid.uuid4())
    db = MagicMock()

    def query_model(model):
        q = MagicMock()
        if model is NegotiationThread:
            q.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
                t1,
                t2,
            ]
        else:
            q.filter.return_value.limit.return_value.all.return_value = []
        return q

    db.query.side_effect = query_model
    db.get.return_value = None
    res = link_email_to_thread(db, email=email, sender_email="a@b.com", subject="Hello there")
    assert res.thread_id is None
    assert res.needs_review is True
