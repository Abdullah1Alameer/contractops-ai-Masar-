"""Central contract lifecycle — only this module may change contracts.stage."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import Contract

ALLOWED_STAGES = frozenset(
    {
        "negotiation",
        "internal_review",
        "approved",
        "awaiting_signature",
        "partially_signed",
        "signed",
        "active",
    }
)
APPROVAL_START_STAGES = frozenset({"negotiation", "internal_review"})
SIGNATURE_CREATE_STAGE = "approved"
DECLINE_REVERT_STAGE = "negotiation"


def set_stage(contract: Contract, stage: str, db: Session) -> Contract:
    if stage not in ALLOWED_STAGES:
        raise ValueError("invalid_stage")
    old = contract.stage
    contract.stage = stage
    db.commit()
    db.refresh(contract)
    if old != stage:
        from .approvals import log_activity

        log_activity(
            db,
            contract.id,
            "contract_stage_changed",
            metadata={"from": old, "to": stage},
        )
    return contract


def can_start_approval(contract: Contract | None) -> bool:
    if contract is None:
        return False
    return (contract.stage or "negotiation") in APPROVAL_START_STAGES


def can_create_signature(contract: Contract | None) -> bool:
    if contract is None:
        return False
    return (contract.stage or "negotiation") == SIGNATURE_CREATE_STAGE


def transition_stage(contract: Contract, stage: str, db: Session) -> Contract:
    """Alias used by signature service — same rules as set_stage."""
    return set_stage(contract, stage, db)
