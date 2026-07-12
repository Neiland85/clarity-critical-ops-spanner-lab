from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Self
from uuid import uuid4

from google.cloud import spanner
from google.cloud.spanner_v1 import param_types
from google.cloud.spanner_v1.data_types import JsonObject

from app.idempotency.registry import (
    ExpiredExecutionLeaseError,
    IdempotencyDecision,
    IdempotencyRecord,
    IdempotencyRecordSnapshot,
    IdempotencyStatus,
    InvalidIdempotencyTransitionError,
    RegistryResult,
    StaleExecutionLeaseError,
)
from app.idempotency.value_semantics import (
    FrozenPayload,
    freeze_payload,
    thaw_payload,
    validate_identity,
)

_TABLE = "IdempotencyRecords"
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
_SELECT_SQL = """
SELECT
  IdempotencyScope,
  IdempotencyKey,
  OperationType,
  RequestHash,
  Status,
  ResponsePayload,
  ErrorPayload,
  CreatedAt,
  UpdatedAt,
  LeaseToken,
  LeaseExpiresAt,
  Attempt,
  CompletedAt,
  FailedAt,
  LastExpiredAt
FROM IdempotencyRecords
WHERE IdempotencyScope = @scope AND IdempotencyKey = @key
"""

_KEY_TYPES = {"scope": param_types.STRING, "key": param_types.STRING}


@dataclass(frozen=True)
class _TransitionOutcome:
    record: IdempotencyRecord | None = None
    error: Exception | None = None


class SpannerIdempotencyRegistry:
    """Cloud Spanner implementation of the provider-neutral registry port."""

    def __init__(
        self,
        database: Any,
        *,
        pending_ttl: timedelta = timedelta(minutes=5),
        token_factory: Callable[[], str] | None = None,
    ) -> None:
        if pending_ttl <= timedelta(0):
            raise ValueError("pending_ttl must be greater than zero")
        self._database = database
        self._pending_ttl = pending_ttl
        self._token_factory = token_factory or (lambda: uuid4().hex)

    @classmethod
    def from_identifiers(
        cls,
        *,
        project_id: str,
        instance_id: str,
        database_id: str,
        pending_ttl: timedelta = timedelta(minutes=5),
    ) -> Self:
        for name, value in (
            ("project_id", project_id),
            ("instance_id", instance_id),
            ("database_id", database_id),
        ):
            if not value.strip():
                raise ValueError(f"{name} must not be empty")
        client = spanner.Client(project=project_id)
        database = client.instance(instance_id).database(database_id)
        return cls(database, pending_ttl=pending_ttl)

    def start(
        self,
        *,
        idempotency_key: str,
        operation_type: str,
        request_hash: str,
        idempotency_scope: str,
    ) -> RegistryResult:
        self._validate_identity(
            idempotency_scope,
            idempotency_key,
            operation_type,
            request_hash,
        )

        def transaction_body(transaction: Any) -> RegistryResult:
            now = self._transaction_now(transaction)
            record = self._read(
                transaction,
                scope=idempotency_scope,
                key=idempotency_key,
            )
            if record is None:
                record = self._new_record(
                    scope=idempotency_scope,
                    key=idempotency_key,
                    operation_type=operation_type,
                    request_hash=request_hash,
                    now=now,
                )
                self._write(transaction, record, insert=True)
                return self._acquired(IdempotencyDecision.CREATED, record)

            if (
                record.operation_type != operation_type
                or record.request_hash != request_hash
            ):
                return self._observed(IdempotencyDecision.CONFLICT, record)
            if record.status == IdempotencyStatus.COMPLETED:
                return self._observed(IdempotencyDecision.REPLAY, record)
            if record.status == IdempotencyStatus.FAILED:
                return self._observed(IdempotencyDecision.FAILED, record)
            if (
                record.status == IdempotencyStatus.PENDING
                and now < record.lease_expires_at
            ):
                return self._observed(IdempotencyDecision.PENDING, record)

            if record.status == IdempotencyStatus.PENDING:
                self._expire(record, now)
            self._reacquire(record, now)
            self._write(transaction, record)
            return self._acquired(IdempotencyDecision.REACQUIRED, record)

        return self._database.run_in_transaction(transaction_body)

    def complete(
        self,
        *,
        idempotency_key: str,
        lease_token: str,
        response_payload: dict[str, Any],
        idempotency_scope: str,
    ) -> IdempotencyRecordSnapshot:
        return self._finish(
            scope=idempotency_scope,
            key=idempotency_key,
            lease_token=lease_token,
            status=IdempotencyStatus.COMPLETED,
            payload=response_payload,
        )

    def fail(
        self,
        *,
        idempotency_key: str,
        lease_token: str,
        error_payload: dict[str, Any],
        idempotency_scope: str,
    ) -> IdempotencyRecordSnapshot:
        return self._finish(
            scope=idempotency_scope,
            key=idempotency_key,
            lease_token=lease_token,
            status=IdempotencyStatus.FAILED,
            payload=error_payload,
        )

    def expire_pending(
        self,
        idempotency_key: str,
        *,
        idempotency_scope: str,
    ) -> bool:
        def transaction_body(transaction: Any) -> bool:
            record = self._read(
                transaction,
                scope=idempotency_scope,
                key=idempotency_key,
            )
            if record is None or record.status != IdempotencyStatus.PENDING:
                return False
            now = self._transaction_now(transaction)
            if now < record.lease_expires_at:
                return False
            self._expire(record, now)
            self._write(transaction, record)
            return True

        return self._database.run_in_transaction(transaction_body)

    def get(
        self,
        idempotency_key: str,
        *,
        idempotency_scope: str,
    ) -> IdempotencyRecordSnapshot | None:
        with self._database.snapshot() as snapshot:
            record = self._read(
                snapshot,
                scope=idempotency_scope,
                key=idempotency_key,
            )
            return None if record is None else self._snapshot(record)

    def _finish(
        self,
        *,
        scope: str,
        key: str,
        lease_token: str,
        status: IdempotencyStatus,
        payload: dict[str, Any],
    ) -> IdempotencyRecordSnapshot:
        def transaction_body(transaction: Any) -> _TransitionOutcome:
            record = self._required(transaction, scope=scope, key=key)
            now = self._transaction_now(transaction)
            error = self._lease_error(record, lease_token, now)
            if isinstance(error, ExpiredExecutionLeaseError):
                if record.status == IdempotencyStatus.PENDING:
                    self._expire(record, now)
                    self._write(transaction, record)
                return _TransitionOutcome(error=error)
            if error is not None:
                return _TransitionOutcome(error=error)

            record.status = status
            record.updated_at = now
            if status == IdempotencyStatus.COMPLETED:
                record.response_payload = freeze_payload(payload)
                record.error_payload = None
                record.completed_at = now
            else:
                record.error_payload = freeze_payload(payload)
                record.response_payload = None
                record.failed_at = now
            self._write(transaction, record)
            return _TransitionOutcome(record=record)

        outcome = self._database.run_in_transaction(transaction_body)
        if outcome.error is not None:
            raise outcome.error
        if outcome.record is None:
            raise RuntimeError("transaction returned no record or error")
        return self._snapshot(outcome.record)

    def _read(self, reader: Any, *, scope: str, key: str) -> IdempotencyRecord | None:
        rows = reader.execute_sql(
            _SELECT_SQL,
            params={"scope": scope, "key": key},
            param_types=_KEY_TYPES,
        )
        row = next(iter(rows), None)
        return None if row is None else self._from_row(row)

    def _required(self, reader: Any, *, scope: str, key: str) -> IdempotencyRecord:
        record = self._read(reader, scope=scope, key=key)
        if record is None:
            raise KeyError((scope, key))
        return record

    @staticmethod
    def _write(
        transaction: Any, record: IdempotencyRecord, *, insert: bool = False
    ) -> None:
        mutation = transaction.insert if insert else transaction.update
        mutation(
            table=_TABLE,
            columns=_COLUMNS,
            values=[SpannerIdempotencyRegistry._values(record)],
        )

    @staticmethod
    def _values(record: IdempotencyRecord) -> tuple[Any, ...]:
        return (
            record.idempotency_scope,
            record.idempotency_key,
            record.operation_type,
            record.request_hash,
            record.status.value,
            SpannerIdempotencyRegistry._encode(record.response_payload),
            SpannerIdempotencyRegistry._encode(record.error_payload),
            record.created_at,
            record.updated_at,
            record.lease_token,
            record.lease_expires_at,
            record.attempt,
            record.completed_at,
            record.failed_at,
            record.last_expired_at,
        )

    @staticmethod
    def _from_row(row: tuple[Any, ...]) -> IdempotencyRecord:
        values = dict(zip(_COLUMNS, row, strict=True))
        return IdempotencyRecord(
            idempotency_scope=values["IdempotencyScope"],
            idempotency_key=values["IdempotencyKey"],
            operation_type=values["OperationType"],
            request_hash=values["RequestHash"],
            status=IdempotencyStatus(values["Status"]),
            response_payload=SpannerIdempotencyRegistry._decode(
                values["ResponsePayload"]
            ),
            error_payload=SpannerIdempotencyRegistry._decode(values["ErrorPayload"]),
            created_at=SpannerIdempotencyRegistry._utc(values["CreatedAt"]),
            updated_at=SpannerIdempotencyRegistry._utc(values["UpdatedAt"]),
            lease_token=values["LeaseToken"],
            lease_expires_at=SpannerIdempotencyRegistry._utc(values["LeaseExpiresAt"]),
            attempt=values["Attempt"],
            completed_at=SpannerIdempotencyRegistry._optional_utc(
                values["CompletedAt"]
            ),
            failed_at=SpannerIdempotencyRegistry._optional_utc(values["FailedAt"]),
            last_expired_at=SpannerIdempotencyRegistry._optional_utc(
                values["LastExpiredAt"]
            ),
        )

    @staticmethod
    def _encode(payload: FrozenPayload | None) -> JsonObject | None:
        thawed = thaw_payload(payload)
        return None if thawed is None else JsonObject(thawed)

    @staticmethod
    def _decode(payload: Any) -> dict[str, Any] | None:
        if payload is None:
            return None
        decoded = json.loads(payload) if isinstance(payload, str) else payload
        if not isinstance(decoded, dict):
            raise TypeError("Spanner JSON payload must decode to an object")
        return freeze_payload(decoded)

    def _new_record(
        self,
        *,
        scope: str,
        key: str,
        operation_type: str,
        request_hash: str,
        now: datetime,
    ) -> IdempotencyRecord:
        return IdempotencyRecord(
            idempotency_scope=scope,
            idempotency_key=key,
            operation_type=operation_type,
            request_hash=request_hash,
            status=IdempotencyStatus.PENDING,
            response_payload=None,
            error_payload=None,
            created_at=now,
            updated_at=now,
            lease_token=self._new_token(),
            lease_expires_at=now + self._pending_ttl,
        )

    def _reacquire(self, record: IdempotencyRecord, now: datetime) -> None:
        record.status = IdempotencyStatus.PENDING
        record.lease_token = self._new_token()
        record.lease_expires_at = now + self._pending_ttl
        record.attempt += 1
        record.updated_at = now
        record.response_payload = None
        record.error_payload = None
        record.completed_at = None
        record.failed_at = None

    @staticmethod
    def _expire(record: IdempotencyRecord, now: datetime) -> None:
        record.status = IdempotencyStatus.EXPIRED
        record.updated_at = now
        record.last_expired_at = now

    @staticmethod
    def _lease_error(
        record: IdempotencyRecord,
        lease_token: str,
        now: datetime,
    ) -> Exception | None:
        if record.status == IdempotencyStatus.EXPIRED:
            return ExpiredExecutionLeaseError("execution lease has expired")
        if record.status != IdempotencyStatus.PENDING:
            return InvalidIdempotencyTransitionError(
                f"cannot transition {record.status.value} operation"
            )
        if record.lease_token != lease_token:
            return StaleExecutionLeaseError("execution lease token is stale")
        if now >= record.lease_expires_at:
            return ExpiredExecutionLeaseError("execution lease has expired")
        return None

    @staticmethod
    def _observed(
        decision: IdempotencyDecision, record: IdempotencyRecord
    ) -> RegistryResult:
        if decision == IdempotencyDecision.CONFLICT:
            return RegistryResult(
                decision=decision,
                status=record.status,
                attempt=record.attempt,
            )

        return RegistryResult(
            decision=decision,
            status=record.status,
            attempt=record.attempt,
            lease_expires_at=(
                record.lease_expires_at
                if decision == IdempotencyDecision.PENDING
                else None
            ),
            response_payload=freeze_payload(record.response_payload),
            error_payload=freeze_payload(record.error_payload),
        )

    @staticmethod
    def _acquired(
        decision: IdempotencyDecision, record: IdempotencyRecord
    ) -> RegistryResult:
        return RegistryResult(
            decision=decision,
            status=record.status,
            attempt=record.attempt,
            lease_token=record.lease_token,
            lease_expires_at=record.lease_expires_at,
        )

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
    def _validate_identity(
        scope: str, key: str, operation_type: str, request_hash: str
    ) -> None:
        validate_identity(
            idempotency_scope=scope,
            idempotency_key=key,
            operation_type=operation_type,
            request_hash=request_hash,
        )

    def _new_token(self) -> str:
        token = self._token_factory()
        if not token or len(token) > 64:
            raise ValueError("lease token must contain 1 to 64 characters")
        return token

    @staticmethod
    def _transaction_now(transaction: Any) -> datetime:
        row = next(iter(transaction.execute_sql("SELECT CURRENT_TIMESTAMP()")), None)
        if row is None:
            raise RuntimeError("Spanner did not return a transaction timestamp")
        return SpannerIdempotencyRegistry._utc(row[0])

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Spanner timestamp must be timezone-aware")
        return value.astimezone(UTC)

    @staticmethod
    def _optional_utc(value: datetime | None) -> datetime | None:
        return None if value is None else SpannerIdempotencyRegistry._utc(value)
