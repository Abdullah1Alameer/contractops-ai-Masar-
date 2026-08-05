from ...config import ESIGN_PROVIDER
from .base import ESignProvider
from .signit import SignitESignProvider
from .simulated import SimulatedESignProvider


def get_provider() -> ESignProvider:
    if ESIGN_PROVIDER == "signit":
        return SignitESignProvider()
    return SimulatedESignProvider()
