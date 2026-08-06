"""Contract-level lifecycle actions that don't belong to a downstream
workflow domain (review/negotiation/approval/signature) — currently just
the draft -> ready_for_client entry action.

Every mutation here goes through `LifecycleService.transition()`; nothing
assigns `contract.stage` directly, and workflow/activity state is
committed exactly once per call.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import Contract, ReviewRequest
from . import approvals
from .lifecycle import LifecycleError, LifecycleEvent, LifecycleService
from .versions import current_version

# Ingestion is "usable" for the same statuses reviews.create_review_request
# already requires (reviews._USABLE_CONTRACT_STATUSES) — kept as an
# independent constant here, matching how every other service module in
# this codebase defines its own local copy rather than importing another
# module's private name.
_USABLE_CONTRACT_STATUSES = frozenset({"ready", "needs_review"})
_ACTIONABLE_REVIEW_STATUSES = frozenset({"sent", "opened"})


def _lock_contract(contract_id, db: Session) -> Contract:
    contract = (
        db.query(Contract)
        .filter(Contract.id == contract_id)
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    if contract is None:
        raise LifecycleError(status_code=404, code="not_found")
    return contract


def mark_ready_for_client(contract_id, db: Session, *, actor: str) -> dict:
    """draft -> ready_for_client, the one internal action that unlocks
    Send for Client Review. Validates, in order:

    - a current version exists;
    - extraction/classification finished and the document is supported
      (ingestion `status` in {ready, needs_review}, `supported is not
      False`) — surfaced through the same `contract_ready`/`supported`
      metadata the DRAFT -> CONTRACT_READY_FOR_CLIENT rule's own
      `_validate_ready` validator already checks, so this function does
      not duplicate that logic, it only supplies the evidence;
    - no already-active review on the current version;
    - no unresolved negotiation on the current version.

    The stage-source check ("only valid from draft") is enforced by
    `LifecycleService.validate_transition()` itself via the rule table —
    calling this from any other stage raises the same deterministic
    `409 invalid_stage_transition` every other illegal transition raises.
    """
    try:
        contract = _lock_contract(contract_id, db)
        version = current_version(contract.id, db)
        if version is None:
            raise LifecycleError(status_code=409, code="no_current_version")

        active_review = (
            db.query(ReviewRequest)
            .filter(
                ReviewRequest.contract_id == contract.id,
                ReviewRequest.version_id == version.id,
                ReviewRequest.status.in_(_ACTIONABLE_REVIEW_STATUSES),
            )
            .with_for_update()
            .first()
        )
        if active_review is not None:
            raise LifecycleError(status_code=409, code="review_already_active")

        unresolved = approvals.unresolved_negotiations(contract.id, db)
        if unresolved:
            raise LifecycleError(
                status_code=409,
                code="unresolved_negotiations",
                payload={"error": "unresolved_negotiations", "unresolved": unresolved},
            )

        supported = contract.supported is not False
        contract_ready = supported and contract.status in _USABLE_CONTRACT_STATUSES

        transition = LifecycleService.transition(
            contract,
            LifecycleEvent.CONTRACT_READY_FOR_CLIENT,
            actor,
            metadata={
                "contract_ready": contract_ready,
                "supported": supported,
                "version_id": str(version.id),
            },
        )
        if transition.changed:
            approvals.log_activity(
                db,
                contract.id,
                transition.activity_event.value,
                actor=actor,
                metadata=transition.activity_metadata,
            )
        db.commit()
        db.refresh(contract)
    except Exception:
        db.rollback()
        raise

    return {"id": str(contract.id), "stage": contract.stage}
