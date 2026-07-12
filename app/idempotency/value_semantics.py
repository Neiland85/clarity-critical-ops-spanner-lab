from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from types import MappingProxyType
from typing import Any, TypeAlias

FrozenPayload: TypeAlias = Mapping[str, Any]


def freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {key: freeze_value(item) for key, item in value.items()}
        )

    if isinstance(value, (list, tuple)):
        return tuple(freeze_value(item) for item in value)

    return deepcopy(value)


def freeze_payload(
    payload: Mapping[str, Any] | None,
) -> FrozenPayload | None:
    if payload is None:
        return None

    return freeze_value(payload)


def thaw_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: thaw_value(item) for key, item in value.items()}

    if isinstance(value, tuple):
        return [thaw_value(item) for item in value]

    return deepcopy(value)


def thaw_payload(
    payload: FrozenPayload | None,
) -> dict[str, Any] | None:
    if payload is None:
        return None

    return thaw_value(payload)


def validate_identity(
    *,
    idempotency_scope: str,
    idempotency_key: str,
    operation_type: str,
    request_hash: str,
) -> None:
    for name, value, maximum in (
        ("idempotency_scope", idempotency_scope, 256),
        ("idempotency_key", idempotency_key, 256),
        ("operation_type", operation_type, 256),
        ("request_hash", request_hash, 128),
    ):
        if not value.strip():
            raise ValueError(f"{name} must not be empty")

        if len(value) > maximum:
            raise ValueError(f"{name} must be at most {maximum} characters")
