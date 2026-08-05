"""Gmail connector skeleton — no live API calls in MVP."""
from __future__ import annotations

import os

from .base import (
    EmailConnector,
    EmailMessageDTO,
    EmailThreadDTO,
    OutboundEmailRequest,
    OutboundEmailResult,
)


class GmailConnector(EmailConnector):
    """TODO: OAuth2 + Gmail Users.messages API mapping."""

    name = "gmail"

    def __init__(self) -> None:
        self.client_id = os.getenv("GMAIL_CLIENT_ID", "")
        self.client_secret = os.getenv("GMAIL_CLIENT_SECRET", "")
        self.refresh_token = os.getenv("GMAIL_REFRESH_TOKEN", "")

    def list_threads(self, *, limit: int = 50) -> list[EmailThreadDTO]:
        raise NotImplementedError("gmail_connector_not_configured")

    def get_thread(self, external_thread_id: str) -> EmailThreadDTO | None:
        raise NotImplementedError("gmail_connector_not_configured")

    def get_message(self, external_message_id: str) -> EmailMessageDTO | None:
        raise NotImplementedError("gmail_connector_not_configured")

    def download_attachment(self, external_message_id: str, external_attachment_id: str) -> bytes:
        raise NotImplementedError("gmail_connector_not_configured")

    def send_message(self, request: OutboundEmailRequest) -> OutboundEmailResult:
        raise NotImplementedError("gmail_connector_not_configured")

    def mark_processed(self, external_message_id: str) -> None:
        raise NotImplementedError("gmail_connector_not_configured")
