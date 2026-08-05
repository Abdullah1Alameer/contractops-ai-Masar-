"""Microsoft Outlook / Graph connector skeleton — no live API calls in MVP."""
from __future__ import annotations

import os

from .base import (
    EmailConnector,
    EmailMessageDTO,
    EmailThreadDTO,
    OutboundEmailRequest,
    OutboundEmailResult,
)


class OutlookConnector(EmailConnector):
    """TODO: Microsoft Graph mail integration."""

    name = "outlook"

    def __init__(self) -> None:
        self.tenant_id = os.getenv("MS_TENANT_ID", "")
        self.client_id = os.getenv("MS_CLIENT_ID", "")
        self.client_secret = os.getenv("MS_CLIENT_SECRET", "")

    def list_threads(self, *, limit: int = 50) -> list[EmailThreadDTO]:
        raise NotImplementedError("outlook_connector_not_configured")

    def get_thread(self, external_thread_id: str) -> EmailThreadDTO | None:
        raise NotImplementedError("outlook_connector_not_configured")

    def get_message(self, external_message_id: str) -> EmailMessageDTO | None:
        raise NotImplementedError("outlook_connector_not_configured")

    def download_attachment(self, external_message_id: str, external_attachment_id: str) -> bytes:
        raise NotImplementedError("outlook_connector_not_configured")

    def send_message(self, request: OutboundEmailRequest) -> OutboundEmailResult:
        raise NotImplementedError("outlook_connector_not_configured")

    def mark_processed(self, external_message_id: str) -> None:
        raise NotImplementedError("outlook_connector_not_configured")
