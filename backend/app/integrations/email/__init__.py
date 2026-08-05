from ...config import EMAIL_PROVIDER
from .base import EmailConnector
from .gmail import GmailConnector
from .outlook import OutlookConnector
from .simulated import SimulatedEmailConnector


def get_email_connector() -> EmailConnector:
    if EMAIL_PROVIDER == "gmail":
        return GmailConnector()
    if EMAIL_PROVIDER == "outlook":
        return OutlookConnector()
    return SimulatedEmailConnector()
