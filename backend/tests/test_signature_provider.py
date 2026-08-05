from app.integrations.esign import get_provider
from app.integrations.esign.simulated import SimulatedESignProvider


def test_default_provider_simulated():
    p = get_provider()
    assert p.name == "simulated"


def test_simulated_signer_link():
    p = SimulatedESignProvider()
    link = p.get_signer_link(token="abc", metadata={})
    assert "/sign/abc" in link
