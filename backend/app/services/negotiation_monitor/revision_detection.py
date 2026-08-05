"""Detect whether an attachment is a contract revision."""
from __future__ import annotations

import hashlib
import re
from enum import Enum

from sqlalchemy.orm import Session

from ...models import Contract, ContractVersion
from ...services.textextract import TextExtractError, extract_pages, build_raw_text as pages_to_raw


class RevisionKind(str, Enum):
    same = "same"
    revised = "revised"
    unrelated = "unrelated"
    supporting = "supporting"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normalize_title(text: str) -> str:
    m = re.search(r"(MASTER SERVICE AGREEMENT|MSA|NDA|AGREEMENT)[^\n]{0,80}", text, re.I)
    return m.group(0).lower() if m else ""


def detect_revision(
    db: Session,
    *,
    contract: Contract,
    file_bytes: bytes,
    filename: str,
    mime_type: str | None = None,
) -> tuple[RevisionKind, str, str | None]:
    """Returns kind, sha256 hash, extracted text snippet."""
    file_hash = _sha256(file_bytes)
    cur = (
        db.query(ContractVersion)
        .filter_by(contract_id=contract.id, is_current=True)
        .order_by(ContractVersion.version_number.desc())
        .first()
    )
    if cur and cur.hash_sha256 and cur.hash_sha256 == file_hash:
        return RevisionKind.same, file_hash, None

    dup = (
        db.query(ContractVersion)
        .filter_by(contract_id=contract.id, hash_sha256=file_hash)
        .first()
    )
    if dup:
        return RevisionKind.same, file_hash, None

    try:
        pages = extract_pages(file_bytes, filename)
        raw, _ = pages_to_raw(pages)
    except TextExtractError:
        if filename.lower().endswith(".txt"):
            raw = file_bytes.decode("utf-8", errors="replace")
        else:
            return RevisionKind.unrelated, file_hash, None

    snippet = raw[:4000] if raw else ""
    ct = (contract.title or "").lower()
    if ct and len(ct) > 5 and ct not in snippet.lower():
        if "agreement" not in snippet.lower() and "contract" not in snippet.lower():
            return RevisionKind.supporting, file_hash, snippet

    if cur and cur.hash_sha256:
        return RevisionKind.revised, file_hash, snippet

    return RevisionKind.revised, file_hash, snippet
