from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from threading import RLock
from typing import Any


class IdempotencyStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


class IdempotencyDecision(str, Enum):
    CREATED = "CREATED"
    PENDING = "PENDING"
    REPLAY = "REPLAY"
    CONFLICT = "CONFLICT"
    FAILED = "FAILED"


@dataclass(frozen=True)
class RegistryResult:
    decision: IdempotencyDecision
    status: IdempotencyStatus
    response_payload: dict[str, Any] | None = None
    error_payload: dict[str, Any] | None = None


@dataclass
class IdempotencyRecord:
    idempotency_scope: str
    idempotency_key: str
    operation_type: str
    request_hash: str
    status: IdempotencyStatus
    response_payload: dict[str, Any] | None
    error_payload: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class InMemoryIdempotencyRegistry:
    def __init__(self) -> None:
        self._records: dict[tuple[str, str], IdempotencyRecord] = {}
        self._lock = RLock()

    def start(
        self,
        *,
        idempotency_key: str,
        operation_type: str,
        request_hash: str,
        idempotency_scope: str = "global",
    ) -> RegistryResult:
        self._validate_input(
            idempotency_scope,
            idempotency_key,
            operation_type,
            request_hash,
        )

        record_key = self._record_key(idempotency_scope, idempotency_key)

        with self._lock:
            existing = self._records.get(record_key)

            if existing is None:
                now = self._now()
                self._records[record_key] = IdempotencyRecord(
                    idempotency_scope=idempotency_scope,
                    idempotency_key=idempotency_key,
                    operation_type=operation_type,
                    request_hash=request_hash,
                    status=IdempotencyStatus.PENDING,
                    response_payload=None,
                    error_payload=None,
                    created_at=now,
                    updated_at=now,
                )
                return RegistryResult(
                    decision=IdempotencyDecision.CREATED,
                    status=IdempotencyStatus.PENDING,
                )

            if (
                existing.request_hash != request_hash
                or existing.operation_type != operation_type
            ):
                return RegistryResult(
                    decision=IdempotencyDecision.CONFLICT,
                    status=existing.status,
                    response_payload=existing.response_payload,
                    error_payload=existing.error_payload,
                )

            if existing.status == IdempotencyStatus.COMPLETED:
                return RegistryResult(
                    decision=IdempotencyDecision.REPLAY,
                    status=existing.status,
                    response_payload=existing.response_payload,
                )

            if existing.status == IdempotencyStatus.FAILED:
                return RegistryResult(
                    decision=IdempotencyDecision.FAILED,
                    status=existing.status,
                    error_payload=existing.error_payload,
                )

            return RegistryResult(
                decision=IdempotencyDecision.PENDING,
                status=existing.status,
            )

    def complete(
        self,
        *,
        idempotency_key: str,
        response_payload: dict[str, Any],
        idempotency_scope: str = "global",
    ) -> IdempotencyRecord:
        with self._lock:
            record = self._get_record(idempotency_scope, idempotency_key)
            now = self._now()
            record.status = IdempotencyStatus.COMPLETED
            record.response_payload = dict(response_payload)
            record.error_payload = None
            record.updated_at = now
            record.completed_at = now
            return record

    def fail(
        self,
        *,
        idempotency_key: str,
        error_payload: dict[str, Any],
        idempotency_scope: str = "global",
    ) -> IdempotencyRecord:
        with self._lock:
            record = self._get_record(idempotency_scope, idempotency_key)
            now = self._now()
            record.status = IdempotencyStatus.FAILED
            record.error_payload = dict(error_payload)
            record.updated_at = now
            return record

    def get(
        self,
        idempotency_key: str,
        *,
        idempotency_scope: str = "global",
    ) -> IdempotencyRecord | None:
        with self._lock:
            return self._records.get(
                self._record_key(idempotency_scope, idempotency_key)
            )

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)

    @staticmethod
    def _validate_input(
        idempotency_scope: str,
        idempotency_key: str,
        operation_type: str,
        request_hash: str,
    ) -> None:
        if not idempotency_scope.strip():
            raise ValueError("idempotency_scope must not be empty")
        if not idempotency_key.strip():
            raise ValueError("idempotency_key must not be empty")
        if not operation_type.strip():
            raise ValueError("operation_type must not be empty")
        if not request_hash.strip():
            raise ValueError("request_hash must not be empty")

    def _get_record(
        self,
        idempotency_scope: str,
        idempotency_key: str,
    ) -> IdempotencyRecord:
        record = self._records.get(self._record_key(idempotency_scope, idempotency_key))
        if record is None:
            raise KeyError((idempotency_scope, idempotency_key))
        return record

    @staticmethod
    def _record_key(
        idempotency_scope: str,
        idempotency_key: str,
    ) -> tuple[str, str]:
        return idempotency_scope, idempotency_key

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)
