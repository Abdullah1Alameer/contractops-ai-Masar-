"""Signature field placement inside the actual document — see
docs/signature-placement-and-template-flow-report.md."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import fitz
import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import ApprovalWorkflow, Contract, ContractVersion, SignatureField, SignatureRequest
from app.services.storage import storage

AUTH = {"Authorization": "Bearer demo-secret-token", "X-Demo-Role": "legal"}


def _pdf_bytes(pages: int = 2):
    document = fitz.open()
    for i in range(pages):
        document.new_page().insert_text((72, 72), f"Synthetic page {i + 1}")
    data = document.tobytes()
    document.close()
    return data


@pytest.fixture(autouse=True)
def portal_token_secret(monkeypatch):
    monkeypatch.setenv("PORTAL_TOKEN_SECRET", "signature-field-secret")


@pytest.fixture
def field_db():
    db = SessionLocal()
    contract_ids = []

    def create_contract(*, pages=2):
        file_key = storage.save(_pdf_bytes(pages), "field-placement.pdf")
        contract = Contract(
            id=uuid4(), title="Synthetic field placement", status="ready",
            stage="ready_to_sign", supported=True, file_url=file_key,
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
            "signers": [
                {"name": "Signer One", "email": "one@example.invalid", "role": "company_signatory", "order": 1},
                {"name": "Signer Two", "email": "two@example.invalid", "role": "client_signatory", "order": 2},
            ],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_send_is_blocked_until_every_signer_has_a_signature_field(field_db):
    db, create_contract = field_db
    contract, _ = create_contract()
    client = TestClient(app)
    created = _create_request(client, contract.id)
    request_id = created["request"]["id"]

    response = client.post(f"/api/signature-requests/{request_id}/send", headers=AUTH)

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "signature_fields_required"


def test_placing_and_persisting_field_coordinates(field_db):
    db, create_contract = field_db
    contract, version = create_contract()
    client = TestClient(app)
    created = _create_request(client, contract.id)
    request_id = created["request"]["id"]
    signer_ids = [s["id"] for s in created["signers"]]

    response = client.put(
        f"/api/signature-requests/{request_id}/fields",
        headers=AUTH,
        json={
            "fields": [
                {"signer_id": signer_ids[0], "page_number": 1, "x": 0.1, "y": 0.2, "width": 0.3, "height": 0.05, "field_type": "signature", "required": True},
                {"signer_id": signer_ids[1], "page_number": 2, "x": 0.1, "y": 0.4, "width": 0.3, "height": 0.05, "field_type": "signature", "required": True},
            ]
        },
    )

    assert response.status_code == 200, response.text
    fields = response.json()["fields"]
    assert len(fields) == 2
    assert all(f["ai_suggested"] is False for f in fields)

    db.expire_all()
    stored = db.query(SignatureField).filter_by(signature_request_id=request_id).all()
    assert len(stored) == 2
    # Fields belong to the request's version — the one that was current and
    # approved at request-creation time.
    assert all(str(f.version_id) == str(version.id) for f in stored)
    pages = sorted(f.page_number for f in stored)
    assert pages == [1, 2]


def test_two_ordered_signers_have_distinct_fields_and_signer_only_sees_their_own(field_db):
    db, create_contract = field_db
    contract, _ = create_contract()
    client = TestClient(app)
    created = _create_request(client, contract.id)
    request_id = created["request"]["id"]
    signer_ids = [s["id"] for s in created["signers"]]

    client.put(
        f"/api/signature-requests/{request_id}/fields",
        headers=AUTH,
        json={
            "fields": [
                {"signer_id": signer_ids[0], "page_number": 1, "x": 0.1, "y": 0.1, "width": 0.3, "height": 0.05, "field_type": "signature", "required": True},
                {"signer_id": signer_ids[1], "page_number": 1, "x": 0.1, "y": 0.5, "width": 0.3, "height": 0.05, "field_type": "signature", "required": True},
            ]
        },
    )
    sent = client.post(f"/api/signature-requests/{request_id}/send", headers=AUTH)
    assert sent.status_code == 200, sent.text
    token_one = next(row["token"] for row in created["signer_links"] if row["order"] == 1)
    token_two = next(row["token"] for row in created["signer_links"] if row["order"] == 2)

    portal_one = client.post(f"/api/public/sign/{token_one}/open")
    assert portal_one.status_code == 200, portal_one.text
    body_one = portal_one.json()
    assert len(body_one["fields"]) == 1
    assert body_one["fields"][0]["signer_id"] == signer_ids[0]

    # Signer two is waiting for signer one (signing order enabled) — but a
    # fetch of the raw bundle still exposes only signer two's own field, not
    # signer one's, regardless of ordering state.
    bundle_two = client.get(f"/api/public/sign/{token_two}")
    assert bundle_two.status_code == 200, bundle_two.text
    body_two = bundle_two.json()
    assert len(body_two["fields"]) == 1
    assert body_two["fields"][0]["signer_id"] == signer_ids[1]


def test_typed_signature_embeds_at_the_confirmed_field_location(field_db):
    db, create_contract = field_db
    contract, _ = create_contract(pages=1)
    client = TestClient(app)
    created = _create_request(client, contract.id)
    request_id = created["request"]["id"]
    signer_ids = [s["id"] for s in created["signers"]]

    client.put(
        f"/api/signature-requests/{request_id}/fields",
        headers=AUTH,
        json={
            "fields": [
                {"signer_id": signer_ids[0], "page_number": 1, "x": 0.1, "y": 0.1, "width": 0.3, "height": 0.05, "field_type": "signature", "required": True},
                {"signer_id": signer_ids[1], "page_number": 1, "x": 0.1, "y": 0.5, "width": 0.3, "height": 0.05, "field_type": "signature", "required": True},
            ]
        },
    )
    client.post(f"/api/signature-requests/{request_id}/send", headers=AUTH)
    token_one = next(row["token"] for row in created["signer_links"] if row["order"] == 1)
    token_two = next(row["token"] for row in created["signer_links"] if row["order"] == 2)

    for token, name in ((token_one, "Signer One"), (token_two, "Signer Two")):
        response = client.post(
            f"/api/public/sign/{token}/submit",
            json={
                "signature_type": "typed",
                "signature_value": name,
                "consent_accepted": True,
                "signer_name_confirmation": name,
            },
        )
        assert response.status_code == 200, response.text

    db.expire_all()
    req = db.get(SignatureRequest, request_id)
    assert req.status == "completed"
    assert req.signed_file_url is not None
    signed_bytes = storage.get(req.signed_file_url)
    doc = fitz.open(stream=signed_bytes, filetype="pdf")
    # The fix: no new page is appended purely for the signature block — the
    # original single page still holds the whole document, with both marks
    # embedded onto it.
    assert doc.page_count == 1
    page_text = doc[0].get_text()
    doc.close()
    assert "Signer One" in page_text
    assert "Signer Two" in page_text


def test_duplicate_signing_creates_no_duplicate_artifacts(field_db):
    db, create_contract = field_db
    contract, _ = create_contract(pages=1)
    client = TestClient(app)
    created = _create_request(client, contract.id)
    request_id = created["request"]["id"]
    signer_ids = [s["id"] for s in created["signers"]]
    client.put(
        f"/api/signature-requests/{request_id}/fields",
        headers=AUTH,
        json={
            "fields": [
                {"signer_id": signer_ids[0], "page_number": 1, "x": 0.1, "y": 0.1, "width": 0.3, "height": 0.05, "field_type": "signature", "required": True},
                {"signer_id": signer_ids[1], "page_number": 1, "x": 0.1, "y": 0.5, "width": 0.3, "height": 0.05, "field_type": "signature", "required": True},
            ]
        },
    )
    client.post(f"/api/signature-requests/{request_id}/send", headers=AUTH)
    token_one = next(row["token"] for row in created["signer_links"] if row["order"] == 1)
    token_two = next(row["token"] for row in created["signer_links"] if row["order"] == 2)
    for token, name in ((token_one, "Signer One"), (token_two, "Signer Two")):
        client.post(
            f"/api/public/sign/{token}/submit",
            json={"signature_type": "typed", "signature_value": name, "consent_accepted": True, "signer_name_confirmation": name},
        )

    # Retry submitting signer one again after completion.
    retry = client.post(
        f"/api/public/sign/{token_one}/submit",
        json={"signature_type": "typed", "signature_value": "Signer One", "consent_accepted": True, "signer_name_confirmation": "Signer One"},
    )
    assert retry.status_code == 409

    db.expire_all()
    fields = db.query(SignatureField).filter_by(signature_request_id=request_id).all()
    assert len(fields) == 2  # unchanged — no duplicate rows from the retried submit


def test_field_coordinates_reference_confirmed_page_and_reject_out_of_range(field_db):
    db, create_contract = field_db
    contract, _ = create_contract(pages=1)
    client = TestClient(app)
    created = _create_request(client, contract.id)
    request_id = created["request"]["id"]
    signer_ids = [s["id"] for s in created["signers"]]

    response = client.put(
        f"/api/signature-requests/{request_id}/fields",
        headers=AUTH,
        json={
            "fields": [
                {"signer_id": signer_ids[0], "page_number": 5, "x": 0.1, "y": 0.1, "width": 0.3, "height": 0.05, "field_type": "signature", "required": True},
                {"signer_id": signer_ids[1], "page_number": 1, "x": 0.1, "y": 0.5, "width": 0.3, "height": 0.05, "field_type": "signature", "required": True},
            ]
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "field_page_invalid"


def test_ai_suggested_fields_are_not_persisted_until_confirmed(field_db):
    db, create_contract = field_db
    contract, _ = create_contract()
    client = TestClient(app)
    created = _create_request(client, contract.id)
    request_id = created["request"]["id"]

    suggested = client.get(f"/api/signature-requests/{request_id}/fields/suggest", headers=AUTH)
    assert suggested.status_code == 200, suggested.text
    assert all(f["ai_suggested"] is True for f in suggested.json()["fields"])

    db.expire_all()
    persisted = db.query(SignatureField).filter_by(signature_request_id=request_id).all()
    assert persisted == []  # suggestion alone never writes rows

    # Confirming the exact suggested set persists it, and it is no longer
    # flagged as an un-reviewed AI suggestion — a human explicitly saved it.
    save = client.put(f"/api/signature-requests/{request_id}/fields", headers=AUTH, json={"fields": suggested.json()["fields"]})
    assert save.status_code == 200, save.text
    assert all(f["ai_suggested"] is False for f in save.json()["fields"])
