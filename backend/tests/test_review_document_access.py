"""Public Review Portal document access — audit finding #1 ("Missing
Contract Viewer"): the portal previously exposed only extracted AI data
and never the contract itself, and no public document endpoint existed
at all (confirmed by a full grep of reviews_public.py's route list).

Fix: `GET /api/review/{token}/document`, gated by the exact same
`_rate`/`_load`/`expire_if_needed` boundary as every other public review
route, serving the same guaranteed-renderable PDF single source of truth
(`services/signature_pdf.py::original_bytes`) already used by the
signature flow — real PDF pass-through when the upload actually is a
PDF, otherwise a PDF generated from the extracted text. See
docs/review-portal-document-access-redesign.md.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import fitz
import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Contract, ContractVersion, ReviewRequest
from app.services.storage import storage

AUTH = {"Authorization": "Bearer demo-secret-token", "X-Demo-Role": "legal"}


def _pdf_bytes(text: str):
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture(autouse=True)
def portal_token_secret(monkeypatch):
    monkeypatch.setenv("PORTAL_TOKEN_SECRET", "review-document-access-secret")


@pytest.fixture
def doc_db():
    db = SessionLocal()
    contract_ids = []

    def create_contract(*, file_bytes: bytes, file_name: str, raw_text: str | None = None):
        file_key = storage.save(file_bytes, file_name)
        contract = Contract(
            id=uuid4(), title="Synthetic review-document contract", status="ready",
            stage="ready_for_client", supported=True, file_url=file_key, raw_text=raw_text,
        )
        version = ContractVersion(
            id=uuid4(), contract_id=contract.id, version_number=1, version_label="v1",
            source="initial_upload", status="ready", file_path=contract.file_url,
            is_current=True, created_by="synthetic-test",
        )
        db.add_all([contract, version])
        db.commit()
        contract_ids.append(contract.id)
        return contract

    yield db, create_contract

    db.rollback()
    for contract_id in contract_ids:
        row = db.get(Contract, contract_id)
        if row is not None:
            db.delete(row)
    db.commit()
    db.close()


def _send_and_get_token(client, contract_id) -> str:
    response = client.post(
        f"/api/contracts/{contract_id}/review/send",
        headers=AUTH,
        json={
            "recipient_name": "Synthetic Reviewer",
            "recipient_email": "reviewer@example.invalid",
            "sender_name": "Synthetic Sender",
            "sender_email": "sender@example.invalid",
            "expires_in_days": 7,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["request"]["token"]


def test_uploaded_pdf_is_served_as_is(doc_db):
    db, create_contract = doc_db
    contract = create_contract(file_bytes=_pdf_bytes("Real uploaded review PDF"), file_name="upload.pdf")
    client = TestClient(app)
    token = _send_and_get_token(client, contract.id)

    response = client.get(f"/api/review/{token}/document")

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    doc = fitz.open(stream=response.content, filetype="pdf")
    text = doc[0].get_text()
    doc.close()
    assert "Real uploaded review PDF" in text


def test_docx_sourced_contract_obtains_a_renderable_representation(doc_db):
    db, create_contract = doc_db
    docx_like_bytes = b"PK\x03\x04this is not a pdf, it is a fake docx payload"
    contract = create_contract(
        file_bytes=docx_like_bytes, file_name="upload.docx",
        raw_text="Clause 4: The Client shall pay all invoices within fifteen (15) days.",
    )
    client = TestClient(app)
    token = _send_and_get_token(client, contract.id)

    response = client.get(f"/api/review/{token}/document")

    assert response.status_code == 200, response.text
    assert response.content[:4] == b"%PDF"
    doc = fitz.open(stream=response.content, filetype="pdf")
    text = doc[0].get_text()
    doc.close()
    assert "The Client shall pay all invoices within fifteen" in text


def test_unknown_token_returns_deterministic_not_found(doc_db):
    client = TestClient(app)
    response = client.get("/api/review/does-not-exist/document")
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "review_not_found"


def test_expired_review_token_still_shows_the_document_read_only(doc_db):
    """expire_if_needed() marks the request `expired` but — matching the
    existing dossier/decision routes exactly — does not itself raise; an
    expired review is read-only (no more approve/reject/comment), not
    invisible. The document endpoint mirrors that, not a stricter rule of
    its own."""
    db, create_contract = doc_db
    contract = create_contract(file_bytes=_pdf_bytes("Expired token content"), file_name="upload.pdf")
    client = TestClient(app)
    token = _send_and_get_token(client, contract.id)

    req = db.query(ReviewRequest).filter_by(contract_id=contract.id).first()
    req.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db.commit()

    portal = client.get(f"/api/review/{token}").json()
    assert portal["status"] == "expired"

    response = client.get(f"/api/review/{token}/document")
    assert response.status_code == 200, response.text
    assert response.content[:4] == b"%PDF"


def test_document_url_in_the_dossier_resolves_to_the_same_bytes(doc_db):
    """The `document_url` field the portal payload exposes must actually
    resolve — not a dangling reference to an endpoint that doesn't
    match."""
    db, create_contract = doc_db
    contract = create_contract(file_bytes=_pdf_bytes("Linked document check"), file_name="upload.pdf")
    client = TestClient(app)
    token = _send_and_get_token(client, contract.id)

    portal = client.get(f"/api/review/{token}").json()
    assert portal["document_url"] == f"/api/review/{token}/document"

    doc = client.get(portal["document_url"])
    assert doc.status_code == 200
    assert doc.headers["content-type"] == "application/pdf"
