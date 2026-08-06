"""Signature field-placement document viewer — release-blocking fix.

Root cause: the internal placement viewer fetched the CONTRACT's raw
uploaded file (GET /api/contracts/{id}/file), which for a DOCX-sourced
contract is a real Word document, not a PDF — pdfjs always failed to
parse it, and the UI showed only a static "showing the extracted-text
fallback" sentence with no actual fallback ever rendered.

Fix: a new, internal, request-scoped endpoint
(GET /api/signature-requests/{id}/document) returns the same
guaranteed-renderable PDF snapshot (real PDF pass-through, or a PDF
generated from the extracted text) already computed by
original_bytes()/create_request() and used by the public signer portal.
See docs/signature-placement-viewer-fix-report.md.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import fitz
import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import ApprovalWorkflow, Contract, ContractVersion, SignatureRequest
from app.services.storage import storage

AUTH = {"Authorization": "Bearer demo-secret-token", "X-Demo-Role": "legal"}


def _pdf_bytes(text: str = "Synthetic contract page"):
    document = fitz.open()
    document.new_page().insert_text((72, 72), text)
    data = document.tobytes()
    document.close()
    return data


@pytest.fixture(autouse=True)
def portal_token_secret(monkeypatch):
    monkeypatch.setenv("PORTAL_TOKEN_SECRET", "signature-document-viewer-secret")


@pytest.fixture
def viewer_db():
    db = SessionLocal()
    contract_ids = []

    def create_contract(*, file_bytes: bytes, file_name: str, raw_text: str | None = None):
        file_key = storage.save(file_bytes, file_name)
        contract = Contract(
            id=uuid4(), title="Synthetic viewer contract", status="ready",
            stage="ready_to_sign", supported=True, file_url=file_key, raw_text=raw_text,
        )
        version = ContractVersion(
            id=uuid4(), contract_id=contract.id, version_number=1, version_label="v1",
            source="initial_upload", status="approved", file_path=contract.file_url,
            is_current=True, created_by="synthetic-test",
        )
        db.add_all([contract, version])
        db.flush()
        db.add(ApprovalWorkflow(id=uuid4(), contract_id=contract.id, version_id=version.id, status="approved"))
        db.commit()
        contract_ids.append(contract.id)
        return contract, version

    yield db, create_contract

    db.rollback()
    for contract_id in contract_ids:
        contract = db.get(Contract, contract_id)
        if contract is not None:
            db.delete(contract)
    db.commit()
    db.close()


def _create_request(client, contract_id):
    response = client.post(
        f"/api/contracts/{contract_id}/signature-request",
        headers=AUTH,
        json={
            "subject": "Please sign",
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "signing_order_enabled": True,
            "signers": [{"name": "Signer One", "email": "one@example.invalid", "role": "company_signatory", "order": 1}],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_uploaded_pdf_renders_in_placement_view(viewer_db):
    db, create_contract = viewer_db
    contract, _ = create_contract(file_bytes=_pdf_bytes("Real uploaded PDF content"), file_name="upload.pdf")
    client = TestClient(app)
    created = _create_request(client, contract.id)
    request_id = created["request"]["id"]

    response = client.get(f"/api/signature-requests/{request_id}/document", headers=AUTH)

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    doc = fitz.open(stream=response.content, filetype="pdf")
    text = doc[0].get_text()
    doc.close()
    assert "Real uploaded PDF content" in text


def test_uploaded_docx_obtains_a_renderable_representation(viewer_db):
    """The exact bug: a DOCX-sourced contract's raw file is not a PDF at
    all. The document endpoint must still return something pdfjs can
    render — generated from the extracted text — never the raw DOCX
    bytes."""
    db, create_contract = viewer_db
    docx_like_bytes = b"PK\x03\x04this is not a pdf, it is a fake docx payload"
    contract, _ = create_contract(
        file_bytes=docx_like_bytes, file_name="upload.docx",
        raw_text="Clause 1: The Vendor shall deliver the goods within thirty (30) days.",
    )
    client = TestClient(app)
    created = _create_request(client, contract.id)
    request_id = created["request"]["id"]

    # Confirm the raw contract file endpoint really does return the
    # non-PDF bytes as-is (this is the endpoint the buggy viewer used to
    # call) — establishing that the bug is real before proving the fix.
    raw_file = client.get(f"/api/contracts/{contract.id}/file", headers=AUTH)
    assert raw_file.status_code == 200
    assert raw_file.content[:4] != b"%PDF"

    response = client.get(f"/api/signature-requests/{request_id}/document", headers=AUTH)

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert response.content[:4] == b"%PDF"
    doc = fitz.open(stream=response.content, filetype="pdf")
    text = doc[0].get_text()
    doc.close()
    assert "The Vendor shall deliver the goods within thirty" in text


def test_generated_template_contract_renders(viewer_db):
    """A template-generated contract's stored file is already a real PDF
    (built by the templates service) — confirms that path renders too,
    not just hand-uploaded PDFs."""
    db, create_contract = viewer_db
    contract, _ = create_contract(
        file_bytes=_pdf_bytes("Master Service Agreement — generated from template"),
        file_name="template_msa.pdf",
    )
    client = TestClient(app)
    created = _create_request(client, contract.id)
    request_id = created["request"]["id"]

    response = client.get(f"/api/signature-requests/{request_id}/document", headers=AUTH)

    assert response.status_code == 200, response.text
    doc = fitz.open(stream=response.content, filetype="pdf")
    text = doc[0].get_text()
    doc.close()
    assert "Master Service Agreement" in text


def test_document_endpoint_falls_back_to_regenerating_when_snapshot_missing(viewer_db):
    db, create_contract = viewer_db
    contract, _ = create_contract(
        file_bytes=b"not a pdf at all", file_name="broken.bin",
        raw_text="Regenerated fallback content for a missing snapshot.",
    )
    client = TestClient(app)
    created = _create_request(client, contract.id)
    request_id = created["request"]["id"]

    db.expire_all()
    req = db.get(SignatureRequest, request_id)
    req.original_file_url = None
    db.commit()

    response = client.get(f"/api/signature-requests/{request_id}/document", headers=AUTH)

    assert response.status_code == 200, response.text
    doc = fitz.open(stream=response.content, filetype="pdf")
    text = doc[0].get_text()
    doc.close()
    assert "Regenerated fallback content" in text


def test_unknown_request_returns_deterministic_not_found(viewer_db):
    client = TestClient(app)
    response = client.get(f"/api/signature-requests/{uuid4()}/document", headers=AUTH)
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "not_found"


def test_document_is_tied_to_the_exact_version_the_request_was_created_against(viewer_db):
    """Two different contracts (standing in for two versions with
    different content) must each get their own request's own snapshot —
    never a mix-up."""
    db, create_contract = viewer_db
    contract_a, _ = create_contract(file_bytes=_pdf_bytes("Version A unique content"), file_name="a.pdf")
    contract_b, _ = create_contract(file_bytes=_pdf_bytes("Version B unique content"), file_name="b.pdf")
    client = TestClient(app)
    request_a = _create_request(client, contract_a.id)["request"]["id"]
    request_b = _create_request(client, contract_b.id)["request"]["id"]

    doc_a = fitz.open(stream=client.get(f"/api/signature-requests/{request_a}/document", headers=AUTH).content, filetype="pdf")
    doc_b = fitz.open(stream=client.get(f"/api/signature-requests/{request_b}/document", headers=AUTH).content, filetype="pdf")
    text_a, text_b = doc_a[0].get_text(), doc_b[0].get_text()
    doc_a.close()
    doc_b.close()

    assert "Version A unique content" in text_a and "Version B unique content" not in text_a
    assert "Version B unique content" in text_b and "Version A unique content" not in text_b


def test_stale_version_cannot_receive_fields(viewer_db):
    db, create_contract = viewer_db
    contract, version = create_contract(file_bytes=_pdf_bytes(), file_name="stale.pdf")
    client = TestClient(app)
    created = _create_request(client, contract.id)
    request_id = created["request"]["id"]
    signer_id = created["signers"][0]["id"]

    # The document is still viewable against the (now historical) version...
    still_viewable = client.get(f"/api/signature-requests/{request_id}/document", headers=AUTH)
    assert still_viewable.status_code == 200

    # ...but a new current version supersedes it, and saving fields must
    # be refused rather than silently attaching them to a stale request.
    version.is_current = False
    db.add(ContractVersion(
        id=uuid4(), contract_id=contract.id, version_number=2, version_label="v2",
        source="internal_revision", status="approved", file_path=contract.file_url,
        is_current=True, created_by="synthetic-test",
    ))
    db.commit()

    response = client.put(
        f"/api/signature-requests/{request_id}/fields", headers=AUTH,
        json={"fields": [{"signer_id": signer_id, "page_number": 1, "x": 0.1, "y": 0.1, "width": 0.3, "height": 0.05, "field_type": "signature", "required": True}]},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "workflow_stale"
