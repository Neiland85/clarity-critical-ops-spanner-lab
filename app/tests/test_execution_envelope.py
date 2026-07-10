from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.execution import (
    ExecutionEnvelope,
    ReplayPolicy,
    stable_request_hash,
)


def build_envelope(**overrides) -> ExecutionEnvelope:
    values = {
        "idempotency_key": "idem-transfer-001",
        "operation_type": "transfer.create",
        "payload": {
            "amount": 100,
            "currency": "EUR",
            "beneficiary": {"account": "ES00"},
        },
        "actor_id": "user-001",
        "tenant_id": "tenant-001",
        "security_context": {
            "roles": ["operator"],
            "authentication_level": "strong",
        },
    }
    values.update(overrides)

    return ExecutionEnvelope.create(**values)


def test_create_builds_versioned_execution_envelope() -> None:
    envelope = build_envelope()

    assert envelope.schema_version == "1.0"
    assert isinstance(envelope.operation_id, UUID)
    assert isinstance(envelope.correlation_id, UUID)
    assert envelope.issued_at.tzinfo == UTC
    assert envelope.replay_policy == ReplayPolicy.RETURN_STORED_RESPONSE
    assert envelope.request_hash == stable_request_hash(envelope.payload)


def test_envelope_generates_registry_input() -> None:
    envelope = build_envelope()

    assert envelope.idempotency_start_input() == {
        "idempotency_scope": "tenant-001",
        "idempotency_key": "idem-transfer-001",
        "operation_type": "transfer.create",
        "request_hash": envelope.request_hash,
    }


def test_payload_and_security_context_are_deeply_immutable() -> None:
    payload = {
        "amount": 100,
        "metadata": {"tags": ["priority"]},
    }
    security_context = {
        "roles": ["operator"],
    }

    envelope = build_envelope(
        payload=payload,
        security_context=security_context,
    )

    payload["metadata"]["tags"].append("mutated")
    security_context["roles"].append("admin")

    assert envelope.payload_copy() == {
        "amount": 100,
        "metadata": {"tags": ["priority"]},
    }
    assert envelope.security_context_copy() == {
        "roles": ["operator"],
    }

    with pytest.raises(TypeError):
        envelope.payload["amount"] = 200

    with pytest.raises(TypeError):
        envelope.payload["metadata"]["tags"][0] = "mutated"


def test_serialized_envelope_round_trips_without_losing_contract_data() -> None:
    envelope = build_envelope()

    serialized = envelope.model_dump_json()
    restored = ExecutionEnvelope.model_validate_json(serialized)

    assert restored == envelope
    assert restored.payload_copy() == envelope.payload_copy()
    assert restored.security_context_copy() == envelope.security_context_copy()


def test_request_hash_mismatch_is_rejected() -> None:
    envelope = build_envelope()
    data = envelope.model_dump(mode="json")
    data["request_hash"] = "0" * 64

    with pytest.raises(ValidationError, match="request_hash does not match payload"):
        ExecutionEnvelope.model_validate(data)


def test_unknown_transport_specific_fields_are_rejected() -> None:
    envelope = build_envelope()
    data = envelope.model_dump(mode="json")
    data["transport"] = "websocket"

    with pytest.raises(ValidationError):
        ExecutionEnvelope.model_validate(data)


def test_naive_issued_at_is_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        build_envelope(issued_at=datetime(2026, 7, 10, 1, 0, 0))


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("idempotency_key", "key with spaces"),
        ("actor_id", "actor with spaces"),
        ("tenant_id", "tenant with spaces"),
        ("operation_type", "Transfer.Create"),
        ("operation_type", "transfer create"),
    ],
)
def test_invalid_contract_identifiers_are_rejected(
    field_name: str,
    value: str,
) -> None:
    with pytest.raises(ValidationError):
        build_envelope(**{field_name: value})


@pytest.mark.parametrize(
    "payload",
    [
        {"value": float("nan")},
        {"issued_at": datetime.now(UTC)},
        {1: "non-string-key"},
    ],
)
def test_non_json_payload_values_are_rejected(payload: dict) -> None:
    with pytest.raises(ValueError):
        build_envelope(payload=payload)


def test_causation_and_replay_policy_are_preserved() -> None:
    causation_id = uuid4()

    envelope = build_envelope(
        causation_id=causation_id,
        replay_policy=ReplayPolicy.RETURN_STATUS,
    )

    assert envelope.causation_id == causation_id
    assert envelope.replay_policy == ReplayPolicy.RETURN_STATUS


def test_default_security_context_is_immutable() -> None:
    payload = {"amount": 100}

    envelope = ExecutionEnvelope(
        idempotency_key="idem-default-context",
        operation_type="transfer.create",
        payload=payload,
        request_hash=stable_request_hash(payload),
        actor_id="user-001",
        tenant_id="tenant-001",
    )

    with pytest.raises(TypeError):
        envelope.security_context["role"] = "admin"


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("idempotency_key", " idem-key"),
        ("idempotency_key", "idem-key "),
        ("actor_id", " actor-001"),
        ("tenant_id", "tenant-001 "),
    ],
)
def test_identifier_whitespace_is_rejected_without_normalization(
    field_name: str,
    value: str,
) -> None:
    with pytest.raises(ValidationError):
        build_envelope(**{field_name: value})


def test_non_json_security_context_values_are_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported JSON value type"):
        build_envelope(
            security_context={
                "authenticated_at": datetime.now(UTC),
            }
        )
