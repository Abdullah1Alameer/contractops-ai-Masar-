"""Local-SMTP proof: review and signature invitations are real, valid email.

Starts a stdlib capture SMTP server bound to an ephemeral local port, points
`app.services.email_delivery.send_email` at it via env vars (config is read
at call time — see app/config.py), and drives real review/signature send
calls through the live app. Asserts the captured message is a proper
multipart (text + html) email, carries the expected portal URL, and never
contains a token, credential, or contract body in the envelope/subject.
"""
from __future__ import annotations

import asyncore
import smtpd
import threading
from datetime import datetime, timedelta, timezone
from email import message_from_bytes
from uuid import uuid4

import fitz
import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import ApprovalWorkflow, Contract, ContractVersion
from app.services.storage import storage

AUTH = {"Authorization": "Bearer demo-secret-token", "X-Demo-Role": "legal"}


class _CaptureSMTPServer(smtpd.SMTPServer):
    def __init__(self):
        super().__init__(("127.0.0.1", 0), None, decode_data=False)
        self.messages: list[dict] = []

    def process_message(self, peer, mailfrom, rcpttos, data, **kwargs):
        self.messages.append({"mailfrom": mailfrom, "rcpttos": list(rcpttos), "raw": data})

    @property
    def port(self) -> int:
        return self.socket.getsockname()[1]


@pytest.fixture
def capture_smtp(monkeypatch):
    server = _CaptureSMTPServer()

    def _loop():
        try:
            asyncore.loop(timeout=0.1)
        except Exception:
            pass

    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()

    monkeypatch.setenv("EMAIL_DELIVERY_ENABLED", "true")
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("SMTP_HOST", "127.0.0.1")
    monkeypatch.setenv("SMTP_PORT", str(server.port))
    monkeypatch.setenv("SMTP_USERNAME", "")
    monkeypatch.setenv("SMTP_PASSWORD", "")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "contracts@contractops.local")
    monkeypatch.setenv("SMTP_FROM_NAME", "ContractOps Demo")
    monkeypatch.setenv("SMTP_USE_TLS", "false")
    monkeypatch.setenv("SMTP_USE_SSL", "false")
    monkeypatch.setenv("SMTP_TIMEOUT_SECONDS", "5")
    monkeypatch.setenv("PUBLIC_APP_URL", "http://localhost:3000")
    monkeypatch.setenv("PORTAL_TOKEN_SECRET", "smtp-local-integration-secret")

    yield server

    try:
        server.close()
    except Exception:
        pass


def _pdf_bytes() -> bytes:
    document = fitz.open()
    document.new_page().insert_text((72, 72), "SMTP local integration synthetic contract")
    data = document.tobytes()
    document.close()
    return data


@pytest.fixture
def review_contract():
    db = SessionLocal()
    contract = Contract(
        id=uuid4(),
        title="SMTP local integration review",
        status="ready",
        stage="ready_for_client",
        supported=True,
        file_url="synthetic/smtp-local-review.pdf",
    )
    version = ContractVersion(
        id=uuid4(),
        contract_id=contract.id,
        version_number=1,
        version_label="v1",
        source="initial_upload",
        status="ready",
        file_path=contract.file_url,
        is_current=True,
        created_by="synthetic-test",
    )
    db.add_all([contract, version])
    db.commit()
    yield contract
    db.rollback()
    row = db.get(Contract, contract.id)
    if row is not None:
        db.delete(row)
    db.commit()
    db.close()


@pytest.fixture
def signature_contract():
    db = SessionLocal()
    file_key = storage.save(_pdf_bytes(), "smtp-local-signature.pdf")
    contract = Contract(
        id=uuid4(),
        title="SMTP local integration signature",
        status="ready",
        stage="ready_to_sign",
        supported=True,
        file_url=file_key,
    )
    version = ContractVersion(
        id=uuid4(),
        contract_id=contract.id,
        version_number=1,
        version_label="v1",
        source="initial_upload",
        status="approved",
        file_path=contract.file_url,
        is_current=True,
        created_by="synthetic-test",
    )
    db.add_all([contract, version])
    db.flush()
    db.add(ApprovalWorkflow(id=uuid4(), contract_id=contract.id, version_id=version.id, status="approved"))
    db.commit()
    yield contract
    db.rollback()
    row = db.get(Contract, contract.id)
    if row is not None:
        db.delete(row)
    db.commit()
    db.close()


def _decoded_text(raw: bytes) -> str:
    """Join every text part, decoded per its own Content-Transfer-Encoding.

    Raw bytes/`raw.decode()` still carry quoted-printable soft line breaks
    (e.g. a long link split with a trailing `=\\n`), so substring checks on
    a link must go through the decoded MIME payload instead.
    """
    parsed = message_from_bytes(raw)
    parts = []
    for part in parsed.walk():
        if part.get_content_maintype() == "text":
            payload = part.get_payload(decode=True) or b""
            parts.append(payload.decode(part.get_content_charset() or "utf-8", "ignore"))
    return "\n".join(parts)


def _assert_safe_email(raw: bytes, *, forbidden_substrings: list[str]) -> None:
    parsed = message_from_bytes(raw)
    assert parsed.is_multipart(), "invitation email must offer text + html alternatives"
    content_types = {part.get_content_type() for part in parsed.walk()}
    assert "text/plain" in content_types
    assert "text/html" in content_types
    subject = parsed.get("Subject", "")
    assert subject.strip(), "subject must be non-empty"
    assert "\n" not in subject and "\r" not in subject
    raw_text = raw.decode("utf-8", "ignore")
    for forbidden in forbidden_substrings:
        assert forbidden not in raw_text, f"email leaked forbidden value: {forbidden!r}"


def test_review_invitation_is_delivered_through_local_smtp(capture_smtp, review_contract):
    client = TestClient(app)
    response = client.post(
        f"/api/contracts/{review_contract.id}/review/send",
        headers=AUTH,
        json={
            "recipient_name": "Local SMTP Reviewer",
            "recipient_email": "local-smtp-reviewer@example.invalid",
            "sender_name": "Local SMTP Sender",
            "sender_email": "local-smtp-sender@example.invalid",
            "expires_in_days": 7,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["delivery"]["status"] == "sent"
    token = payload["request"]["token"]

    assert len(capture_smtp.messages) == 1
    message = capture_smtp.messages[0]
    assert message["rcpttos"] == ["local-smtp-reviewer@example.invalid"]
    assert message["mailfrom"] == "contracts@contractops.local"

    assert f"http://localhost:3000/review/{token}" in _decoded_text(message["raw"])
    _assert_safe_email(
        message["raw"],
        forbidden_substrings=["smtp-local-integration-secret", "PORTAL_TOKEN_SECRET"],
    )


def test_signature_invitation_is_delivered_through_local_smtp(capture_smtp, signature_contract):
    client = TestClient(app)
    created = client.post(
        f"/api/contracts/{signature_contract.id}/signature-request",
        headers=AUTH,
        json={
            "subject": "Please sign (SMTP local integration)",
            "message": "Synthetic signing invitation",
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "signing_order_enabled": True,
            "signers": [
                {"name": "Local Signer One", "email": "local-signer-one@example.invalid", "role": "company_signatory", "order": 1},
                {"name": "Local Signer Two", "email": "local-signer-two@example.invalid", "role": "client_signatory", "order": 2},
            ],
        },
    )
    assert created.status_code == 200, created.text
    request_id = created.json()["request"]["id"]
    token_one = next(
        row["token"] for row in created.json()["signer_links"] if row["email"] == "local-signer-one@example.invalid"
    )

    assert len(capture_smtp.messages) == 0, "creation must not send any invitation"

    sent = client.post(f"/api/signature-requests/{request_id}/send", headers=AUTH)
    assert sent.status_code == 200, sent.text
    deliveries = sent.json()["deliveries"]
    assert len(deliveries) == 1
    assert deliveries[0]["status"] == "sent"

    assert len(capture_smtp.messages) == 1
    message = capture_smtp.messages[0]
    assert message["rcpttos"] == ["local-signer-one@example.invalid"]

    assert f"http://localhost:3000/sign/{token_one}" in _decoded_text(message["raw"])
    _assert_safe_email(
        message["raw"],
        forbidden_substrings=["smtp-local-integration-secret"],
    )
