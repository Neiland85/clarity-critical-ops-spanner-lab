from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import Any, cast

import pytest

from app.idempotency import (
    ExpiredExecutionLeaseError,
    IdempotencyDecision,
    IdempotencyRegistry,
    IdempotencyStatus,
    InMemoryIdempotencyRegistry,
    RegistryResult,
    SpannerIdempotencyRegistry,
    StaleExecutionLeaseError,
    stable_request_hash,
)

RegistryFactory = Callable[[], IdempotencyRegistry]
_COLUMNS = (
    "IdempotencyScope",
    "IdempotencyKey",
    "OperationType",
    "RequestHash",
    "Status",
    "ResponsePayload",
    "ErrorPayload",
    "CreatedAt",
    "UpdatedAt",
    "LeaseToken",
    "LeaseExpiresAt",
    "Attempt",
    "CompletedAt",
    "FailedAt",
    "LastExpiredAt",
)


class MutableClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 7, 12, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


class FakeSpannerReader:
    def __init__(
        self,
        rows: dict[tuple[str, str], dict[str, Any]],
        clock: MutableClock,
    ) -> None:
        self._rows = rows
        self._clock = clock

    def execute_sql(
        self,
        sql: str,
        *,
        params: dict[str, Any] | None = None,
        param_types: dict[str, Any] | None = None,
    ) -> list[tuple[Any, ...]]:
        del param_types
        if "CURRENT_TIMESTAMP" in sql:
            return [(self._clock(),)]
        assert params is not None
        row = self._rows.get((params["scope"], params["key"]))
        return [] if row is None else [tuple(row[column] for column in _COLUMNS)]


class FakeSpannerTransaction(FakeSpannerReader):
    def insert(
        self,
        *,
        table: str,
        columns: tuple[str, ...],
        values: list[tuple[Any, ...]],
    ) -> None:
        assert table == "IdempotencyRecords"
        for values_row in values:
            row = dict(zip(columns, values_row, strict=True))
            key = (row["IdempotencyScope"], row["IdempotencyKey"])
            if key in self._rows:
                raise RuntimeError("duplicate primary key")
            self._rows[key] = row

    def update(
        self,
        *,
        table: str,
        columns: tuple[str, ...],
        values: list[tuple[Any, ...]],
    ) -> None:
        assert table == "IdempotencyRecords"
        for values_row in values:
            row = dict(zip(columns, values_row, strict=True))
            key = (row["IdempotencyScope"], row["IdempotencyKey"])
            if key not in self._rows:
                raise RuntimeError("missing primary key")
            self._rows[key] = row


class FakeSpannerSnapshot(FakeSpannerReader):
    def __enter__(self) -> FakeSpannerSnapshot:
        return self

    def __exit__(self, *_: object) -> None:
        return None


class FakeSpannerDatabase:
    def __init__(self, clock: MutableClock) -> None:
        self.clock = clock
        self.rows: dict[tuple[str, str], dict[str, Any]] = {}
        self._lock = RLock()

    def run_in_transaction(self, callback: Any) -> Any:
        with self._lock:
            return callback(FakeSpannerTransaction(self.rows, self.clock))

    def snapshot(self) -> FakeSpannerSnapshot:
        return FakeSpannerSnapshot(self.rows, self.clock)


def new_spanner_registry(
    *,
    clock: MutableClock | None = None,
) -> SpannerIdempotencyRegistry:
    effective_clock = clock or MutableClock()
    tokens = iter(("lease-1", "lease-2", "lease-3"))
    return SpannerIdempotencyRegistry(
        FakeSpannerDatabase(effective_clock),
        pending_ttl=timedelta(seconds=30),
        token_factory=lambda: next(tokens),
    )


REGISTRY_FACTORIES = (
    pytest.param(InMemoryIdempotencyRegistry, id="in-memory"),
    pytest.param(new_spanner_registry, id="spanner-fake"),
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


def test_spanner_expired_record_is_reacquired_with_new_fencing_token() -> None:
    clock = MutableClock()
    registry = new_spanner_registry(clock=clock)
    first = start_operation(registry)
    clock.advance(timedelta(seconds=30))

    reacquired = start_operation(registry)
    record = registry.get("operation-1", idempotency_scope="tenant-a")

    assert reacquired.decision == IdempotencyDecision.REACQUIRED
    assert reacquired.attempt == 2
    assert reacquired.lease_token == "lease-2"
    assert reacquired.lease_token != first.lease_token
    assert record is not None
    assert record.last_expired_at == clock.now


def test_spanner_old_worker_is_fenced_after_reacquisition() -> None:
    clock = MutableClock()
    registry = new_spanner_registry(clock=clock)
    first = start_operation(registry)
    clock.advance(timedelta(seconds=30))
    start_operation(registry)

    with pytest.raises(StaleExecutionLeaseError):
        registry.complete(
            idempotency_scope="tenant-a",
            idempotency_key="operation-1",
            lease_token=required_lease_token(first),
            response_payload={"transfer_id": "stale"},
        )


def test_spanner_late_completion_persists_expired_state() -> None:
    clock = MutableClock()
    registry = new_spanner_registry(clock=clock)
    acquired = start_operation(registry)
    clock.advance(timedelta(seconds=30))

    with pytest.raises(ExpiredExecutionLeaseError):
        registry.complete(
            idempotency_scope="tenant-a",
            idempotency_key="operation-1",
            lease_token=required_lease_token(acquired),
            response_payload={"transfer_id": "late"},
        )

    record = registry.get("operation-1", idempotency_scope="tenant-a")
    assert record is not None
    assert record.status == IdempotencyStatus.EXPIRED
    assert record.last_expired_at == clock.now


def test_spanner_expiry_sweeper_is_transactional_and_idempotent() -> None:
    clock = MutableClock()
    registry = new_spanner_registry(clock=clock)
    start_operation(registry)

    assert registry.expire_pending("operation-1", idempotency_scope="tenant-a") is False
    clock.advance(timedelta(seconds=30))
    assert registry.expire_pending("operation-1", idempotency_scope="tenant-a") is True
    assert registry.expire_pending("operation-1", idempotency_scope="tenant-a") is False


def test_spanner_schema_limits_fail_before_mutation() -> None:
    registry = new_spanner_registry()

    with pytest.raises(ValueError, match="idempotency_key"):
        registry.start(
            idempotency_scope="tenant-a",
            idempotency_key="x" * 257,
            operation_type="transfer.create",
            request_hash="hash-100",
        )
