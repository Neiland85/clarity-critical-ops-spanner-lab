from __future__ import annotations

from collections.abc import Callable
from typing import cast

import pytest

from app.idempotency import (
    IdempotencyDecision,
    IdempotencyRegistry,
    IdempotencyStatus,
    InMemoryIdempotencyRegistry,
    RegistryResult,
    stable_request_hash,
)

RegistryFactory = Callable[[], IdempotencyRegistry]

REGISTRY_FACTORIES = (
    pytest.param(InMemoryIdempotencyRegistry, id="in-memory"),
)


@pytest.fixture(params=REGISTRY_FACTORIES)
def registry(request: pytest.FixtureRequest) -> IdempotencyRegistry:
    factory = cast(RegistryFactory, request.param)
    instance = factory()
    assert isinstance(instance, IdempotencyRegistry)
    return instance


def start_operation(
    registry: IdempotencyRegistry,
    *,
    scope: str = "tenant-a",
    key: str = "operation-1",
    amount: int = 100,
) -> RegistryResult:
    return registry.start(
        idempotency_scope=scope,
        idempotency_key=key,
        operation_type="transfer.create",
        request_hash=stable_request_hash({"amount": amount, "currency": "EUR"}),
    )


def required_lease_token(result: RegistryResult) -> str:
    assert result.lease_token is not None
    return result.lease_token


def test_registry_implements_provider_neutral_port(
    registry: IdempotencyRegistry,
) -> None:
    assert isinstance(registry, IdempotencyRegistry)


def test_first_request_acquires_and_duplicate_observes_pending(
    registry: IdempotencyRegistry,
) -> None:
    first = start_operation(registry)
    duplicate = start_operation(registry)

    assert first.decision == IdempotencyDecision.CREATED
    assert first.status == IdempotencyStatus.PENDING
    assert first.lease_token is not None
    assert duplicate.decision == IdempotencyDecision.PENDING
    assert duplicate.status == IdempotencyStatus.PENDING
    assert duplicate.lease_token is None


def test_same_identity_with_different_payload_conflicts(
    registry: IdempotencyRegistry,
) -> None:
    start_operation(registry, amount=100)
    conflict = start_operation(registry, amount=200)

    assert conflict.decision == IdempotencyDecision.CONFLICT


def test_completed_operation_replays_original_response(
    registry: IdempotencyRegistry,
) -> None:
    acquired = start_operation(registry)
    registry.complete(
        idempotency_scope="tenant-a",
        idempotency_key="operation-1",
        lease_token=required_lease_token(acquired),
        response_payload={"transfer_id": "tx-1"},
    )

    replay = start_operation(registry)

    assert replay.decision == IdempotencyDecision.REPLAY
    assert replay.status == IdempotencyStatus.COMPLETED
    assert replay.response_payload == {"transfer_id": "tx-1"}


def test_failed_operation_returns_terminal_failure(
    registry: IdempotencyRegistry,
) -> None:
    acquired = start_operation(registry)
    registry.fail(
        idempotency_scope="tenant-a",
        idempotency_key="operation-1",
        lease_token=required_lease_token(acquired),
        error_payload={"code": "REJECTED"},
    )

    failed = start_operation(registry)

    assert failed.decision == IdempotencyDecision.FAILED
    assert failed.status == IdempotencyStatus.FAILED
    assert failed.error_payload == {"code": "REJECTED"}


def test_same_key_is_isolated_between_scopes(
    registry: IdempotencyRegistry,
) -> None:
    tenant_a = start_operation(registry, scope="tenant-a", key="shared-key")
    tenant_b = start_operation(registry, scope="tenant-b", key="shared-key")

    assert tenant_a.decision == IdempotencyDecision.CREATED
    assert tenant_b.decision == IdempotencyDecision.CREATED
    assert registry.get("shared-key", idempotency_scope="tenant-a") is not None
    assert registry.get("shared-key", idempotency_scope="tenant-b") is not None


def test_unknown_identity_returns_no_record(
    registry: IdempotencyRegistry,
) -> None:
    assert registry.get("unknown", idempotency_scope="tenant-a") is None
