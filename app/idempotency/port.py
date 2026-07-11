from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from app.idempotency.registry import IdempotencyRecord, RegistryResult


@runtime_checkable
class IdempotencyRegistry(Protocol):
    """Provider-neutral port for authoritative idempotency decisions."""

    def start(
        self,
        *,
        idempotency_key: str,
        operation_type: str,
        request_hash: str,
        idempotency_scope: str = "global",
    ) -> RegistryResult: ...

    def complete(
        self,
        *,
        idempotency_key: str,
        lease_token: str,
        response_payload: dict[str, Any],
        idempotency_scope: str = "global",
    ) -> IdempotencyRecord: ...

    def fail(
        self,
        *,
        idempotency_key: str,
        lease_token: str,
        error_payload: dict[str, Any],
        idempotency_scope: str = "global",
    ) -> IdempotencyRecord: ...

    def expire_pending(
        self,
        idempotency_key: str,
        *,
        idempotency_scope: str = "global",
    ) -> bool: ...

    def get(
        self,
        idempotency_key: str,
        *,
        idempotency_scope: str = "global",
    ) -> IdempotencyRecord | None: ...
