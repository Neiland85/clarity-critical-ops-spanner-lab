from dataclasses import FrozenInstanceError
from datetime import datetime
import pytest

from app.idempotency import (
    IdempotencyDecision,
    IdempotencyStatus,
    InMemoryIdempotencyRegistry,
    stable_request_hash,
)
from app.idempotency.value_semantics import (
    FrozenPayload,
    freeze_payload,
    thaw_payload,
)

SCOPE = "tenant-001"
KEY = "operation-001"
OPERATION = "transfer.create"
REQUEST_HASH = stable_request_hash({"amount": 100})


def _completed_registry():
    registry = InMemoryIdempotencyRegistry()
    created = registry.start(
        idempotency_scope=SCOPE,
        idempotency_key=KEY,
        operation_type=OPERATION,
        request_hash=REQUEST_HASH,
    )
    assert created.lease_token is not None

    payload = {"result": {"transfer_id": "tx-001"}}
    completed = registry.complete(
        idempotency_scope=SCOPE,
        idempotency_key=KEY,
        lease_token=created.lease_token,
        response_payload=payload,
    )
    return registry, completed, payload


def test_returned_record_is_an_immutable_detached_snapshot() -> None:
    registry, completed, _ = _completed_registry()

    with pytest.raises(FrozenInstanceError):
        completed.status = IdempotencyStatus.FAILED

    current = registry.get(KEY, idempotency_scope=SCOPE)

    assert current is not None
    assert current is not completed
    assert current.status == IdempotencyStatus.COMPLETED


def test_input_payload_cannot_mutate_authoritative_state() -> None:
    registry, _, payload = _completed_registry()

    payload["result"]["transfer_id"] = "tampered"

    current = registry.get(KEY, idempotency_scope=SCOPE)

    assert current is not None
    assert current.response_payload == {"result": {"transfer_id": "tx-001"}}


def test_returned_payload_is_deeply_immutable() -> None:
    registry, _, _ = _completed_registry()
    replay = registry.start(
        idempotency_scope=SCOPE,
        idempotency_key=KEY,
        operation_type=OPERATION,
        request_hash=REQUEST_HASH,
    )

    assert replay.response_payload is not None

    with pytest.raises(TypeError):
        replay.response_payload["result"]["transfer_id"] = "tampered"


def test_conflict_never_exposes_existing_payloads() -> None:
    registry, _, _ = _completed_registry()
    conflict = registry.start(
        idempotency_scope=SCOPE,
        idempotency_key=KEY,
        operation_type=OPERATION,
        request_hash=stable_request_hash({"amount": 999}),
    )

    assert conflict.decision == IdempotencyDecision.CONFLICT
    assert conflict.response_payload is None
    assert conflict.error_payload is None


def test_scope_is_mandatory() -> None:
    registry = InMemoryIdempotencyRegistry()
    with pytest.raises(TypeError):
        # El contrato exige el scope de forma mandatoria sin defaults globales
        registry.start(idempotency_key=KEY, operation_type=OPERATION, request_hash=REQUEST_HASH)
