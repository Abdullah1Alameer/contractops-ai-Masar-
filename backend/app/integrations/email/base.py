"""Abstract email connector contract."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EmailAttachmentDTO:
    external_id: str
    filename: str
    mime_type: str | None
    size_bytes: int | None
    content: bytes | None = None


@dataclass
class EmailMessageDTO:
    external_message_id: str
    external_thread_id: str | None
    sender_name: str | None
    sender_email: str | None
    recipients: list[str] = field(default_factory=list)
    cc: list[str] = field(default_factory=list)
    subject: str | None = None
    body_text: str | None = None
    body_html: str | None = None
    received_at: str | None = None
    reply_reference: str | None = None
    attachments: list[EmailAttachmentDTO] = field(default_factory=list)


@dataclass
class EmailThreadDTO:
    external_thread_id: str
    subject: str | None
    messages: list[EmailMessageDTO]


@dataclass
class OutboundEmailRequest:
    thread_id: str | None
    external_thread_id: str | None
    to: list[str]
    cc: list[str]
    subject: str
    body_text: str
    body_html: str | None = None
    reply_reference: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OutboundEmailResult:
    external_message_id: str
    sent_at: str
    provider: str


class EmailConnector(ABC):
    name: str = "base"

    @abstractmethod
    def list_threads(self, *, limit: int = 50) -> list[EmailThreadDTO]:
        ...

    @abstractmethod
    def get_thread(self, external_thread_id: str) -> EmailThreadDTO | None:
        ...

    @abstractmethod
    def get_message(self, external_message_id: str) -> EmailMessageDTO | None:
        ...

    @abstractmethod
    def download_attachment(self, external_message_id: str, external_attachment_id: str) -> bytes:
        ...

    @abstractmethod
    def send_message(self, request: OutboundEmailRequest) -> OutboundEmailResult:
        ...

    @abstractmethod
    def mark_processed(self, external_message_id: str) -> None:
        ...
