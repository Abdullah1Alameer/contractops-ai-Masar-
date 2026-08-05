"""Simulated email inbox for hackathon demos."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .base import (
    EmailAttachmentDTO,
    EmailConnector,
    EmailMessageDTO,
    EmailThreadDTO,
    OutboundEmailRequest,
    OutboundEmailResult,
)

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "demo_inbox.json"
_PROCESSED: set[str] = set()


def _load_fixture() -> dict:
    if not _FIXTURE.exists():
        return {"threads": []}
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def _msg_from_raw(raw: dict) -> EmailMessageDTO:
    attachments = []
    for att in raw.get("attachments") or []:
        content = None
        if att.get("inline_text"):
            content = att["inline_text"].encode("utf-8")
        attachments.append(
            EmailAttachmentDTO(
                external_id=att["external_id"],
                filename=att["filename"],
                mime_type=att.get("mime_type"),
                size_bytes=att.get("size_bytes"),
                content=content,
            )
        )
    return EmailMessageDTO(
        external_message_id=raw["external_message_id"],
        external_thread_id=raw.get("external_thread_id"),
        sender_name=raw.get("sender_name"),
        sender_email=raw.get("sender_email"),
        recipients=list(raw.get("recipients") or []),
        cc=list(raw.get("cc") or []),
        subject=raw.get("subject"),
        body_text=raw.get("body_text"),
        body_html=raw.get("body_html"),
        received_at=raw.get("received_at"),
        reply_reference=raw.get("reply_reference"),
        attachments=attachments,
    )


class SimulatedEmailConnector(EmailConnector):
    name = "simulated"

    def list_threads(self, *, limit: int = 50) -> list[EmailThreadDTO]:
        data = _load_fixture()
        out: list[EmailThreadDTO] = []
        for t in data.get("threads", [])[:limit]:
            msgs = [_msg_from_raw(m) for m in t.get("messages", [])]
            out.append(
                EmailThreadDTO(
                    external_thread_id=t["external_thread_id"],
                    subject=t.get("subject"),
                    messages=msgs,
                )
            )
        return out

    def get_thread(self, external_thread_id: str) -> EmailThreadDTO | None:
        for t in self.list_threads(limit=500):
            if t.external_thread_id == external_thread_id:
                return t
        return None

    def get_message(self, external_message_id: str) -> EmailMessageDTO | None:
        for t in self.list_threads(limit=500):
            for m in t.messages:
                if m.external_message_id == external_message_id:
                    return m
        return None

    def download_attachment(self, external_message_id: str, external_attachment_id: str) -> bytes:
        msg = self.get_message(external_message_id)
        if msg is None:
            raise ValueError("message_not_found")
        for att in msg.attachments:
            if att.external_id == external_attachment_id and att.content:
                return att.content
        raise ValueError("attachment_not_found")

    def send_message(self, request: OutboundEmailRequest) -> OutboundEmailResult:
        ext_id = f"sim-out-{uuid.uuid4().hex[:12]}"
        sent = datetime.now(timezone.utc).isoformat()
        return OutboundEmailResult(external_message_id=ext_id, sent_at=sent, provider=self.name)

    def mark_processed(self, external_message_id: str) -> None:
        _PROCESSED.add(external_message_id)
