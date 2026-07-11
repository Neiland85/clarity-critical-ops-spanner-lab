# Idempotency Retention and Capacity Contract

- Status: Proposed
- Version: 1.0-draft
- Date: 2026-07-11
- Product: Clarity Critical Operations
- Applies to: provider-neutral critical execution control plane
- Related:
  - `docs/adr/ADR-0002-edge-idempotency-execution-contracts.md`
  - `docs/adr/ADR-0004-multi-vector-disruption-and-flapping-control.md`
  - `docs/security/THREAT-MODEL-0001-multi-vector-disruption-flapping-and-duplicate-execution.md`

## 1. Purpose

This contract defines the minimum retention, expiry, deletion, admission and
capacity semantics required for an authoritative idempotency registry.

Its purpose is to prevent two opposite failure modes:

1. deleting execution records too early and allowing an old request to execute
   again; and
2. retaining or allocating unbounded state until the registry becomes a denial
   of service against itself.

The contract is provider-neutral. A conforming implementation may use an
in-memory reference registry, a relational database, Google Cloud Spanner or
another transactional substrate, provided that the externally observable
semantics remain equivalent.

## 2. Normative language

The terms **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT** and **MAY** are
normative requirements for a conforming implementation.

Statements under `Current implementation boundary` describe verified repository
behaviour. Statements elsewhere define target contract requirements and must not
be presented as implemented until the corresponding validation gates pass.

## 3. Core identity and request binding

### 3.1 Authoritative identity

The authoritative idempotency identity is:

```text
(tenant_id, idempotency_key)
```

The current in-memory reference implementation represents `tenant_id` through
`idempotency_scope`. A durable adapter MUST preserve the same isolation
semantics even if it uses different physical column or index names.

`tenant_id` MUST be derived from an authenticated and authorized context. An
untrusted request body MUST NOT be allowed to select another tenant's scope.

### 3.2 Request binding

Each identity MUST be bound to, at minimum:

```text
operation_type
request_hash
schema_version
```

For the same authoritative identity:

- the same `operation_type` and `request_hash` refer to the same logical
  operation;
- a different `operation_type` or `request_hash` MUST produce `CONFLICT`;
- an existing record MUST NOT be silently overwritten to accept a different
  request;
- transport changes MUST NOT alter these semantics.

The request hash MUST be computed from a deterministic canonical
representation. Raw transport framing, header order and object-key order MUST
NOT create different hashes for semantically identical input.

### 3.3 Client key requirements

Idempotency keys MUST:

- be non-empty;
- be bounded in length;
- use an explicitly documented character set or encoding;
- be unique for the intended idempotency horizon;
- contain no secrets or personal data that is unnecessary for execution;
- remain stable across client retries and transport reconnections.

A client MUST NOT assume protection after the published idempotency horizon has
expired.

## 4. Execution-state contract

The version 1 execution states remain:

```text
PENDING
COMPLETED
FAILED
EXPIRED
```

The version 1 acquisition decisions remain:

```text
CREATED
REACQUIRED
PENDING
REPLAY
CONFLICT
FAILED
```

### 4.1 State meanings

`PENDING`
: One current attempt owns a bounded execution lease. Duplicate requests do not
  receive that lease.

`COMPLETED`
: The authoritative operation completed and its replayable result or durable
  result reference is available.

`FAILED`
: The authoritative attempt reached the version 1 terminal failure state and
  its failure result or durable failure reference is available.

`EXPIRED`
: The previous pending lease expired. The operation may be reacquired according
  to policy with a new lease token and an incremented attempt number.

### 4.2 Terminality

`COMPLETED` and `FAILED` are terminal in version 1.

A terminal record MUST NOT:

- be completed twice;
- be failed after completion;
- be completed after failure;
- be reacquired because a lease-duration timer elapsed;
- be converted into a different request binding.

A new product version may define controlled retry from selected failure classes,
but that behaviour requires a new explicit state and replay contract. It MUST
NOT be introduced as an implicit reinterpretation of `FAILED`.

## 5. Lease expiry is not record retention

The following durations are independent and MUST NOT be conflated:

```text
pending lease duration
full idempotency retention duration
optional evidence retention duration
```

The pending lease duration controls when an executing worker loses authority.
It does not authorize deletion of the idempotency record.

When a pending lease expires:

1. the existing lease holder loses transition authority;
2. the record becomes `EXPIRED` or is atomically reacquired;
3. reacquisition rotates the lease token;
4. the attempt number increases;
5. the prior token remains invalid;
6. the request binding remains unchanged;
7. the record remains inside the retention horizon.

A stale or expired lease holder MUST NOT complete or fail a newer attempt.

## 6. Idempotency horizon

### 6.1 Definition

The idempotency horizon is the minimum period during which the registry
preserves enough authoritative state to prevent the protected operation from
being executed again under the same identity.

The horizon begins at authoritative record creation and MUST be explicitly
configured by operation class or policy.

### 6.2 Required retained data

For the full idempotency horizon, a retained record MUST preserve at least:

```text
tenant_id
idempotency_key
operation_type
request_hash
schema_version
status
attempt
created_at
updated_at
terminal timestamp, when applicable
policy identifier and version
```

For `COMPLETED`, the registry MUST also preserve either:

- the replayable response payload; or
- a durable, integrity-protected response reference that can reconstruct the
  contractually required replay response.

For `FAILED`, the registry MUST preserve either:

- the replayable failure payload; or
- a durable, integrity-protected failure reference.

A response or failure payload MUST NOT be silently evicted while the registry
continues to advertise that complete replay semantics are available.

### 6.3 Minimum horizon selection

The configured horizon MUST be at least as long as the maximum plausible retry
or redelivery window for the protected operation, including:

- client retry policy;
- gateway and ingress retry policy;
- webhook redelivery policy;
- message retention and redelivery policy;
- worker recovery delay;
- operator replay window;
- expected offline or reconnect duration;
- bounded clock and scheduling delay.

No universal duration is established by this document. Each operation class
MUST publish and test its selected horizon.

### 6.4 After the horizon

After the horizon expires, a record MAY become purge-eligible according to the
retention policy.

Purging means the registry can no longer guarantee suppression or replay for
that identity. Therefore:

- purge eligibility MUST be explicit and observable;
- purge MUST NOT occur before the configured horizon;
- client contracts MUST state that late retries may no longer be protected;
- critical clients SHOULD use globally unique keys rather than intentionally
  reusing expired keys;
- evidence required outside the idempotency horizon MUST be governed by a
  separate evidence-retention policy.

## 7. Retention policy contract

Every authoritative operation MUST resolve one immutable policy snapshot before
record allocation.

A retention policy snapshot MUST include at least:

```text
policy_id
policy_version
policy_hash
operation_class
pending_lease_seconds
idempotency_horizon_seconds
max_request_bytes
max_response_bytes
max_error_bytes
max_new_keys_per_window
new_key_window_seconds
max_pending_per_tenant
max_pending_global
max_records_per_tenant
max_records_global
purge_batch_size
```

A durable record MUST store the policy identifier, version and hash used for its
creation. Later policy changes MUST NOT silently shorten the retention horizon
of an existing record unless an explicit migration is authorized, evidenced and
validated.

A missing, invalid or unsupported policy MUST cause fail-closed admission for a
new protected operation.

## 8. Admission before allocation

### 8.1 Separation of decisions

Admission is a separate decision from execution idempotency.

The system MUST determine whether it can safely accept a new identity before it
allocates durable or process-local record state for that identity.

An admission denial MUST NOT create a `PENDING` idempotency record.

### 8.2 Existing-key path

A request for an existing identity MUST first resolve the existing record and
request binding.

An existing-key lookup:

- MUST NOT consume a `new key` quota;
- MAY consume a separately defined request or lookup quota;
- MUST still enforce authentication, authorization and tenant isolation;
- MUST return `CONFLICT`, `PENDING`, `REPLAY` or `FAILED` according to the
  authoritative record;
- MUST NOT allocate another record.

This rule prevents a capacity limit from breaking correct replay while also
allowing duplicate lookup floods to be controlled independently.

### 8.3 New-key path

Before allocating a new record, the implementation MUST evaluate at least:

- request and envelope size;
- new keys per tenant per window;
- pending operations per tenant;
- global pending operations;
- records per tenant;
- global records;
- concurrent acquisitions;
- storage or memory pressure;
- policy availability;
- provider or repository health required for authoritative persistence.

The checks and the record creation MUST be race-safe. Concurrent requests MUST
not each observe spare capacity and collectively exceed a hard limit without a
bounded, documented tolerance.

### 8.4 Capacity denial

A capacity denial MUST:

- occur before expensive domain execution;
- avoid creating a protected effect;
- avoid allocating an idempotency record for a new identity;
- return a stable machine-readable reason code;
- identify whether retry is permitted and, when safe, a bounded retry delay;
- emit operational evidence without disclosing another tenant's activity.

Suggested reason codes include:

```text
IDEMPOTENCY_POLICY_UNAVAILABLE
REQUEST_SIZE_EXCEEDED
RESPONSE_SIZE_LIMIT_UNSUPPORTED
NEW_KEY_RATE_EXCEEDED
TENANT_PENDING_LIMIT_REACHED
GLOBAL_PENDING_LIMIT_REACHED
TENANT_RECORD_LIMIT_REACHED
GLOBAL_RECORD_LIMIT_REACHED
REGISTRY_CAPACITY_UNAVAILABLE
REGISTRY_HEALTH_UNAVAILABLE
```

Reason codes are contract identifiers. Human-readable messages may evolve
without changing their meaning.

## 9. Result-size limits

A worker MUST NOT be allowed to place an unbounded response or failure payload
inside the registry.

Before a terminal transition, the implementation MUST enforce:

- maximum serialized response bytes;
- maximum serialized error bytes;
- supported content type and schema;
- absence or redaction of forbidden secrets;
- integrity of any externalized payload reference.

If a result is too large, the system MUST follow an explicit failure policy. It
MUST NOT mark the operation `COMPLETED` while discarding the only replayable
result required by the contract.

## 10. Purge and reclamation

### 10.1 Eligibility

A record MAY be purged only when all of the following are true:

- it is not `PENDING`;
- its idempotency horizon has elapsed;
- no explicit preservation hold applies;
- any required evidence or result has been retained or transferred according to
  its separate policy;
- the purge decision uses the policy snapshot applicable to that record.

### 10.2 Atomicity and concurrency

Purge MUST be safe against concurrent lookup, replay, completion, failure,
expiry and reacquisition.

A purge worker MUST NOT delete a record that became ineligible after the worker
selected it.

A durable implementation SHOULD use a version, timestamp or transactional
predicate to prove that the record still satisfies the purge conditions at
commit time.

### 10.3 Bounded work

Purge MUST be incremental and bounded.

The implementation MUST define:

- maximum records per purge batch;
- maximum execution time per batch;
- backoff under repository pressure;
- tenant fairness or partitioning strategy;
- metrics for selected, purged, skipped and failed records.

A purge process MUST NOT create a load spike that threatens active execution.

### 10.4 Evidence

Each purge batch MUST emit enough evidence to reconstruct:

- policy identifier and version;
- selection cutoff;
- batch identifier;
- number selected;
- number purged;
- number skipped due to changed state or hold;
- number failed;
- occurrence and recording timestamps.

Raw request or response payloads SHOULD NOT be copied into purge logs.

## 11. Security requirements

### 11.1 Tenant isolation

Capacity counters, records, responses, errors and evidence MUST preserve tenant
isolation.

A caller MUST NOT be able to infer another tenant's:

- key existence;
- pending count;
- record count;
- payload;
- result;
- policy exception;
- capacity consumption.

### 11.2 Lease-token handling

A lease token is a sensitive execution capability.

It MUST:

- be generated with sufficient unpredictability;
- rotate on every reacquisition;
- be returned only to the authorized execution path;
- never be returned to a duplicate caller;
- never appear in public events;
- never be written raw to application logs or evidence records;
- be represented only by a non-reversible fingerprint when correlation is
  operationally required.

### 11.3 Policy integrity

Retention and capacity policy changes MUST be authenticated, authorized,
versioned and evidenced.

Emergency capacity reductions MAY be applied to new admissions, but they MUST
NOT silently invalidate an active lease or shorten an existing record's
idempotency horizon.

## 12. Observability and evidence

The registry MUST expose metrics or equivalent telemetry for:

```text
new identities admitted
existing identities resolved
conflicts
pending decisions
replays
failed decisions
reacquisitions
lease expiries
stale lease rejections
expired lease rejections
admission denials by reason
pending records by tenant and globally
records by state
record age by state
purge selected, completed, skipped and failed
storage or memory pressure
```

High-cardinality idempotency keys and lease tokens MUST NOT be used as metric
labels.

Authoritative transition evidence SHOULD include:

```text
operation reference
attempt
previous state
new state
decision
reason code
policy_id
policy_version
policy_hash
correlation reference
causation reference
occurred_at
recorded_at
```

## 13. Current implementation boundary

The repository currently implements and tests a process-local reference
registry with:

- identity scoped by `(idempotency_scope, idempotency_key)`;
- deterministic request-hash comparison;
- `PENDING`, `COMPLETED`, `FAILED` and `EXPIRED` states;
- `CREATED`, `REACQUIRED`, `PENDING`, `REPLAY`, `CONFLICT` and `FAILED`
  decisions;
- configurable positive pending lease duration;
- timezone-aware injected clock;
- lease-token rotation on reacquisition;
- attempt increments;
- stale-worker fencing;
- expired-lease rejection;
- terminal-state protection;
- deterministic explicit expiry;
- process-local tenant-scope isolation;
- limited process-local concurrent duplicate handling.

The current reference registry does not yet implement or prove:

- durable retention across restart;
- a persistent purge worker;
- per-tenant or global capacity quotas;
- admission before allocation;
- bounded result serialization;
- distributed or multi-process counters;
- a Spanner-backed authoritative adapter;
- sustained-load behaviour;
- restart, failover or regional recovery semantics.

## 14. Required validation gates

### 14.1 Contract tests

A conforming implementation MUST pass tests proving:

- same scope and key with same binding resolves one logical operation;
- same scope and key with different binding returns `CONFLICT`;
- the same key remains isolated across tenants;
- duplicate pending requests do not receive a lease;
- completed requests replay the original result;
- failed requests return the original failure contract;
- expired pending work is reacquired with a new token and incremented attempt;
- stale and expired lease holders cannot transition state;
- terminal records cannot be transitioned twice;
- lease expiry does not delete the record;
- terminal records are not purged before their horizon;
- purge does not delete records whose eligibility changed concurrently;
- existing-key lookup does not consume new-key quota;
- capacity denial creates no new idempotency record;
- hard limits remain bounded under concurrent admission;
- result-size violations do not create false completion;
- policy changes do not silently shorten existing horizons;
- tenant metrics and errors do not leak another tenant's state.

### 14.2 Recovery tests

A durable adapter MUST additionally prove:

- process restart preserves terminal replay and conflict detection;
- restart during `PENDING` preserves or safely expires lease authority;
- failover does not create two current lease holders;
- purge resumes idempotently after interruption;
- policy snapshots remain resolvable after policy updates;
- repository retry callbacks do not repeat irreversible external effects.

### 14.3 Capacity tests

Capacity validation MUST define and record:

- workload model;
- tenant distribution;
- duplicate-to-new-key ratio;
- payload and result sizes;
- concurrency level;
- test duration;
- configured limits;
- observed admission overshoot, if any;
- latency percentiles;
- resource consumption;
- failure and recovery behaviour.

No industrial-capacity claim is permitted from the current process-local
64-call concurrency test alone.

## 15. Claim boundary

Currently permitted:

- a process-local idempotency registry is implemented and tested;
- pending leases are bounded and rotate on reacquisition;
- stale workers are fenced in the reference implementation;
- terminal-state replay and conflict semantics are tested locally;
- process-local tenant scopes are isolated in tests;
- retention and capacity requirements are now explicitly defined as a target
  contract.

Not yet permitted:

- durable retention is implemented;
- record reclamation is production-safe;
- capacity is bounded across processes or regions;
- admission control is implemented;
- a Spanner adapter is complete;
- sustained industrial load has been validated;
- exactly-once execution is guaranteed end to end;
- the system is production-ready or certified.

## 16. Non-goals

This contract does not:

- define volumetric DDoS mitigation;
- define RF anti-jamming controls;
- select a commercial database or cloud provider;
- establish a universal retention duration;
- replace privacy, legal-hold or records-management assessment;
- guarantee exactly-once behaviour outside the defined execution boundary;
- authorize deletion of operational evidence required by another policy;
- claim production readiness.

## 17. Change control

An incompatible change requires a new contract version.

The following are incompatible unless explicitly versioned:

- changing authoritative identity composition;
- weakening conflict detection;
- making `FAILED` non-terminal;
- shortening a published horizon for existing records;
- changing purge eligibility;
- removing replay requirements;
- exposing lease tokens to new parties;
- changing hard-capacity semantics from fail-closed to unbounded allocation.

Provider-specific adapters MAY evolve independently when they preserve this
contract and pass the same conformance suite.