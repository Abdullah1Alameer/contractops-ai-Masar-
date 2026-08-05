from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.lifecycle import (
    ContractStage,
    LegacyContractStage,
    LifecycleError,
    LifecycleEvent,
    LifecycleService,
    normalize_stage,
)


def _contract(stage: ContractStage | LegacyContractStage | str):
    value = stage.value if hasattr(stage, "value") else stage
    return SimpleNamespace(id="contract-1", stage=value)


@pytest.mark.parametrize(
    ("current", "event", "expected", "metadata"),
    [
        (ContractStage.DRAFT, LifecycleEvent.CONTRACT_READY_FOR_CLIENT, ContractStage.READY_FOR_CLIENT, {}),
        (ContractStage.READY_FOR_CLIENT, LifecycleEvent.REVIEW_SENT, ContractStage.CLIENT_REVIEW, {}),
        (ContractStage.CLIENT_REVIEW, LifecycleEvent.REVIEW_APPROVED, ContractStage.INTERNAL_REVIEW, {}),
        (ContractStage.CLIENT_REVIEW, LifecycleEvent.REVIEW_CHANGES_REQUESTED, ContractStage.NEGOTIATION, {}),
        (
            ContractStage.NEGOTIATION,
            LifecycleEvent.NEGOTIATION_ACCEPTED,
            ContractStage.INTERNAL_REVIEW,
            {"negotiations_resolved": True},
        ),
        (ContractStage.INTERNAL_REVIEW, LifecycleEvent.APPROVAL_STARTED, ContractStage.INTERNAL_REVIEW, {}),
        (
            ContractStage.INTERNAL_REVIEW,
            LifecycleEvent.APPROVAL_COMPLETED,
            ContractStage.READY_TO_SIGN,
            {"approval_complete": True},
        ),
        (
            ContractStage.READY_TO_SIGN,
            LifecycleEvent.SIGNATURE_PARTIALLY_SIGNED,
            ContractStage.PARTIALLY_SIGNED,
            {},
        ),
        (
            ContractStage.PARTIALLY_SIGNED,
            LifecycleEvent.SIGNATURE_COMPLETED,
            ContractStage.SIGNED,
            {"signature_complete": True},
        ),
        (
            ContractStage.SIGNED,
            LifecycleEvent.CONTRACT_ACTIVATED,
            ContractStage.ACTIVE,
            {"activation_ready": True},
        ),
        (
            ContractStage.ACTIVE,
            LifecycleEvent.CONTRACT_COMPLETED,
            ContractStage.COMPLETED,
            {"closeout_complete": True},
        ),
        (
            ContractStage.ACTIVE,
            LifecycleEvent.CONTRACT_TERMINATED,
            ContractStage.TERMINATED,
            {"reason": "termination right", "effective_date": "2026-08-05", "evidence": "notice-1"},
        ),
    ],
)
def test_valid_transitions(current, event, expected, metadata):
    contract = _contract(current)

    result = LifecycleService.transition(contract, event, actor="tester", metadata=metadata)

    assert result.previous_stage == current
    assert result.next_stage == expected
    assert contract.stage == expected.value
    assert result.activity_metadata["from"] == current.value
    assert result.activity_metadata["to"] == expected.value
    assert result.activity_metadata["event"] == event.value


def test_invalid_transition_has_deterministic_conflict_payload():
    contract = _contract(ContractStage.DRAFT)

    with pytest.raises(LifecycleError) as raised:
        LifecycleService.transition(
            contract,
            LifecycleEvent.SIGNATURE_COMPLETED,
            actor="tester",
            metadata={"signature_complete": True},
        )

    assert raised.value.status_code == 409
    assert raised.value.code == "invalid_stage_transition"
    assert raised.value.payload == {
        "error": "invalid_stage_transition",
        "current_stage": "draft",
        "event": "signature_completed",
        "allowed_next_stages": ["ready_for_client", "cancelled"],
    }
    assert contract.stage == "draft"


@pytest.mark.parametrize(
    ("stage", "terminal"),
    [
        (ContractStage.DRAFT, False),
        (ContractStage.ACTIVE, False),
        (ContractStage.COMPLETED, True),
        (ContractStage.REJECTED, True),
        (ContractStage.CANCELLED, True),
        (ContractStage.TERMINATED, True),
    ],
)
def test_terminal_helper(stage, terminal):
    assert LifecycleService.is_terminal(stage) is terminal


def test_active_helper_only_matches_active_stage():
    assert LifecycleService.is_active(ContractStage.ACTIVE)
    assert not LifecycleService.is_active(ContractStage.SIGNED)
    assert not LifecycleService.is_active(ContractStage.COMPLETED)


def test_allowed_events_are_structural_and_terminal_stages_have_none():
    allowed = LifecycleService.list_allowed_events(ContractStage.CLIENT_REVIEW)

    assert LifecycleEvent.REVIEW_OPENED in allowed
    assert LifecycleEvent.REVIEW_APPROVED in allowed
    assert LifecycleEvent.REVIEW_REJECTED in allowed
    assert LifecycleService.list_allowed_events(ContractStage.COMPLETED) == ()


def test_terminal_transition_has_deterministic_error():
    with pytest.raises(LifecycleError) as raised:
        LifecycleService.validate_transition(
            ContractStage.REJECTED,
            LifecycleEvent.NEGOTIATION_STARTED,
            actor="tester",
        )

    assert raised.value.status_code == 409
    assert raised.value.payload == {
        "error": "terminal_contract",
        "current_stage": "rejected",
        "event": "negotiation_started",
    }


def test_can_transition_and_next_stage_do_not_mutate_contract():
    contract = _contract(ContractStage.READY_FOR_CLIENT)

    assert LifecycleService.can_transition(
        ContractStage.READY_FOR_CLIENT,
        LifecycleEvent.REVIEW_SENT,
        actor="tester",
    )
    assert not LifecycleService.can_transition(
        ContractStage.READY_FOR_CLIENT,
        LifecycleEvent.SIGNATURE_SENT,
        actor="tester",
    )
    assert (
        LifecycleService.next_stage(
            ContractStage.READY_FOR_CLIENT,
            LifecycleEvent.REVIEW_SENT,
            actor="tester",
        )
        == ContractStage.CLIENT_REVIEW
    )
    assert contract.stage == ContractStage.READY_FOR_CLIENT.value


def test_missing_actor_is_forbidden():
    with pytest.raises(LifecycleError) as raised:
        LifecycleService.validate_transition(
            ContractStage.READY_FOR_CLIENT,
            LifecycleEvent.REVIEW_SENT,
            actor=None,
        )

    assert raised.value.status_code == 403
    assert raised.value.code == "forbidden_transition"


def test_missing_required_reason_is_invalid_payload():
    with pytest.raises(LifecycleError) as raised:
        LifecycleService.validate_transition(
            ContractStage.DRAFT,
            LifecycleEvent.CONTRACT_CANCELLED,
            actor="tester",
            metadata={},
        )

    assert raised.value.status_code == 422
    assert raised.value.code == "invalid_transition_payload"
    assert raised.value.payload["missing_fields"] == ["reason"]


def test_stale_workflow_is_rejected():
    with pytest.raises(LifecycleError) as raised:
        LifecycleService.validate_transition(
            ContractStage.READY_FOR_CLIENT,
            LifecycleEvent.REVIEW_SENT,
            actor="tester",
            metadata={"workflow_stale": True},
        )

    assert raised.value.status_code == 409
    assert raised.value.code == "workflow_stale"


def test_unresolved_negotiations_are_rejected():
    with pytest.raises(LifecycleError) as raised:
        LifecycleService.validate_transition(
            ContractStage.NEGOTIATION,
            LifecycleEvent.NEGOTIATION_ACCEPTED,
            actor="tester",
            metadata={"negotiations_resolved": False},
        )

    assert raised.value.status_code == 409
    assert raised.value.code == "unresolved_negotiations"


def test_incomplete_approval_is_rejected():
    with pytest.raises(LifecycleError) as raised:
        LifecycleService.validate_transition(
            ContractStage.INTERNAL_REVIEW,
            LifecycleEvent.APPROVAL_COMPLETED,
            actor="tester",
            metadata={"approval_complete": False},
        )

    assert raised.value.status_code == 409
    assert raised.value.code == "approval_not_complete"


@pytest.mark.parametrize(
    ("legacy", "canonical"),
    [
        (LegacyContractStage.APPROVED, ContractStage.READY_TO_SIGN),
        (LegacyContractStage.AWAITING_SIGNATURE, ContractStage.READY_TO_SIGN),
    ],
)
def test_temporary_legacy_stage_mapping(legacy, canonical):
    assert normalize_stage(legacy) == canonical
    assert normalize_stage(legacy.value) == canonical


def test_transition_does_not_commit_a_transaction():
    session = MagicMock()
    contract = _contract(ContractStage.DRAFT)
    contract.session = session

    LifecycleService.transition(
        contract,
        LifecycleEvent.CONTRACT_READY_FOR_CLIENT,
        actor="tester",
    )

    session.commit.assert_not_called()


def test_transition_metadata_is_copied_and_not_mutated():
    metadata = {"request_id": "review-1"}
    result = LifecycleService.transition(
        _contract(ContractStage.READY_FOR_CLIENT),
        LifecycleEvent.REVIEW_SENT,
        actor="tester",
        metadata=metadata,
    )

    assert metadata == {"request_id": "review-1"}
    assert result.activity_metadata["request_id"] == "review-1"
    assert result.activity_metadata["actor"] == "tester"
    assert result.activity_event == LifecycleEvent.CONTRACT_ENTERED_CLIENT_REVIEW


def test_malformed_metadata_has_deterministic_payload_error():
    with pytest.raises(LifecycleError) as raised:
        LifecycleService.validate_transition(
            ContractStage.DRAFT,
            LifecycleEvent.CONTRACT_READY_FOR_CLIENT,
            actor="tester",
            metadata=["not", "a", "mapping"],  # type: ignore[arg-type]
        )

    assert raised.value.status_code == 422
    assert raised.value.payload == {
        "error": "invalid_transition_payload",
        "field": "metadata",
    }
