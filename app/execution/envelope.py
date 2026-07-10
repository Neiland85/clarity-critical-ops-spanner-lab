from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from app.execution.hashing import stable_request_hash, to_json_compatible


class ReplayPolicy(str, Enum):
    RETURN_STORED_RESPONSE = "RETURN_STORED_RESPONSE"
    RETURN_STATUS = "RETURN_STATUS"
    REJECT = "REJECT"


def _freeze_json(value: Any) -> Any:
    normalized = to_json_compatible(value)
    return _freeze_normalized_json(normalized)


def _freeze_normalized_json(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType(
            {key: _freeze_normalized_json(item) for key, item in value.items()}
        )

    if isinstance(value, list):
        return tuple(_freeze_normalized_json(item) for item in value)

    return value


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}

    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]

    return value


class ExecutionEnvelope(BaseModel):
    """Transport-independent contract for a critical operation."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    schema_version: Literal["1.0"] = "1.0"

    operation_id: UUID = Field(default_factory=uuid4)
    idempotency_key: str = Field(min_length=1, max_length=255)
    operation_type: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$",
    )

    payload: Mapping[str, Any]
    request_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    actor_id: str = Field(min_length=1, max_length=255)
    tenant_id: str = Field(min_length=1, max_length=255)

    correlation_id: UUID = Field(default_factory=uuid4)
    causation_id: UUID | None = None

    issued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    security_context: Mapping[str, Any] = Field(default_factory=dict)

    replay_policy: ReplayPolicy = ReplayPolicy.RETURN_STORED_RESPONSE

    @field_validator("idempotency_key", "actor_id", "tenant_id")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        if any(character.isspace() for character in value):
            raise ValueError("identifiers must not contain whitespace")

        return value

    @field_validator("payload", "security_context", mode="after")
    @classmethod
    def freeze_json_mapping(
        cls,
        value: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        return _freeze_json(value)

    @field_validator("issued_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("issued_at must be timezone-aware")

        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_request_hash(self) -> "ExecutionEnvelope":
        expected_hash = stable_request_hash(self.payload)

        if self.request_hash != expected_hash:
            raise ValueError("request_hash does not match payload")

        return self

    @field_serializer("payload", "security_context")
    def serialize_json_mapping(
        self,
        value: Mapping[str, Any],
    ) -> dict[str, Any]:
        return _thaw_json(value)

    @classmethod
    def create(
        cls,
        *,
        idempotency_key: str,
        operation_type: str,
        payload: Mapping[str, Any],
        actor_id: str,
        tenant_id: str,
        operation_id: UUID | None = None,
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
        issued_at: datetime | None = None,
        security_context: Mapping[str, Any] | None = None,
        replay_policy: ReplayPolicy = ReplayPolicy.RETURN_STORED_RESPONSE,
    ) -> "ExecutionEnvelope":
        normalized_payload = to_json_compatible(payload)

        return cls(
            operation_id=operation_id or uuid4(),
            idempotency_key=idempotency_key,
            operation_type=operation_type,
            payload=normalized_payload,
            request_hash=stable_request_hash(normalized_payload),
            actor_id=actor_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id or uuid4(),
            causation_id=causation_id,
            issued_at=issued_at or datetime.now(UTC),
            security_context=security_context or {},
            replay_policy=replay_policy,
        )

    def payload_copy(self) -> dict[str, Any]:
        return _thaw_json(self.payload)

    def security_context_copy(self) -> dict[str, Any]:
        return _thaw_json(self.security_context)

    def idempotency_start_input(self) -> dict[str, str]:
        return {
            "idempotency_scope": self.tenant_id,
            "idempotency_key": self.idempotency_key,
            "operation_type": self.operation_type,
            "request_hash": self.request_hash,
        }
