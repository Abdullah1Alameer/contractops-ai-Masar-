"""Create proposed contract versions from client revisions."""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from ...models import Contract, NegotiationAttachment
from ...services import versions as ver_svc
from .revision_detection import RevisionKind, detect_revision


def create_proposed_version_from_attachment(
    db: Session,
    *,
    contract: Contract,
    attachment: NegotiationAttachment,
    file_bytes: bytes,
    actor: str = "negotiation_monitor",
) -> tuple[str, object | None]:
    kind, file_hash, _ = detect_revision(
        db,
        contract=contract,
        file_bytes=file_bytes,
        filename=attachment.filename,
        mime_type=attachment.mime_type,
    )
    attachment.file_hash_sha256 = file_hash
    if kind == RevisionKind.same:
        attachment.processing_status = "completed"
        db.commit()
        return "duplicate", None
    if kind in (RevisionKind.unrelated, RevisionKind.supporting):
        attachment.processing_status = "completed"
        attachment.document_type = kind.value
        db.commit()
        return kind.value, None

    v = ver_svc.create_new_version(
        contract.id,
        db,
        source="client_revision",
        actor=actor,
        file_bytes=file_bytes,
        filename=attachment.filename,
        change_summary="Counterparty revision received via email",
        make_current=False,
        version_status="under_review",
        run_pipeline=False,
    )
    attachment.created_version_id = v.id
    attachment.processing_status = "completed"
    attachment.document_type = "revised_contract"
    db.commit()
    return "revised", v
