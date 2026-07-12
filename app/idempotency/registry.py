from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from threading import RLock
from typing import Any
from uuid import uuid4

from app.idempotency.value_semantics import (
    FrozenPayload,
    freeze_payload,
    validate_identity,
)


class IdempotencyStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


class IdempotencyDecision(str, Enum):
    CREATED = "CREATED"
    REACQUIRED = "REACQUIRED"
    PENDING = "PENDING"
    REPLAY = "REPLAY"
    CONFLICT = "CONFLICT"
    FAILED = "FAILED"


class IdempotencyRegistryError(RuntimeError):
    """Base error for invalid registry state or lease usage."""


class InvalidIdempotencyTransitionError(IdempotencyRegistryError):
    """Raised when a terminal or incompatible state is transitioned."""


class StaleExecutionLeaseError(IdempotencyRegistryError):
    """Raised when an obsolete worker attempts to commit a result."""


class ExpiredExecutionLeaseError(IdempotencyRegistryError):
    """Raised when a worker attempts to commit after lease expiry."""


@dataclass(frozen=True)
class RegistryResult:
    decision: IdempotencyDecision
    status: IdempotencyStatus
    attempt: int
    lease_token: str | None = None
    lease_expires_at: datetime | None = None
    response_payload: FrozenPayload | None = None
    error_payload: FrozenPayload | None = None


@dataclass
class IdempotencyRecord:
    idempotency_scope: str
    idempotency_key: str
    operation_type: str
    request_hash: str
    status: IdempotencyStatus
    response_payload: FrozenPayload | None
    error_payload: FrozenPayload | None
    created_at: datetime
    updated_at: datetime
    lease_token: str
    lease_expires_at: datetime
    attempt: int = 1
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    last_expired_at: datetime | None = None


@dataclass(frozen=True)
class IdempotencyRecordSnapshot:
    idempotency_scope: str
    idempotency_key: str
    operation_type: str
    request_hash: str
    status: IdempotencyStatus
    response_payload: FrozenPayload | None
    error_payload: FrozenPayload | None
    created_at: datetime
    updated_at: datetime
    lease_token: str
    lease_expires_at: datetime
    attempt: int
    completed_at: datetime | None
    failed_at: datetime | None
    last_expired_at: datetime | None


class InMemoryIdempotencyRegistry:
    def __init__(
        self,
        *,
        pending_ttl: timedelta = timedelta(minutes=5),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if pending_ttl <= timedelta(0):
            raise ValueError("pending_ttl must be greater than zero")

        self._pending_ttl = pending_ttl
        self._clock = clock if clock is not None else lambda: datetime.now(UTC)
        self._records: dict[tuple[str, str], IdempotencyRecord] = {}
        self._lock = RLock()

    def start(
        self,
        *,
        idempotency_key: str,
        operation_type: str,
        request_hash: str,
        idempotency_scope: str,
    ) -> RegistryResult:
        self._validate_input(
            idempotency_scope,
            idempotency_key,
            operation_type,
            request_hash,
        )
        record_key = self._record_key(
            idempotency_scope,
            idempotency_key,
        )

        with self._lock:
            now = self._now()
            existing = self._records.get(record_key)

            if existing is None:
                record = self._new_pending_record(
                    idempotency_scope=idempotency_scope,
                    idempotency_key=idempotency_key,
                    operation_type=operation_type,
                    request_hash=request_hash,
                    now=now,
                )
                self._records[record_key] = record

                return self._acquired_result(
                    IdempotencyDecision.CREATED,
                    record,
                )

            if (
                existing.request_hash != request_hash
                or existing.operation_type != operation_type
            ):
                return RegistryResult(
                    decision=IdempotencyDecision.CONFLICT,
                    status=existing.status,
                    attempt=existing.attempt,
                )

            if existing.status == IdempotencyStatus.COMPLETED:
                return RegistryResult(
                    decision=IdempotencyDecision.REPLAY,
                    status=existing.status,
                    attempt=existing.attempt,
                    response_payload=freeze_payload(existing.response_payload),
                )

            if existing.status == IdempotencyStatus.FAILED:
                return RegistryResult(
                    decision=IdempotencyDecision.FAILED,
                    status=existing.status,
                    attempt=existing.attempt,
                    error_payload=freeze_payload(existing.error_payload),
                )

            if existing.status == IdempotencyStatus.PENDING:
                if now < existing.lease_expires_at:
                    return RegistryResult(
                        decision=IdempotencyDecision.PENDING,
                        status=existing.status,
                        attempt=existing.attempt,
                        lease_expires_at=existing.lease_expires_at,
                    )

                self._expire_record(existing, now)

            self._reacquire_record(existing, now)

            return self._acquired_result(
                IdempotencyDecision.REACQUIRED,
                existing,
            )

    def complete(
        self,
        *,
        idempotency_key: str,
        lease_token: str,
        response_payload: dict[str, Any],
        idempotency_scope: str,
    ) -> IdempotencyRecordSnapshot:
        with self._lock:
            record = self._get_record(
                idempotency_scope,
                idempotency_key,
            )
            now = self._now()
            self._require_active_lease(
                record,
                lease_token,
                now,
            )

            record.status = IdempotencyStatus.COMPLETED
            record.response_payload = freeze_payload(response_payload)
            record.error_payload = None
            record.updated_at = now
            record.completed_at = now

            return self._snapshot(record)

    def fail(
        self,
        *,
        idempotency_key: str,
        lease_token: str,
        error_payload: dict[str, Any],
        idempotency_scope: str,
    ) -> IdempotencyRecordSnapshot:
        with self._lock:
            record = self._get_record(
                idempotency_scope,
                idempotency_key,
            )
            now = self._now()
            self._require_active_lease(
                record,
                lease_token,
                now,
            )

            record.status = IdempotencyStatus.FAILED
            record.error_payload = freeze_payload(error_payload)
            record.response_payload = None
            record.updated_at = now
            record.failed_at = now

            return self._snapshot(record)

    def expire_pending(
        self,
        idempotency_key: str,
        *,
        idempotency_scope: str,
    ) -> bool:
        """Expire a due pending operation.

        Intended for a deterministic sweeper or recovery process.
        """
        with self._lock:
            record = self._records.get(
                self._record_key(
                    idempotency_scope,
                    idempotency_key,
                )
            )

            if record is None:
                return False

            if record.status != IdempotencyStatus.PENDING:
                return False

            now = self._now()

            if now < record.lease_expires_at:
                return False

            self._expire_record(record, now)
            return True

    def get(
        self,
        idempotency_key: str,
        *,
        idempotency_scope: str,
    ) -> IdempotencyRecordSnapshot | None:
        with self._lock:
            record = self._records.get(
                self._record_key(
                    idempotency_scope,
                    idempotency_key,
                )
            )
            return None if record is None else self._snapshot(record)

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)

    def _new_pending_record(
        self,
        *,
        idempotency_scope: str,
        idempotency_key: str,
        operation_type: str,
        request_hash: str,
        now: datetime,
    ) -> IdempotencyRecord:
        return IdempotencyRecord(
            idempotency_scope=idempotency_scope,
            idempotency_key=idempotency_key,
            operation_type=operation_type,
            request_hash=request_hash,
            status=IdempotencyStatus.PENDING,
            response_payload=None,
            error_payload=None,
            created_at=now,
            updated_at=now,
            lease_token=self._new_lease_token(),
            lease_expires_at=now + self._pending_ttl,
        )

    def _reacquire_record(
        self,
        record: IdempotencyRecord,
        now: datetime,
    ) -> None:
        record.status = IdempotencyStatus.PENDING
        record.lease_token = self._new_lease_token()
        record.lease_expires_at = now + self._pending_ttl
        record.attempt += 1
        record.updated_at = now
        record.response_payload = None
        record.error_payload = None
        record.completed_at = None
        record.failed_at = None

    @staticmethod
    def _acquired_result(
        decision: IdempotencyDecision,
        record: IdempotencyRecord,
    ) -> RegistryResult:
        return RegistryResult(
            decision=decision,
            status=record.status,
            attempt=record.attempt,
            lease_token=record.lease_token,
            lease_expires_at=record.lease_expires_at,
        )

    @staticmethod
    def _expire_record(
        record: IdempotencyRecord,
        now: datetime,
    ) -> None:
        record.status = IdempotencyStatus.EXPIRED
        record.updated_at = now
        record.last_expired_at = now

    def _require_active_lease(
        self,
        record: IdempotencyRecord,
        lease_token: str,
        now: datetime,
    ) -> None:
        if record.status == IdempotencyStatus.EXPIRED:
            raise ExpiredExecutionLeaseError("execution lease has expired")

        if record.status != IdempotencyStatus.PENDING:
            raise InvalidIdempotencyTransitionError(
                f"cannot transition {record.status.value} operation"
            )

        if record.lease_token != lease_token:
            raise StaleExecutionLeaseError("execution lease token is stale")

        if now >= record.lease_expires_at:
            self._expire_record(record, now)
            raise ExpiredExecutionLeaseError("execution lease has expired")

    @staticmethod
    def _validate_input(
        idempotency_scope: str,
        idempotency_key: str,
        operation_type: str,
        request_hash: str,
    ) -> None:
        validate_identity(
            idempotency_scope=idempotency_scope,
            idempotency_key=idempotency_key,
            operation_type=operation_type,
            request_hash=request_hash,
        )

    def _get_record(
        self,
        idempotency_scope: str,
        idempotency_key: str,
    ) -> IdempotencyRecord:
        record = self._records.get(
            self._record_key(
                idempotency_scope,
                idempotency_key,
            )
        )

        if record is None:
            raise KeyError((idempotency_scope, idempotency_key))

        return record

    @staticmethod
    def _snapshot(record: IdempotencyRecord) -> IdempotencyRecordSnapshot:
        return IdempotencyRecordSnapshot(
            idempotency_scope=record.idempotency_scope,
            idempotency_key=record.idempotency_key,
            operation_type=record.operation_type,
            request_hash=record.request_hash,
            status=record.status,
            response_payload=freeze_payload(record.response_payload),
            error_payload=freeze_payload(record.error_payload),
            created_at=record.created_at,
            updated_at=record.updated_at,
            lease_token=record.lease_token,
            lease_expires_at=record.lease_expires_at,
            attempt=record.attempt,
            completed_at=record.completed_at,
            failed_at=record.failed_at,
            last_expired_at=record.last_expired_at,
        )

    @staticmethod
    def _record_key(
        idempotency_scope: str,
        idempotency_key: str,
    ) -> tuple[str, str]:
        return idempotency_scope, idempotency_key

    @staticmethod
    def _new_lease_token() -> str:
        return uuid4().hex

    def _now(self) -> datetime:
        now = self._clock()

        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("clock must return a timezone-aware datetime")

        return now.astimezone(UTC)
