# ADR-0002: Edge Idempotency and Execution Contracts

- **Status:** Accepted for staged product implementation
- **Date:** 2026-07-10
- **Decision owners:** Clarity Structures Digital S.L.
- **Related:** ADR-0001 — Critical Operations Idempotency Lab

## Context

This repository is evolving into a real product for critical financial and
non-financial operations.

The product is intended to integrate Google Cloud Spanner as a strongly
consistent transactional substrate for selected workloads requiring:

- deterministic idempotency;
- safe retries;
- duplicate suppression;
- transactional decision recording;
- controlled replay;
- operational evidence;
- security-boundary enforcement;
- transport-independent execution semantics;
- stable integration of independently evolving services.

The product must not be described as a mockup or disposable demonstration.

It is a product under construction and validation. Documentation must clearly
distinguish between:

1. implemented capabilities;
2. verified capabilities;
3. target architecture;
4. provider-specific integration still pending;
5. contractual or production controls not yet established.

## Problem

Duplicate critical operations may originate before an application service
receives a command.

Sources include:

- client retries;
- load-balancer retries;
- ingress retries;
- API gateway retries;
- webhook redelivery;
- WebSocket reconnection;
- event redelivery;
- worker recovery;
- network timeouts after a successful write;
- concurrent requests reaching different service instances.

If idempotency is implemented only inside a WebSocket handler, route function,
individual pod or in-memory cache, multiple instances may execute the same
critical operation more than once.

Transport-specific logic also increases coupling. HTTP routes, WebSockets,
hooks and internal events may accidentally develop different execution
semantics for the same business operation.

## Decision

The product will implement idempotency from the edge while keeping the
authoritative decision inside a shared transactional registry.

The system will use a transport-independent execution contract that converts
HTTP requests, WebSocket messages, webhooks and internal events into the same
logical command envelope before domain execution.

The high-level flow is:

    Client or external system
        -> Load Balancer / Ingress
        -> API Gateway / Command Router
        -> Security Integration Boundary
        -> Authoritative Idempotency Registry
        -> Domain Service
        -> Domain Write + Outbox / Evidence Event
        -> Events / Projections
        -> WebSockets / Hooks / External Consumers

## Cognitive abstraction

For this product, cognitive abstraction means that transport-specific inputs
are normalized into a common, explicit and versioned execution contract.

The core does not reason differently because a command arrived through:

- HTTP;
- WebSocket;
- webhook;
- scheduled worker;
- message broker;
- internal service invocation.

The transport changes. The execution semantics do not.

This abstraction must make the following properties explicit:

- identity;
- intent;
- causality;
- payload integrity;
- idempotency;
- authorization context;
- schema version;
- replay policy;
- evidence requirements.

## Common execution envelope

Every critical operation must be normalized into an execution envelope
containing, at minimum:

    operation_id
    idempotency_key
    operation_type
    request_hash
    actor_id
    tenant_id
    correlation_id
    causation_id
    schema_version
    issued_at
    security_context
    replay_policy

Additional fields may be added through versioned contracts.

Transport adapters must not silently change the semantic meaning of these
fields.

## Edge responsibilities

The load balancer, ingress or edge gateway participates in the idempotency
policy but is not the source of truth.

The edge may:

- require or propagate an idempotency key;
- normalize correlation and trace identifiers;
- authenticate the connection preliminarily;
- apply rate limits;
- reject malformed requests;
- preserve security context;
- classify safe and unsafe retry behaviour;
- prevent accidental retries for explicitly non-retryable commands;
- route any instance toward the same logical execution contract.

The edge must not be solely responsible for deciding whether a critical
operation has already completed.

The system must not depend on:

- sticky sessions;
- process-local memory;
- pod-local state;
- WebSocket session state;
- load-balancer cache;
- one specific service instance.

## Authoritative idempotency decision

The authoritative idempotency registry owns the execution decision.

The current local in-memory registry is an implemented and tested reference
implementation.

Google Cloud Spanner is the target transactional substrate for the durable,
shared implementation.

The registry must support at least these decisions:

- `CREATED`
- `PENDING`
- `REPLAY`
- `CONFLICT`
- `FAILED`
- `EXPIRED`

Required behaviour:

### First valid request

A new idempotency key and request hash create a pending operation.

### Same key and same payload

If the operation completed, the system returns the original response without
executing the domain operation again.

### Same key and different payload

The system rejects the request as a conflict.

An idempotency key must not be reused to represent a different operation.

### Concurrent duplicate

Concurrent requests reaching separate instances must converge on one
authoritative decision.

Only one request may acquire the right to execute the critical operation.

### Pending operation

A pending operation must be handled through an explicit policy.

Possible policies include:

- return a pending response;
- wait for bounded completion;
- query operation status;
- recover after a defined lease or timeout;
- transition to a controlled failed or expired state.

Pending records must not be silently overwritten.

## Security integration boundary

Authentication and authorization must occur before irreversible domain effects.

The execution boundary must support:

- authentication context;
- authorization policy;
- tenant isolation;
- payload validation;
- schema validation;
- request fingerprint verification;
- risk controls;
- audit hooks;
- policy decisions;
- trace and correlation propagation.

Security hooks must not bypass the authoritative idempotency decision.

A rejected security decision may generate operational evidence without
creating the protected domain effect.

## Transaction boundary

The intended durable design must coordinate:

1. the idempotency decision;
2. the domain write;
3. the outbox or evidence event.

The product must avoid these inconsistent states:

- domain operation executed but idempotency record missing;
- idempotency record completed but domain write missing;
- domain write committed but event not recoverable;
- response returned without durable evidence;
- event emitted twice because a transport retried.

The exact transaction implementation will depend on the selected domain and
Spanner repository design.

Spanner is the consistency substrate. It is not the business logic itself.

## Evidence and immutability

The product must not claim that the entire system is absolutely immutable.

The defensible design target is:

- append-only operational evidence;
- tamper-evident hashes;
- immutable identifiers;
- explicit state transitions;
- causal correlation;
- controlled replay;
- no silent rewriting of critical execution history.

Business entities may evolve.

The evidence of what was requested, decided, written and returned must remain
verifiable.

Evidence records should include:

    event_id
    operation_id
    idempotency_key
    event_type
    request_hash
    correlation_id
    causation_id
    actor_id
    decision
    event_payload
    created_at

## WebSockets

WebSockets are transport and projection mechanisms.

They are not the transactional source of truth.

A WebSocket command must be converted into the same execution envelope used by
other transports.

Reconnect and resume behaviour should support fields such as:

    command_id
    idempotency_key
    correlation_id
    schema_version
    sequence
    last_acknowledged_sequence
    resume_from_event_id

A reconnect must not repeat a completed critical write.

## Hooks and webhooks

External hooks must support:

    delivery_id
    idempotency_key
    payload_hash
    signature
    timestamp
    attempt_number
    schema_version

Redelivery of the same valid event must not duplicate the protected effect.

A reused delivery or idempotency identifier with a different payload must be
rejected and recorded.

## Contract boundaries

The product will separate these contracts:

- edge contract;
- command envelope contract;
- security decision contract;
- idempotency decision contract;
- domain operation contract;
- evidence and outbox contract;
- event delivery contract;
- WebSocket projection contract;
- external hook contract.

Contracts must be versioned and independently testable.

Provider-specific adapters must remain replaceable.

## Mainline and runtime stability

The `main` branch must remain releasable after each accepted service
integration.

Each non-trivial service change requires:

- a dedicated branch;
- local validation;
- contract tests;
- regression tests;
- security checks;
- reviewed integration;
- a clean working tree after merge.

At runtime, adding or replacing a service must not require uncontrolled global
reloads or provider-specific changes inside the domain core.

The core should communicate through explicit ports, adapters and versioned
contracts.

## Required validation

The architecture must be supported progressively by tests for:

- stable request hashing;
- duplicate request suppression;
- idempotency-key conflict detection;
- completed-response replay;
- concurrent duplicate handling;
- pending-state handling;
- failed-state handling;
- transport-independent command normalization;
- edge propagation of identifiers;
- WebSocket reconnection without duplicate writes;
- webhook redelivery without duplicate effects;
- atomic domain-write and outbox behaviour;
- security-boundary rejection;
- correlation and causation preservation;
- contract-version compatibility;
- isolated service integration;
- regression-free mainline operation.

## Regulatory and standards posture

This ADR is an architectural decision, not a legal certification.

The architecture is intended to support later control mapping for contexts
that may involve:

- GDPR / RGPD;
- data protection impact assessments;
- accountability and auditability;
- data minimisation;
- retention and deletion policies;
- access control;
- incident evidence;
- NIST security and resilience frameworks;
- sector-specific operational-resilience requirements;
- ICANN or ALAC-related concerns where DNS, domain governance, abuse or
  Internet-user interests are materially involved.

No document may claim regulatory compliance, NIST certification, production
readiness or legal sufficiency unless supported by the corresponding controls,
contracts, evidence and assessment.

## Claims permitted by this decision

Permitted:

- idempotency is designed from the edge;
- the authoritative decision is separated from transport state;
- a local idempotency registry is implemented and tested;
- the architecture targets Spanner as a shared transactional substrate;
- execution contracts are transport-independent;
- append-only operational evidence is an architectural requirement;
- WebSockets and hooks are consumers or adapters, not the source of truth;
- the product is under construction and validation.

Not yet permitted:

- Spanner integration is complete;
- exactly-once execution is guaranteed end to end;
- the full system is immutable;
- the product is production-ready;
- the product is certified or legally compliant;
- contractual SLAs have been validated;
- regulated deployment controls are complete.

## Consequences

### Positive

- duplicate handling begins before individual services;
- independently scaled instances converge on one decision;
- transport adapters remain replaceable;
- WebSockets and hooks do not own business truth;
- security checks become explicit integration boundaries;
- evidence can be reviewed independently from projections;
- the domain core remains cleaner and more stable;
- Spanner integration has a precise responsibility.

### Costs

- contracts must be versioned and governed;
- pending-state recovery requires explicit policy;
- outbox and evidence writing add implementation complexity;
- concurrency testing becomes mandatory;
- edge behaviour and backend behaviour must remain aligned;
- schema evolution requires compatibility rules;
- regulatory claims require separate evidence and assessment.

## Follow-up work

1. Define the first versioned `ExecutionEnvelope`.
2. Define the edge idempotency propagation contract.
3. Add pending-state and expiry policies.
4. Add operational evidence event models.
5. Define repository ports independent of Spanner.
6. Implement a Spanner-backed registry adapter.
7. Add concurrency and replay integration tests.
8. Add WebSocket and webhook adapters only after the common contract is stable.
9. Create a separate control-mapping document for GDPR, DPIA, NIST and relevant
   sector requirements.
