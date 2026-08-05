"""Canonical contract lifecycle engine and temporary legacy compatibility APIs."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Callable, Mapping, NoReturn

from sqlalchemy.orm import Session

from ..models import Contract


class ContractStage(str, Enum):
    DRAFT = "draft"
    READY_FOR_CLIENT = "ready_for_client"
    CLIENT_REVIEW = "client_review"
    NEGOTIATION = "negotiation"
    INTERNAL_REVIEW = "internal_review"
    READY_TO_SIGN = "ready_to_sign"
    PARTIALLY_SIGNED = "partially_signed"
    SIGNED = "signed"
    ACTIVE = "active"
    COMPLETED = "completed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    TERMINATED = "terminated"


class LegacyContractStage(str, Enum):
    """Temporary aliases for rows and callers that predate the canonical engine."""

    APPROVED = "approved"
    AWAITING_SIGNATURE = "awaiting_signature"


class LifecycleEvent(str, Enum):
    CONTRACT_CREATED = "contract_created"
    CONTRACT_RETURNED_TO_DRAFT = "contract_returned_to_draft"
    CONTRACT_READY_FOR_CLIENT = "contract_ready_for_client"
    CONTRACT_ENTERED_CLIENT_REVIEW = "contract_entered_client_review"
    CONTRACT_ENTERED_NEGOTIATION = "contract_entered_negotiation"
    CONTRACT_ENTERED_INTERNAL_REVIEW = "contract_entered_internal_review"
    CONTRACT_READY_TO_SIGN = "contract_ready_to_sign"
    CONTRACT_PARTIALLY_SIGNED = "contract_partially_signed"
    CONTRACT_SIGNED = "contract_signed"
    CONTRACT_ACTIVATED = "contract_activated"
    CONTRACT_COMPLETED = "contract_completed"
    CONTRACT_REJECTED = "contract_rejected"
    CONTRACT_CANCELLED = "contract_cancelled"
    CONTRACT_TERMINATED = "contract_terminated"

    INGESTION_STARTED = "ingestion_started"
    INGESTION_COMPLETED = "ingestion_completed"
    INGESTION_FAILED = "ingestion_failed"
    CURRENT_VERSION_REPLACED = "current_version_replaced"
    CLIENT_REVIEW_WAIVED = "client_review_waived"

    REVIEW_SENT = "review_sent"
    REVIEW_OPENED = "review_opened"
    REVIEW_APPROVED = "review_approved"
    REVIEW_REJECTED = "review_rejected"
    REVIEW_CHANGES_REQUESTED = "review_changes_requested"
    REVIEW_EXPIRED = "review_expired"
    REVIEW_CANCELLED = "review_cancelled"

    NEGOTIATION_STARTED = "negotiation_started"
    NEGOTIATION_ANALYSIS_REQUESTED = "negotiation_analysis_requested"
    NEGOTIATION_ANALYSIS_STARTED = "negotiation_analysis_started"
    NEGOTIATION_ANALYSIS_FAILED = "negotiation_analysis_failed"
    NEGOTIATION_ANALYZED = "negotiation_analyzed"
    NEGOTIATION_EDITED = "negotiation_edited"
    COUNTERPROPOSAL_SENT = "counterproposal_sent"
    NEGOTIATION_CLIENT_RESPONDED = "negotiation_client_responded"
    NEGOTIATION_ROUND_STARTED = "negotiation_round_started"
    NEGOTIATION_ACCEPTED = "negotiation_accepted"
    NEGOTIATION_CLOSED = "negotiation_closed"
    NEGOTIATION_REJECTED = "negotiation_rejected"
    NEGOTIATION_ABANDONED = "negotiation_abandoned"
    NEGOTIATION_SUPERSEDED = "negotiation_superseded"

    APPROVAL_STARTED = "approval_started"
    APPROVAL_STEP_APPROVED = "approval_step_approved"
    APPROVAL_COMPLETED = "approval_completed"
    APPROVAL_REJECTED = "approval_rejected"
    APPROVAL_CHANGES_REQUESTED = "approval_changes_requested"
    APPROVAL_CANCELLED = "approval_cancelled"

    SIGNATURE_REQUEST_CREATED = "signature_request_created"
    SIGNATURE_SENT = "signature_sent"
    SIGNATURE_VIEWED = "signature_viewed"
    SIGNATURE_PARTIALLY_SIGNED = "signature_partially_signed"
    SIGNATURE_COMPLETED = "signature_completed"
    SIGNATURE_DECLINED = "signature_declined"
    SIGNATURE_EXPIRED = "signature_expired"
    SIGNATURE_CANCELLED = "signature_cancelled"
    SIGNATURE_FAILED = "signature_failed"

    LEGAL_VOIDED = "legal_voided"
    AMENDMENT_STARTED = "amendment_started"


TERMINAL_STAGES = frozenset(
    {
        ContractStage.COMPLETED,
        ContractStage.REJECTED,
        ContractStage.CANCELLED,
        ContractStage.TERMINATED,
    }
)

# Temporary compatibility only. Remove after existing rows and workflow services
# have migrated to canonical lifecycle events.
LEGACY_STAGE_MAP: Mapping[LegacyContractStage, ContractStage] = {
    LegacyContractStage.APPROVED: ContractStage.READY_TO_SIGN,
    LegacyContractStage.AWAITING_SIGNATURE: ContractStage.READY_TO_SIGN,
}


def normalize_stage(stage: ContractStage | LegacyContractStage | str) -> ContractStage:
    if isinstance(stage, ContractStage):
        return stage
    if isinstance(stage, LegacyContractStage):
        return LEGACY_STAGE_MAP[stage]
    try:
        return ContractStage(stage)
    except (TypeError, ValueError):
        try:
            return LEGACY_STAGE_MAP[LegacyContractStage(stage)]
        except (TypeError, ValueError):
            raise LifecycleError(
                status_code=409,
                code="invalid_stage_transition",
                payload={"error": "invalid_stage_transition", "current_stage": str(stage)},
            ) from None


class LifecycleError(ValueError):
    def __init__(self, *, status_code: int, code: str, payload: Mapping[str, Any] | None = None):
        self.status_code = status_code
        self.code = code
        self.payload = dict(payload or {"error": code})
        super().__init__(code)


Validator = Callable[[Any, Mapping[str, Any]], None]


@dataclass(frozen=True)
class TransitionRule:
    current_stage: ContractStage
    event: LifecycleEvent
    next_stage: ContractStage
    validator: Validator
    activity_event: LifecycleEvent


@dataclass(frozen=True)
class TransitionResult:
    previous_stage: ContractStage
    next_stage: ContractStage
    event: LifecycleEvent
    activity_event: LifecycleEvent
    activity_metadata: Mapping[str, Any]

    @property
    def changed(self) -> bool:
        return self.previous_stage != self.next_stage


def _error(status_code: int, code: str, **payload: Any) -> NoReturn:
    raise LifecycleError(status_code=status_code, code=code, payload={"error": code, **payload})


def _metadata_value(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    if metadata is None:
        return {}
    if not isinstance(metadata, Mapping):
        _error(422, "invalid_transition_payload", field="metadata")
    return dict(metadata)


def _actor_value(actor: Any) -> str:
    if isinstance(actor, str):
        return actor.strip()
    if actor is None:
        return ""
    identifier = getattr(actor, "id", None)
    return str(identifier if identifier is not None else actor)


def _validate_actor(actor: Any, metadata: Mapping[str, Any]) -> None:
    if not _actor_value(actor) or metadata.get("authorized") is False:
        _error(403, "forbidden_transition")


def _require_fields(*fields: str) -> Validator:
    def validator(actor: Any, metadata: Mapping[str, Any]) -> None:
        _validate_actor(actor, metadata)
        missing = [field for field in fields if metadata.get(field) in (None, "")]
        if missing:
            _error(422, "invalid_transition_payload", missing_fields=missing)

    return validator


def _validate_ready(actor: Any, metadata: Mapping[str, Any]) -> None:
    _validate_actor(actor, metadata)
    if metadata.get("contract_ready") is False or metadata.get("supported") is False:
        _error(409, "contract_not_ready")


def _validate_no_active_workflow(actor: Any, metadata: Mapping[str, Any]) -> None:
    _validate_actor(actor, metadata)
    if metadata.get("workflow_active") is True:
        _error(409, "workflow_active")


def _validate_review_send(actor: Any, metadata: Mapping[str, Any]) -> None:
    _validate_actor(actor, metadata)
    if metadata.get("active_review") is True:
        _error(409, "review_already_active")


def _validate_review_action(actor: Any, metadata: Mapping[str, Any]) -> None:
    _validate_actor(actor, metadata)
    if metadata.get("review_closed") is True or metadata.get("active_review") is False:
        _error(409, "review_closed")


def _validate_negotiations_resolved(actor: Any, metadata: Mapping[str, Any]) -> None:
    _validate_actor(actor, metadata)
    if metadata.get("negotiations_resolved") is not True:
        _error(409, "unresolved_negotiations")


def _validate_approval_complete(actor: Any, metadata: Mapping[str, Any]) -> None:
    _validate_actor(actor, metadata)
    if metadata.get("approval_complete") is not True:
        _error(409, "approval_not_complete")


def _validate_signature_complete(actor: Any, metadata: Mapping[str, Any]) -> None:
    _validate_actor(actor, metadata)
    if metadata.get("signature_complete") is not True:
        _error(409, "signature_not_complete")


def _validate_activation(actor: Any, metadata: Mapping[str, Any]) -> None:
    _validate_actor(actor, metadata)
    if metadata.get("activation_ready") is not True:
        _error(409, "activation_not_ready")


def _validate_closeout(actor: Any, metadata: Mapping[str, Any]) -> None:
    _validate_actor(actor, metadata)
    if metadata.get("closeout_complete") is not True:
        _error(409, "closeout_incomplete")


def _validate_legal_void(actor: Any, metadata: Mapping[str, Any]) -> None:
    _require_fields("reason", "evidence")(actor, metadata)
    if metadata.get("privileged") is not True:
        _error(403, "forbidden_transition")


def _validate_amendment(actor: Any, metadata: Mapping[str, Any]) -> None:
    _validate_actor(actor, metadata)
    if metadata.get("formal_amendment") is not True:
        _error(409, "amendment_required")


def _rule(
    current_stage: ContractStage,
    event: LifecycleEvent,
    next_stage: ContractStage,
    *,
    validator: Validator = _validate_actor,
    activity_event: LifecycleEvent | None = None,
) -> TransitionRule:
    return TransitionRule(
        current_stage=current_stage,
        event=event,
        next_stage=next_stage,
        validator=validator,
        activity_event=activity_event or event,
    )


_TRANSITION_RULES = (
    _rule(ContractStage.DRAFT, LifecycleEvent.CONTRACT_CREATED, ContractStage.DRAFT),
    _rule(ContractStage.DRAFT, LifecycleEvent.INGESTION_STARTED, ContractStage.DRAFT),
    _rule(ContractStage.DRAFT, LifecycleEvent.INGESTION_COMPLETED, ContractStage.DRAFT),
    _rule(ContractStage.DRAFT, LifecycleEvent.INGESTION_FAILED, ContractStage.DRAFT),
    _rule(
        ContractStage.DRAFT,
        LifecycleEvent.CONTRACT_READY_FOR_CLIENT,
        ContractStage.READY_FOR_CLIENT,
        validator=_validate_ready,
    ),
    _rule(
        ContractStage.DRAFT,
        LifecycleEvent.CONTRACT_CANCELLED,
        ContractStage.CANCELLED,
        validator=_require_fields("reason"),
    ),
    _rule(
        ContractStage.READY_FOR_CLIENT,
        LifecycleEvent.REVIEW_SENT,
        ContractStage.CLIENT_REVIEW,
        validator=_validate_review_send,
        activity_event=LifecycleEvent.CONTRACT_ENTERED_CLIENT_REVIEW,
    ),
    _rule(
        ContractStage.READY_FOR_CLIENT,
        LifecycleEvent.CLIENT_REVIEW_WAIVED,
        ContractStage.INTERNAL_REVIEW,
        validator=_require_fields("reason"),
        activity_event=LifecycleEvent.CONTRACT_ENTERED_INTERNAL_REVIEW,
    ),
    _rule(
        ContractStage.READY_FOR_CLIENT,
        LifecycleEvent.CURRENT_VERSION_REPLACED,
        ContractStage.DRAFT,
        validator=_validate_no_active_workflow,
        activity_event=LifecycleEvent.CONTRACT_RETURNED_TO_DRAFT,
    ),
    _rule(
        ContractStage.READY_FOR_CLIENT,
        LifecycleEvent.CONTRACT_CANCELLED,
        ContractStage.CANCELLED,
        validator=_require_fields("reason"),
    ),
    _rule(
        ContractStage.CLIENT_REVIEW,
        LifecycleEvent.REVIEW_OPENED,
        ContractStage.CLIENT_REVIEW,
        validator=_validate_review_action,
    ),
    _rule(
        ContractStage.CLIENT_REVIEW,
        LifecycleEvent.REVIEW_APPROVED,
        ContractStage.INTERNAL_REVIEW,
        validator=_validate_review_action,
        activity_event=LifecycleEvent.CONTRACT_ENTERED_INTERNAL_REVIEW,
    ),
    _rule(
        ContractStage.CLIENT_REVIEW,
        LifecycleEvent.REVIEW_CHANGES_REQUESTED,
        ContractStage.NEGOTIATION,
        validator=_validate_review_action,
        activity_event=LifecycleEvent.CONTRACT_ENTERED_NEGOTIATION,
    ),
    _rule(
        ContractStage.CLIENT_REVIEW,
        LifecycleEvent.REVIEW_REJECTED,
        ContractStage.REJECTED,
        validator=_validate_review_action,
        activity_event=LifecycleEvent.CONTRACT_REJECTED,
    ),
    _rule(
        ContractStage.CLIENT_REVIEW,
        LifecycleEvent.REVIEW_EXPIRED,
        ContractStage.READY_FOR_CLIENT,
        validator=_validate_review_action,
        activity_event=LifecycleEvent.CONTRACT_READY_FOR_CLIENT,
    ),
    _rule(
        ContractStage.CLIENT_REVIEW,
        LifecycleEvent.REVIEW_CANCELLED,
        ContractStage.READY_FOR_CLIENT,
        validator=_validate_review_action,
        activity_event=LifecycleEvent.CONTRACT_READY_FOR_CLIENT,
    ),
    _rule(
        ContractStage.CLIENT_REVIEW,
        LifecycleEvent.CONTRACT_CANCELLED,
        ContractStage.CANCELLED,
        validator=_require_fields("reason"),
    ),
    _rule(
        ContractStage.NEGOTIATION,
        LifecycleEvent.NEGOTIATION_STARTED,
        ContractStage.NEGOTIATION,
    ),
    _rule(
        ContractStage.NEGOTIATION,
        LifecycleEvent.NEGOTIATION_ANALYSIS_REQUESTED,
        ContractStage.NEGOTIATION,
    ),
    _rule(
        ContractStage.NEGOTIATION,
        LifecycleEvent.NEGOTIATION_ANALYSIS_STARTED,
        ContractStage.NEGOTIATION,
    ),
    _rule(
        ContractStage.NEGOTIATION,
        LifecycleEvent.NEGOTIATION_ANALYSIS_FAILED,
        ContractStage.NEGOTIATION,
    ),
    _rule(
        ContractStage.NEGOTIATION,
        LifecycleEvent.NEGOTIATION_ANALYZED,
        ContractStage.NEGOTIATION,
    ),
    _rule(
        ContractStage.NEGOTIATION,
        LifecycleEvent.NEGOTIATION_EDITED,
        ContractStage.NEGOTIATION,
    ),
    _rule(
        ContractStage.NEGOTIATION,
        LifecycleEvent.COUNTERPROPOSAL_SENT,
        ContractStage.NEGOTIATION,
    ),
    _rule(
        ContractStage.NEGOTIATION,
        LifecycleEvent.NEGOTIATION_CLIENT_RESPONDED,
        ContractStage.NEGOTIATION,
    ),
    _rule(
        ContractStage.NEGOTIATION,
        LifecycleEvent.NEGOTIATION_ROUND_STARTED,
        ContractStage.NEGOTIATION,
    ),
    _rule(
        ContractStage.NEGOTIATION,
        LifecycleEvent.NEGOTIATION_CLOSED,
        ContractStage.NEGOTIATION,
    ),
    _rule(
        ContractStage.NEGOTIATION,
        LifecycleEvent.NEGOTIATION_SUPERSEDED,
        ContractStage.NEGOTIATION,
    ),
    _rule(
        ContractStage.NEGOTIATION,
        LifecycleEvent.NEGOTIATION_ACCEPTED,
        ContractStage.INTERNAL_REVIEW,
        validator=_validate_negotiations_resolved,
        activity_event=LifecycleEvent.CONTRACT_ENTERED_INTERNAL_REVIEW,
    ),
    _rule(
        ContractStage.NEGOTIATION,
        LifecycleEvent.NEGOTIATION_REJECTED,
        ContractStage.REJECTED,
        activity_event=LifecycleEvent.CONTRACT_REJECTED,
    ),
    _rule(
        ContractStage.NEGOTIATION,
        LifecycleEvent.NEGOTIATION_ABANDONED,
        ContractStage.CANCELLED,
        validator=_require_fields("reason"),
        activity_event=LifecycleEvent.CONTRACT_CANCELLED,
    ),
    _rule(
        ContractStage.NEGOTIATION,
        LifecycleEvent.CONTRACT_CANCELLED,
        ContractStage.CANCELLED,
        validator=_require_fields("reason"),
    ),
    _rule(
        ContractStage.INTERNAL_REVIEW,
        LifecycleEvent.APPROVAL_STARTED,
        ContractStage.INTERNAL_REVIEW,
    ),
    _rule(
        ContractStage.INTERNAL_REVIEW,
        LifecycleEvent.APPROVAL_STEP_APPROVED,
        ContractStage.INTERNAL_REVIEW,
    ),
    _rule(
        ContractStage.INTERNAL_REVIEW,
        LifecycleEvent.APPROVAL_COMPLETED,
        ContractStage.READY_TO_SIGN,
        validator=_validate_approval_complete,
        activity_event=LifecycleEvent.CONTRACT_READY_TO_SIGN,
    ),
    _rule(
        ContractStage.INTERNAL_REVIEW,
        LifecycleEvent.APPROVAL_CHANGES_REQUESTED,
        ContractStage.NEGOTIATION,
        validator=_require_fields("comment"),
        activity_event=LifecycleEvent.CONTRACT_ENTERED_NEGOTIATION,
    ),
    _rule(
        ContractStage.INTERNAL_REVIEW,
        LifecycleEvent.APPROVAL_REJECTED,
        ContractStage.REJECTED,
        validator=_require_fields("comment"),
        activity_event=LifecycleEvent.CONTRACT_REJECTED,
    ),
    _rule(
        ContractStage.INTERNAL_REVIEW,
        LifecycleEvent.APPROVAL_CANCELLED,
        ContractStage.INTERNAL_REVIEW,
    ),
    _rule(
        ContractStage.INTERNAL_REVIEW,
        LifecycleEvent.CONTRACT_CANCELLED,
        ContractStage.CANCELLED,
        validator=_require_fields("reason"),
    ),
    _rule(
        ContractStage.READY_TO_SIGN,
        LifecycleEvent.SIGNATURE_REQUEST_CREATED,
        ContractStage.READY_TO_SIGN,
    ),
    _rule(
        ContractStage.READY_TO_SIGN,
        LifecycleEvent.SIGNATURE_SENT,
        ContractStage.READY_TO_SIGN,
    ),
    _rule(
        ContractStage.READY_TO_SIGN,
        LifecycleEvent.SIGNATURE_VIEWED,
        ContractStage.READY_TO_SIGN,
    ),
    _rule(
        ContractStage.READY_TO_SIGN,
        LifecycleEvent.SIGNATURE_PARTIALLY_SIGNED,
        ContractStage.PARTIALLY_SIGNED,
        activity_event=LifecycleEvent.CONTRACT_PARTIALLY_SIGNED,
    ),
    _rule(
        ContractStage.READY_TO_SIGN,
        LifecycleEvent.SIGNATURE_COMPLETED,
        ContractStage.SIGNED,
        validator=_validate_signature_complete,
        activity_event=LifecycleEvent.CONTRACT_SIGNED,
    ),
    _rule(
        ContractStage.READY_TO_SIGN,
        LifecycleEvent.CONTRACT_SIGNED,
        ContractStage.SIGNED,
        validator=_validate_signature_complete,
    ),
    _rule(
        ContractStage.READY_TO_SIGN,
        LifecycleEvent.SIGNATURE_EXPIRED,
        ContractStage.READY_TO_SIGN,
    ),
    _rule(
        ContractStage.READY_TO_SIGN,
        LifecycleEvent.SIGNATURE_CANCELLED,
        ContractStage.READY_TO_SIGN,
    ),
    _rule(
        ContractStage.READY_TO_SIGN,
        LifecycleEvent.SIGNATURE_FAILED,
        ContractStage.READY_TO_SIGN,
    ),
    _rule(
        ContractStage.READY_TO_SIGN,
        LifecycleEvent.SIGNATURE_DECLINED,
        ContractStage.INTERNAL_REVIEW,
        activity_event=LifecycleEvent.CONTRACT_ENTERED_INTERNAL_REVIEW,
    ),
    _rule(
        ContractStage.READY_TO_SIGN,
        LifecycleEvent.CONTRACT_CANCELLED,
        ContractStage.CANCELLED,
        validator=_require_fields("reason"),
    ),
    _rule(
        ContractStage.PARTIALLY_SIGNED,
        LifecycleEvent.SIGNATURE_PARTIALLY_SIGNED,
        ContractStage.PARTIALLY_SIGNED,
    ),
    _rule(
        ContractStage.PARTIALLY_SIGNED,
        LifecycleEvent.SIGNATURE_COMPLETED,
        ContractStage.SIGNED,
        validator=_validate_signature_complete,
        activity_event=LifecycleEvent.CONTRACT_SIGNED,
    ),
    _rule(
        ContractStage.PARTIALLY_SIGNED,
        LifecycleEvent.CONTRACT_SIGNED,
        ContractStage.SIGNED,
        validator=_validate_signature_complete,
    ),
    _rule(
        ContractStage.PARTIALLY_SIGNED,
        LifecycleEvent.SIGNATURE_EXPIRED,
        ContractStage.READY_TO_SIGN,
    ),
    _rule(
        ContractStage.PARTIALLY_SIGNED,
        LifecycleEvent.SIGNATURE_CANCELLED,
        ContractStage.READY_TO_SIGN,
    ),
    _rule(
        ContractStage.PARTIALLY_SIGNED,
        LifecycleEvent.SIGNATURE_FAILED,
        ContractStage.READY_TO_SIGN,
    ),
    _rule(
        ContractStage.PARTIALLY_SIGNED,
        LifecycleEvent.SIGNATURE_DECLINED,
        ContractStage.INTERNAL_REVIEW,
        validator=_require_fields("reason"),
        activity_event=LifecycleEvent.CONTRACT_ENTERED_INTERNAL_REVIEW,
    ),
    _rule(
        ContractStage.SIGNED,
        LifecycleEvent.CONTRACT_ACTIVATED,
        ContractStage.ACTIVE,
        validator=_validate_activation,
    ),
    _rule(
        ContractStage.SIGNED,
        LifecycleEvent.LEGAL_VOIDED,
        ContractStage.CANCELLED,
        validator=_validate_legal_void,
        activity_event=LifecycleEvent.CONTRACT_CANCELLED,
    ),
    _rule(
        ContractStage.ACTIVE,
        LifecycleEvent.CONTRACT_COMPLETED,
        ContractStage.COMPLETED,
        validator=_validate_closeout,
    ),
    _rule(
        ContractStage.ACTIVE,
        LifecycleEvent.CONTRACT_TERMINATED,
        ContractStage.TERMINATED,
        validator=_require_fields("reason", "effective_date", "evidence"),
    ),
    _rule(
        ContractStage.ACTIVE,
        LifecycleEvent.AMENDMENT_STARTED,
        ContractStage.ACTIVE,
        validator=_validate_amendment,
    ),
)

_transition_table = {
    (rule.current_stage, rule.event): rule for rule in _TRANSITION_RULES
}
if len(_transition_table) != len(_TRANSITION_RULES):
    raise RuntimeError("duplicate_lifecycle_transition")
_TRANSITION_TABLE: Mapping[tuple[ContractStage, LifecycleEvent], TransitionRule] = (
    MappingProxyType(_transition_table)
)


class LifecycleService:
    @staticmethod
    def is_terminal(stage: ContractStage | LegacyContractStage | str) -> bool:
        return normalize_stage(stage) in TERMINAL_STAGES

    @staticmethod
    def is_active(stage: ContractStage | LegacyContractStage | str) -> bool:
        return normalize_stage(stage) == ContractStage.ACTIVE

    @staticmethod
    def list_allowed_events(stage: ContractStage | LegacyContractStage | str) -> tuple[LifecycleEvent, ...]:
        current = normalize_stage(stage)
        return tuple(rule.event for rule in _TRANSITION_RULES if rule.current_stage == current)

    @staticmethod
    def validate_transition(
        stage: ContractStage | LegacyContractStage | str,
        event: LifecycleEvent | str,
        *,
        actor: Any,
        metadata: Mapping[str, Any] | None = None,
    ) -> TransitionRule:
        current = normalize_stage(stage)
        try:
            lifecycle_event = event if isinstance(event, LifecycleEvent) else LifecycleEvent(event)
        except (TypeError, ValueError):
            _error(422, "invalid_transition_payload", field="event")

        details = _metadata_value(metadata)
        if details.get("workflow_stale") is True or details.get("current_version") is False:
            _error(409, "workflow_stale")
        if current in TERMINAL_STAGES:
            _error(409, "terminal_contract", current_stage=current.value, event=lifecycle_event.value)

        rule = _TRANSITION_TABLE.get((current, lifecycle_event))
        if rule is None:
            next_stages: list[str] = []
            for candidate in _TRANSITION_RULES:
                if candidate.current_stage != current or candidate.next_stage == current:
                    continue
                if candidate.next_stage.value not in next_stages:
                    next_stages.append(candidate.next_stage.value)
            _error(
                409,
                "invalid_stage_transition",
                current_stage=current.value,
                event=lifecycle_event.value,
                allowed_next_stages=next_stages,
            )
        rule.validator(actor, details)
        return rule

    @classmethod
    def can_transition(
        cls,
        stage: ContractStage | LegacyContractStage | str,
        event: LifecycleEvent | str,
        *,
        actor: Any,
        metadata: Mapping[str, Any] | None = None,
    ) -> bool:
        try:
            cls.validate_transition(stage, event, actor=actor, metadata=metadata)
        except LifecycleError:
            return False
        return True

    @classmethod
    def next_stage(
        cls,
        stage: ContractStage | LegacyContractStage | str,
        event: LifecycleEvent | str,
        *,
        actor: Any,
        metadata: Mapping[str, Any] | None = None,
    ) -> ContractStage:
        return cls.validate_transition(stage, event, actor=actor, metadata=metadata).next_stage

    @classmethod
    def transition(
        cls,
        contract: Contract,
        event: LifecycleEvent | str,
        actor: Any,
        metadata: Mapping[str, Any] | None = None,
    ) -> TransitionResult:
        details = _metadata_value(metadata)
        previous_stage = normalize_stage(contract.stage)
        rule = cls.validate_transition(previous_stage, event, actor=actor, metadata=details)
        contract.stage = rule.next_stage.value
        activity_metadata = {
            **details,
            "from": previous_stage.value,
            "to": rule.next_stage.value,
            "event": rule.event.value,
            "actor": _actor_value(actor),
        }
        return TransitionResult(
            previous_stage=previous_stage,
            next_stage=rule.next_stage,
            event=rule.event,
            activity_event=rule.activity_event,
            activity_metadata=activity_metadata,
        )


# Legacy workflow compatibility. These APIs intentionally preserve their current
# transaction behavior until Review/Approval/Signature integration phases.
ALLOWED_STAGES = frozenset(
    {stage.value for stage in ContractStage} | {stage.value for stage in LegacyContractStage}
)
APPROVAL_START_STAGES = frozenset(
    {ContractStage.NEGOTIATION.value, ContractStage.INTERNAL_REVIEW.value}
)
SIGNATURE_CREATE_STAGE = LegacyContractStage.APPROVED.value
SIGNATURE_CREATE_STAGES = frozenset(
    {LegacyContractStage.APPROVED.value, ContractStage.READY_TO_SIGN.value}
)
DECLINE_REVERT_STAGE = ContractStage.NEGOTIATION.value


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
    return (contract.stage or ContractStage.NEGOTIATION.value) in APPROVAL_START_STAGES


def can_create_signature(contract: Contract | None) -> bool:
    if contract is None:
        return False
    return (contract.stage or ContractStage.NEGOTIATION.value) in SIGNATURE_CREATE_STAGES


def transition_stage(contract: Contract, stage: str, db: Session) -> Contract:
    """Alias used by signature service — same rules as set_stage."""
    return set_stage(contract, stage, db)
