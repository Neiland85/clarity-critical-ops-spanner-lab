from concurrent.futures import ThreadPoolExecutor

import pytest

from app.idempotency import (
    IdempotencyDecision,
    IdempotencyStatus,
    InMemoryIdempotencyRegistry,
    stable_request_hash,
)


def test_stable_request_hash_ignores_key_order() -> None:
    left = {"amount": 100, "currency": "EUR", "account": "A"}
    right = {"currency": "EUR", "account": "A", "amount": 100}

    assert stable_request_hash(left) == stable_request_hash(right)


def test_stable_request_hash_changes_when_payload_changes() -> None:
    left = {"amount": 100, "currency": "EUR"}
    right = {"amount": 101, "currency": "EUR"}

    assert stable_request_hash(left) != stable_request_hash(right)


def test_start_creates_pending_record() -> None:
    registry = InMemoryIdempotencyRegistry()
    request_hash = stable_request_hash({"amount": 100})

    result = registry.start(
        idempotency_key="key-1",
        operation_type="transfer",
        request_hash=request_hash,
    )

    assert result.decision == IdempotencyDecision.CREATED
    assert result.status == IdempotencyStatus.PENDING
    assert len(registry) == 1


def test_duplicate_pending_request_is_not_recreated() -> None:
    registry = InMemoryIdempotencyRegistry()
    request_hash = stable_request_hash({"amount": 100})

    first = registry.start(
        idempotency_key="key-1",
        operation_type="transfer",
        request_hash=request_hash,
    )
    second = registry.start(
        idempotency_key="key-1",
        operation_type="transfer",
        request_hash=request_hash,
    )

    assert first.decision == IdempotencyDecision.CREATED
    assert second.decision == IdempotencyDecision.PENDING
    assert len(registry) == 1


def test_same_key_different_payload_is_rejected() -> None:
    registry = InMemoryIdempotencyRegistry()

    registry.start(
        idempotency_key="key-1",
        operation_type="transfer",
        request_hash=stable_request_hash({"amount": 100}),
    )

    result = registry.start(
        idempotency_key="key-1",
        operation_type="transfer",
        request_hash=stable_request_hash({"amount": 200}),
    )

    assert result.decision == IdempotencyDecision.CONFLICT
    assert len(registry) == 1


def test_completed_request_replays_original_response() -> None:
    registry = InMemoryIdempotencyRegistry()
    request_hash = stable_request_hash({"amount": 100})

    registry.start(
        idempotency_key="key-1",
        operation_type="transfer",
        request_hash=request_hash,
    )
    registry.complete(
        idempotency_key="key-1",
        response_payload={"transfer_id": "tx-1", "status": "accepted"},
    )

    result = registry.start(
        idempotency_key="key-1",
        operation_type="transfer",
        request_hash=request_hash,
    )

    assert result.decision == IdempotencyDecision.REPLAY
    assert result.status == IdempotencyStatus.COMPLETED
    assert result.response_payload == {"transfer_id": "tx-1", "status": "accepted"}


def test_failed_request_returns_failed_decision() -> None:
    registry = InMemoryIdempotencyRegistry()
    request_hash = stable_request_hash({"amount": 100})

    registry.start(
        idempotency_key="key-1",
        operation_type="transfer",
        request_hash=request_hash,
    )
    registry.fail(
        idempotency_key="key-1",
        error_payload={"code": "INSUFFICIENT_FUNDS"},
    )

    result = registry.start(
        idempotency_key="key-1",
        operation_type="transfer",
        request_hash=request_hash,
    )

    assert result.decision == IdempotencyDecision.FAILED
    assert result.status == IdempotencyStatus.FAILED
    assert result.error_payload == {"code": "INSUFFICIENT_FUNDS"}


def test_concurrent_duplicates_create_single_pending_record() -> None:
    registry = InMemoryIdempotencyRegistry()
    request_hash = stable_request_hash({"amount": 100})

    def start_once() -> IdempotencyDecision:
        return registry.start(
            idempotency_key="key-1",
            operation_type="transfer",
            request_hash=request_hash,
        ).decision

    with ThreadPoolExecutor(max_workers=16) as executor:
        decisions = list(executor.map(lambda _: start_once(), range(64)))

    assert decisions.count(IdempotencyDecision.CREATED) == 1
    assert decisions.count(IdempotencyDecision.PENDING) == 63
    assert len(registry) == 1


def test_empty_inputs_are_rejected() -> None:
    registry = InMemoryIdempotencyRegistry()

    with pytest.raises(ValueError):
        registry.start(
            idempotency_key="",
            operation_type="transfer",
            request_hash="hash",
        )
