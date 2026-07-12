from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from app.idempotency import (
    ExpiredExecutionLeaseError,
    IdempotencyDecision,
    IdempotencyStatus,
    InMemoryIdempotencyRegistry,
    InvalidIdempotencyTransitionError,
    RegistryResult,
    StaleExecutionLeaseError,
    stable_request_hash,
)


@dataclass
class MutableClock:
    current: datetime

    def __call__(self) -> datetime:
        return self.current

    def advance(self, delta: timedelta) -> None:
        self.current += delta


def create_registry(
    *,
    ttl: timedelta = timedelta(seconds=30),
) -> tuple[
    InMemoryIdempotencyRegistry,
    MutableClock,
]:
    clock = MutableClock(
        datetime(
            2026,
            7,
            10,
            0,
            0,
            tzinfo=UTC,
        )
    )
    registry = InMemoryIdempotencyRegistry(
        pending_ttl=ttl,
        clock=clock,
    )

    return registry, clock


def start_transfer(
    registry: InMemoryIdempotencyRegistry,
    *,
    idempotency_key: str = "key-1",
    idempotency_scope: str = "global",
    amount: int = 100,
) -> RegistryResult:
    return registry.start(
        idempotency_scope=idempotency_scope,
        idempotency_key=idempotency_key,
        operation_type="transfer.create",
        request_hash=stable_request_hash({"amount": amount}),
    )


def required_lease_token(
    result: RegistryResult,
) -> str:
    assert result.lease_token is not None
    return result.lease_token


def test_stable_request_hash_ignores_key_order() -> None:
    left = {
        "amount": 100,
        "currency": "EUR",
        "account": "A",
    }
    right = {
        "currency": "EUR",
        "account": "A",
        "amount": 100,
    }

    assert stable_request_hash(left) == stable_request_hash(right)


def test_stable_request_hash_changes_when_payload_changes() -> None:
    left = {
        "amount": 100,
        "currency": "EUR",
    }
    right = {
        "amount": 101,
        "currency": "EUR",
    }

    assert stable_request_hash(left) != stable_request_hash(right)


def test_start_creates_pending_record_with_execution_lease() -> None:
    registry, clock = create_registry()

    result = start_transfer(registry)

    assert result.decision == IdempotencyDecision.CREATED
    assert result.status == IdempotencyStatus.PENDING
    assert result.attempt == 1
    assert result.lease_token
    assert result.lease_expires_at == (clock.current + timedelta(seconds=30))
    assert len(registry) == 1


def test_duplicate_pending_request_does_not_receive_execution_lease() -> None:
    registry, _ = create_registry()

    first = start_transfer(registry)
    second = start_transfer(registry)

    assert first.decision == IdempotencyDecision.CREATED
    assert first.lease_token
    assert second.decision == IdempotencyDecision.PENDING
    assert second.attempt == 1
    assert second.lease_token is None
    assert len(registry) == 1


def test_same_key_different_payload_is_rejected() -> None:
    registry, _ = create_registry()

    start_transfer(
        registry,
        amount=100,
    )
    result = start_transfer(
        registry,
        amount=200,
    )

    assert result.decision == IdempotencyDecision.CONFLICT
    assert len(registry) == 1


def test_completed_request_replays_original_response() -> None:
    registry, _ = create_registry()
    created = start_transfer(registry)

    registry.complete(
        idempotency_scope="global",
        idempotency_key="key-1",
        lease_token=required_lease_token(created),
        response_payload={
            "transfer_id": "tx-1",
            "status": "accepted",
        },
    )

    result = start_transfer(registry)

    assert result.decision == IdempotencyDecision.REPLAY
    assert result.status == IdempotencyStatus.COMPLETED
    assert result.response_payload == {
        "transfer_id": "tx-1",
        "status": "accepted",
    }


def test_failed_request_returns_failed_decision() -> None:
    registry, _ = create_registry()
    created = start_transfer(registry)

    registry.fail(
        idempotency_scope="global",
        idempotency_key="key-1",
        lease_token=required_lease_token(created),
        error_payload={
            "code": "INSUFFICIENT_FUNDS",
        },
    )

    result = start_transfer(registry)

    assert result.decision == IdempotencyDecision.FAILED
    assert result.status == IdempotencyStatus.FAILED
    assert result.error_payload == {
        "code": "INSUFFICIENT_FUNDS",
    }


def test_concurrent_duplicates_create_single_pending_record() -> None:
    registry, _ = create_registry()

    def start_once() -> IdempotencyDecision:
        return start_transfer(registry).decision

    with ThreadPoolExecutor(max_workers=16) as executor:
        decisions = list(
            executor.map(
                lambda _: start_once(),
                range(64),
            )
        )

    assert decisions.count(IdempotencyDecision.CREATED) == 1
    assert decisions.count(IdempotencyDecision.PENDING) == 63
    assert len(registry) == 1


def test_empty_inputs_are_rejected() -> None:
    registry, _ = create_registry()

    with pytest.raises(ValueError):
        registry.start(
            idempotency_scope="global",
            idempotency_key="",
            operation_type="transfer.create",
            request_hash="hash",
        )


def test_same_key_is_isolated_between_idempotency_scopes() -> None:
    registry, _ = create_registry()

    tenant_a = start_transfer(
        registry,
        idempotency_scope="tenant-a",
        idempotency_key="shared-key",
    )
    tenant_b = start_transfer(
        registry,
        idempotency_scope="tenant-b",
        idempotency_key="shared-key",
    )

    registry.complete(
        idempotency_scope="tenant-a",
        idempotency_key="shared-key",
        lease_token=required_lease_token(tenant_a),
        response_payload={
            "transfer_id": "tx-a",
        },
    )

    record_a = registry.get(
        "shared-key",
        idempotency_scope="tenant-a",
    )
    record_b = registry.get(
        "shared-key",
        idempotency_scope="tenant-b",
    )

    assert tenant_a.decision == IdempotencyDecision.CREATED
    assert tenant_b.decision == IdempotencyDecision.CREATED
    assert record_a is not None
    assert record_b is not None
    assert record_a.status == IdempotencyStatus.COMPLETED
    assert record_b.status == IdempotencyStatus.PENDING
    assert len(registry) == 2


def test_expired_pending_operation_is_reacquired_with_new_lease() -> None:
    registry, clock = create_registry()
    first = start_transfer(registry)

    clock.advance(timedelta(seconds=30))
    second = start_transfer(registry)
    record = registry.get("key-1", idempotency_scope="global")

    assert second.decision == IdempotencyDecision.REACQUIRED
    assert second.status == IdempotencyStatus.PENDING
    assert second.attempt == 2
    assert second.lease_token
    assert second.lease_token != first.lease_token
    assert record is not None
    assert record.last_expired_at == clock.current
    assert record.attempt == 2


def test_stale_worker_cannot_complete_reacquired_operation() -> None:
    registry, clock = create_registry()
    first = start_transfer(registry)

    clock.advance(timedelta(seconds=30))
    second = start_transfer(registry)

    with pytest.raises(StaleExecutionLeaseError):
        registry.complete(
            idempotency_scope="global",
            idempotency_key="key-1",
            lease_token=required_lease_token(first),
            response_payload={
                "transfer_id": "stale",
            },
        )

    registry.complete(
        idempotency_scope="global",
        idempotency_key="key-1",
        lease_token=required_lease_token(second),
        response_payload={
            "transfer_id": "current",
        },
    )

    record = registry.get("key-1", idempotency_scope="global")

    assert record is not None
    assert record.response_payload == {
        "transfer_id": "current",
    }


def test_worker_cannot_complete_after_its_lease_expires() -> None:
    registry, clock = create_registry()
    created = start_transfer(registry)

    clock.advance(timedelta(seconds=30))

    with pytest.raises(ExpiredExecutionLeaseError):
        registry.complete(
            idempotency_scope="global",
            idempotency_key="key-1",
            lease_token=required_lease_token(created),
            response_payload={
                "transfer_id": "too-late",
            },
        )

    record = registry.get("key-1", idempotency_scope="global")

    assert record is not None
    assert record.status == IdempotencyStatus.EXPIRED
    assert record.last_expired_at == clock.current


def test_expire_pending_marks_due_operation_and_allows_reacquisition() -> None:
    registry, clock = create_registry()
    first = start_transfer(registry)

    assert registry.expire_pending("key-1", idempotency_scope="global") is False

    clock.advance(timedelta(seconds=30))

    assert registry.expire_pending("key-1", idempotency_scope="global") is True

    expired = registry.get("key-1", idempotency_scope="global")

    assert expired is not None
    assert expired.status == IdempotencyStatus.EXPIRED

    reacquired = start_transfer(registry)

    assert reacquired.decision == (IdempotencyDecision.REACQUIRED)
    assert reacquired.attempt == 2
    assert reacquired.lease_token != first.lease_token


def test_terminal_operation_cannot_be_completed_twice() -> None:
    registry, _ = create_registry()
    created = start_transfer(registry)
    lease_token = required_lease_token(created)

    registry.complete(
        idempotency_scope="global",
        idempotency_key="key-1",
        lease_token=lease_token,
        response_payload={
            "transfer_id": "tx-1",
        },
    )

    with pytest.raises(InvalidIdempotencyTransitionError):
        registry.complete(
            idempotency_scope="global",
            idempotency_key="key-1",
            lease_token=lease_token,
            response_payload={
                "transfer_id": "tx-2",
            },
        )


def test_completed_operation_is_not_reacquired_after_ttl() -> None:
    registry, clock = create_registry()
    created = start_transfer(registry)

    registry.complete(
        idempotency_scope="global",
        idempotency_key="key-1",
        lease_token=required_lease_token(created),
        response_payload={
            "transfer_id": "tx-1",
        },
    )

    clock.advance(timedelta(hours=1))
    result = start_transfer(registry)

    assert result.decision == IdempotencyDecision.REPLAY
    assert result.attempt == 1


def test_non_positive_pending_ttl_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        InMemoryIdempotencyRegistry(pending_ttl=timedelta(0))


def test_clock_must_return_timezone_aware_datetime() -> None:
    registry = InMemoryIdempotencyRegistry(
        clock=lambda: datetime(
            2026,
            7,
            10,
            0,
            0,
        )
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        start_transfer(registry)


def test_expire_pending_returns_false_for_unknown_operation() -> None:
    registry, _ = create_registry()

    assert (
        registry.expire_pending(
            "unknown-key",
            idempotency_scope="tenant-001",
        )
        is False
    )
