# ADR-0001: Critical Operations Idempotency Lab

## Status

Accepted for private lab implementation.

## Date

2026-07-09

## Context

This repository is being repositioned from a generic NeuroBank FastAPI demo into a private critical-operations lab focused on transaction control, idempotency, replay protection, and operational evidence.

The target use case is not a production banking system. The target is a reproducible technical lab that demonstrates how critical operations can be protected against duplicate execution, ambiguous retries, partial failures, and unsafe replays.

The project should remain technically conservative. It must avoid inflated claims such as blockchain, immutable ledger, nanosecond timing, core banking readiness, military-grade guarantees, or exactly-once end-to-end semantics.

Google Cloud Spanner is relevant because it can provide a strongly consistent transactional store suitable for a decision registry. However, Spanner alone does not solve all end-to-end idempotency problems. Application-level request hashing, state transitions, response replay, evidence records, recovery rules, and operational tests are still required.

## Decision

Build a private lab named:

**Critical Operations Idempotency Lab**

The lab will implement a controlled transfer-like operation protected by an idempotency registry and an append-only operational evidence trail.

The first implementation target will be a small FastAPI-based proof of concept with the following properties:

- a dedicated idempotency registry;
- stable request hashing;
- duplicate request detection;
- safe replay of completed responses;
- explicit handling of pending/in-progress operations;
- operational evidence events;
- concurrency tests;
- failure/retry tests;
- measurable duplicate suppression.

Cloud Spanner may be used as the transactional decision store in a later implementation phase. This ADR does not require immediate Spanner code.

## Scope

The lab will focus on:

1. Idempotent critical operation handling.
2. Replay protection using client-provided idempotency keys.
3. Request hash comparison to prevent key reuse with different payloads.
4. Transactional decision recording.
5. Evidence events suitable for audit and debugging.
6. Local reproducibility before cloud deployment.
7. Clear limits and honest documentation.

## Non-goals

This ADR explicitly excludes:

- production banking claims;
- regulatory certification claims;
- blockchain claims;
- immutable ledger claims;
- exactly-once end-to-end guarantees;
- nanosecond latency claims;
- military or classified-system positioning;
- uncontrolled edits to the existing FastAPI baseline;
- destructive rewrites of `app/main.py`, `app/config.py`, or `app/telemetry.py`.

## Proposed data model

The minimum conceptual model is:

### IdempotencyRegistry

Stores the decision state for a critical operation.

Fields:

- `idempotency_key`
- `operation_type`
- `request_hash`
- `status`
- `response_payload`
- `error_payload`
- `created_at`
- `updated_at`
- `completed_at`

Allowed statuses:

- `PENDING`
- `COMPLETED`
- `FAILED`
- `EXPIRED`

### OperationalEvidenceEvent

Stores audit-oriented operational facts.

Fields:

- `event_id`
- `operation_id`
- `idempotency_key`
- `event_type`
- `event_payload`
- `created_at`

Example event types:

- `REQUEST_RECEIVED`
- `IDEMPOTENCY_KEY_CREATED`
- `DUPLICATE_REPLAYED`
- `KEY_REUSE_REJECTED`
- `OPERATION_COMPLETED`
- `OPERATION_FAILED`

## Idempotency contract

For a given `idempotency_key`:

1. First valid request creates a registry entry.
2. A repeated request with the same payload returns the original completed response.
3. A repeated request with a different payload is rejected.
4. A concurrent duplicate must not execute the critical operation twice.
5. A pending operation must be handled explicitly, not silently duplicated.
6. Every meaningful decision must create operational evidence.

## Spanner rationale

Spanner is a candidate backend for the registry because it supports strongly consistent transactions and can act as a durable decision store for critical operations.

The lab will treat Spanner as a consistency and transaction substrate, not as a magic guarantee layer.

The application remains responsible for:

- idempotency key validation;
- request hashing;
- response replay semantics;
- business operation boundaries;
- evidence generation;
- retry behavior;
- conflict handling;
- observability.

## Validation criteria

The lab is acceptable only if it can demonstrate:

- duplicate requests do not create duplicate critical operations;
- same-key/different-payload requests are rejected;
- completed responses can be replayed safely;
- concurrent duplicate requests are handled deterministically;
- tests document expected behavior;
- the existing baseline test suite remains green.

Minimum baseline command:

```bash
python -m pytest -q
Expected current baseline:

34 passed
Consequences

Positive consequences:

The repo gains a focused technical narrative.
The demo becomes more defensible for critical systems discussions.
Spanner integration can be introduced later without contaminating the baseline.
The project avoids overclaiming.

Trade-offs:

The first version is a lab, not a product.
More evidence plumbing is required before any serious external presentation.
Spanner adds operational complexity and should only be introduced after local semantics are proven.
Next steps
Keep this ADR as the design anchor.
Add a local in-memory or SQLite-backed idempotency prototype first.
Add tests for duplicate replay, key reuse, pending state, and concurrency.
Only after local semantics are green, introduce a Spanner-backed repository.
Document benchmark results separately.
