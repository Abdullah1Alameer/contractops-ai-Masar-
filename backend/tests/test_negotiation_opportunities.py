"""Negotiation opportunity heuristics."""
import re

from app.services.negotiation_opportunities import _AUTO_RENEW, _STATUTORY


def test_may_alone_insufficient():
    quote = "The employee may take leave as permitted by policy."
    assert not _AUTO_RENEW.search(quote)


def test_auto_renew_structural():
    quote = "automatically renewed for an equivalent period, at least 10 days before the contract end date"
    assert _AUTO_RENEW.search(quote)


def test_statutory_marked():
    assert _STATUTORY.search("Ministry of Human Resources and Social Development")


def test_human_decision_required_in_service():
    from app.services.negotiation_opportunities import serialize_opportunity
    from app.models import NegotiationOpportunity

    row = NegotiationOpportunity(
        category="auto_renewal",
        human_decision_required=True,
    )
    out = serialize_opportunity(row)
    assert out["human_decision_required"] is True
