from __future__ import annotations

import json
from collections.abc import Mapping
from hashlib import sha256
from math import isfinite
from typing import Any


def to_json_compatible(value: Any) -> Any:
    """Return a detached, JSON-compatible representation of a value."""
    if value is None or isinstance(value, (str, bool, int)):
        return value

    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("JSON numbers must be finite")
        return value

    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}

        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("JSON object keys must be strings")

            normalized[key] = to_json_compatible(item)

        return normalized

    if isinstance(value, (list, tuple)):
        return [to_json_compatible(item) for item in value]

    raise ValueError(f"unsupported JSON value type: {type(value).__name__}")


def canonical_json(payload: Mapping[str, Any]) -> str:
    """Serialize a payload deterministically for hashing and comparison."""
    normalized = to_json_compatible(payload)

    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def stable_request_hash(payload: Mapping[str, Any]) -> str:
    """Return the SHA-256 hash of the canonical payload representation."""
    return sha256(canonical_json(payload).encode("utf-8")).hexdigest()
