"""Feature 9 digital signature tests."""
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.integrations.esign.signit import SignitESignProvider
from app.services import signature as sig_svc
from app.services.signature_pdf import sha256_hex


def test_cannot_create_before_approval():
    db = MagicMock()
    contract = SimpleNamespace(id=uuid.uuid4(), stage="negotiation")
    db.get.return_value = contract
    with pytest.raises(ValueError, match="invalid_stage_transition"):
        sig_svc.create_request(
            contract.id,
            db,
            subject="S",
            message=None,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            signing_order_enabled=True,
            signers=[{"name": "A", "email": "a@x.com", "role": "company_signatory", "order": 1}],
        )


def test_signers_required():
    with pytest.raises(ValueError, match="signers_required"):
        sig_svc._validate_signers_body([])


def test_token_hash_unique():
    a = sig_svc.hash_token("token-a")
    b = sig_svc.hash_token("token-b")
    assert a != b
    assert len(a) == 64


def test_signer_token_is_reproducible_and_stored_as_hash(monkeypatch):
    monkeypatch.setenv("PORTAL_TOKEN_SECRET", "test-portal-secret")

    material = sig_svc.generate_token_material()
    signer = SimpleNamespace(token_nonce=material.nonce)

    assert sig_svc.public_token_for_signer(signer) == material.public_token
    assert sig_svc.hash_token(material.public_token) == material.token_hash
    assert material.public_token != material.nonce


def test_signing_order_blocks_second():
    req_id = uuid.uuid4()
    s1 = SimpleNamespace(signer_order=1, status="invited")
    s2 = SimpleNamespace(signer_order=2, status="waiting")
    req = SimpleNamespace(signing_order_enabled=True)
    assert sig_svc._waiting_for_prior(s2, [s1, s2], True) is True
    s1.status = "signed"
    assert sig_svc._waiting_for_prior(s2, [s1, s2], True) is False


def test_decline_requires_reason():
    db = MagicMock()
    with pytest.raises(ValueError, match="reason_required"):
        sig_svc.decline_signature("tok", db, reason="  ", ip=None, user_agent=None)


def test_public_payload_no_internal_keys():
    cid = uuid.uuid4()
    rid = uuid.uuid4()
    sid = uuid.uuid4()
    signer = SimpleNamespace(
        id=sid,
        signature_request_id=rid,
        name="Ann",
        email="a@x.com",
        role="company_signatory",
        signer_order=1,
        status="invited",
        opened_at=None,
        signed_at=None,
    )
    req = SimpleNamespace(
        id=rid,
        contract_id=cid,
        subject="Subj",
        message="Msg",
        status="sent",
        expires_at=datetime.now(timezone.utc) + timedelta(days=3),
        signing_order_enabled=True,
        provider="simulated",
    )
    contract = SimpleNamespace(id=cid, title="Contract", party_a="Sender")
    db = MagicMock()

    with patch.object(sig_svc, "get_signer_by_token", return_value=signer):
        with patch.object(sig_svc, "get_request_by_id", return_value=req):
            with patch.object(sig_svc, "expire_if_needed", side_effect=lambda r, d: r):
                with patch.object(sig_svc, "_signers_for", return_value=[signer]):
                    with patch.object(sig_svc, "get_signer_by_token", return_value=signer):
                        db.get.return_value = contract
                        payload = sig_svc.build_public_payload("raw", db)
    forbidden = ("approval", "negotiation", "ai_summary", "risk", "counter_clause")
    blob = str(payload).lower()
    for f in forbidden:
        assert f not in blob


def test_expired_raises():
    signer = SimpleNamespace(signature_request_id=uuid.uuid4())
    req = SimpleNamespace(
        status="sent",
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        contract_id=uuid.uuid4(),
    )
    db = MagicMock()
    with patch.object(sig_svc, "get_signer_by_token", return_value=signer):
        with patch.object(sig_svc, "get_request_by_id", return_value=req):
            with patch.object(sig_svc, "expire_if_needed", side_effect=lambda r, d: setattr(r, "status", "expired") or r):
                with pytest.raises(ValueError, match="expired"):
                    sig_svc.build_public_payload("t", db)


def test_sha256_hash():
    h = sha256_hex(b"hello")
    assert h == sha256_hex(b"hello")
    assert h != sha256_hex(b"world")


def test_signit_raises():
    p = SignitESignProvider()
    with pytest.raises(NotImplementedError):
        p.create_request(contract_id="x", metadata={})


def test_build_invitation_bilingual():
    contract = SimpleNamespace(title="MSA")
    req = SimpleNamespace(subject="S", message="M", expires_at=datetime.now(timezone.utc))
    signer = SimpleNamespace(name="Ali")
    email = sig_svc.build_invitation_email(contract, req, signer, "http://link")
    assert "طلب توقيع" in email["subject_ar"]
    assert "Signature Request" in email["subject_en"]


