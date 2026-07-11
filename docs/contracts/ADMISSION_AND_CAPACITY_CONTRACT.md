# Admission and Capacity Contract

- Status: Proposed
- Version: 1.0-draft
- Date: 2026-07-11
- Product: Clarity Critical Operations
- Applies to: provider-neutral critical execution control plane
- Related:
  - `docs/adr/ADR-0004-multi-vector-disruption-and-flapping-control.md`
  - `docs/security/THREAT-MODEL-0001-multi-vector-disruption-flapping-and-duplicate-execution.md`
  - `docs/contracts/IDEMPOTENCY_RETENTION_AND_CAPACITY_CONTRACT.md`

## 1. Purpose

This contract defines how Clarity decides whether a critical operation may enter
the execution-control path, must wait, must be rejected, or must be degraded
before expensive work, durable allocation, external provider calls or protected
domain effects occur.

The contract exists to prevent overload from becoming inconsistency.

It addresses:

- unique-key floods that bypass duplicate suppression;
- reconnect and retry storms;
- tenant starvation;
- unbounded pending state;
- recursive retry amplification;
- excessive provider concurrency;
- oversized payloads and results;
- queue saturation;
- failure cascades;
- recovery surges after degradation.

Admission control is separate from idempotency. A valid idempotency key does not
create a right to consume unlimited capacity.

## 2. Normative language

The terms **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT** and **MAY** are
normative requirements for a conforming implementation.

Requirements in this document describe target contract behaviour unless a
section explicitly states that the behaviour is currently implemented and
verified.

## 3. Responsibility boundary

### 3.1 External shared responsibilities

This contract begins at the application boundary.

The following controls remain shared with or owned by external systems:

- carrier filtering;
- volumetric DDoS mitigation;
- WAF and bot management;
- connection-level SYN and TLS protection;
- upstream identity proofing;
- physical infrastructure capacity;
- provider-specific anti-abuse controls.

Clarity MUST NOT claim that application admission control provides network-level
DDoS immunity.

### 3.2 Clarity responsibilities

Once a request reaches the application boundary, Clarity MUST be able to decide
whether it may consume:

- parser and validation resources;
- authentication and authorization resources;
- idempotency-registry capacity;
- pending-operation capacity;
- worker concurrency;
- queue capacity;
- external provider concurrency;
- transactional capacity;
- result-storage capacity;
- evidence-generation capacity.

### 3.3 Ordering principle

The system SHOULD reject the cheapest invalid or over-capacity request as early
as possible.

The default order is:

```text
connection accepted
    -> transport framing limits
    -> payload-size and shape limits
    -> authentication
    -> tenant and actor resolution
    -> coarse rate admission
    -> semantic validation
    -> idempotency identity lookup
    -> new-allocation admission
    -> execution-slot reservation
    -> external-provider reservation
    -> protected domain execution
    -> evidence and result recording
```

An implementation MAY combine steps, but it MUST preserve equivalent security,
capacity and evidence semantics.

## 4. Admission decision contract

### 4.1 Decision values

A conforming implementation MUST produce one of the following decisions:

- `ADMITTED`
- `ADMITTED_DEGRADED`
- `PENDING_EXISTING`
- `REPLAY_EXISTING`
- `REJECTED_INVALID`
- `REJECTED_UNAUTHORIZED`
- `REJECTED_CONFLICT`
- `REJECTED_RATE_LIMIT`
- `REJECTED_TENANT_CAPACITY`
- `REJECTED_GLOBAL_CAPACITY`
- `REJECTED_PROVIDER_CAPACITY`
- `REJECTED_PAYLOAD_TOO_LARGE`
- `REJECTED_QUEUE_FULL`
- `REJECTED_POLICY`
- `RETRY_LATER`

An implementation MAY add provider-neutral reason codes, but it MUST NOT collapse
materially different rejection causes into an ambiguous success or generic
internal error.

### 4.2 AdmissionDecision 1.0

The first versioned admission result SHOULD contain at least:

```text
decision
reason_code
tenant_id
actor_id
operation_type
idempotency_key_reference
request_hash
policy_snapshot_id
policy_snapshot_hash
quota_scope
limit_name
limit_value
observed_value
reservation_id
retry_after
occurred_at
correlation_id
causation_id
evidence_reference
```

Raw secrets, credentials and lease tokens MUST NOT appear in this contract.

### 4.3 Determinism

Given the same authoritative state, policy snapshot and request identity, the
admission decision SHOULD be deterministic.

When the decision depends on approximate counters or eventually consistent
signals, the implementation MUST document that limitation and MUST fail safely
for protected operations.

### 4.4 No implicit execution right

Only `ADMITTED` and `ADMITTED_DEGRADED` may authorize creation of a new execution
attempt.

`PENDING_EXISTING` and `REPLAY_EXISTING` MUST NOT allocate a second execution
slot for the same logical operation.

A rejection decision MUST NOT create the protected domain effect.

## 5. Admission dimensions

Admission policy MUST be able to constrain the following dimensions
independently.

### 5.1 Transport and payload limits

- maximum request bytes;
- maximum decompressed bytes;
- maximum header count and aggregate header bytes;
- maximum multipart part count;
- maximum field count;
- maximum nesting depth;
- maximum collection cardinality;
- maximum canonicalized payload bytes;
- maximum inline result bytes;
- maximum evidence-event bytes.

Compressed or encoded input MUST be limited after expansion, not only before it.

### 5.2 Request-rate limits

- requests per tenant per window;
- requests per actor per window;
- requests per credential per window;
- requests per operation type per window;
- new idempotency keys per tenant per window;
- conflict attempts per identity per window;
- authentication failures per source and credential;
- status-poll requests per operation;
- reconnect attempts per client or session.

### 5.3 Concurrent-state limits

- pending operations per tenant;
- pending operations globally;
- active execution attempts per tenant;
- active execution attempts globally;
- active attempts per operation type;
- active operations per actor;
- active status waiters per operation;
- active provider calls per tenant;
- active provider calls globally;
- active provider calls per provider and capability.

### 5.4 Queue and backlog limits

- queued operations per tenant;
- queued operations globally;
- queue age;
- queue bytes;
- delayed-retry count;
- delayed-retry age;
- evidence-outbox backlog;
- evidence-outbox age;
- recovery backlog after failover;
- replay backlog.

### 5.5 Retry and redelivery limits

- retry attempts per operation;
- retry attempts per provider;
- retry budget per tenant;
- retry budget per operation type;
- redelivery count per event or hook;
- cumulative retry time;
- cumulative provider-call time;
- maximum retry concurrency;
- maximum recovery burst.

## 6. Capacity policy

### 6.1 Policy identity

Every decision MUST be attributable to a versioned capacity-policy snapshot.

The snapshot SHOULD identify:

```text
policy_id
policy_version
policy_hash
effective_from
scope
limits
priority_rules
degradation_rules
retry_rules
reservation_ttl
recovery_rules
```

A policy change MUST NOT silently rewrite the evidence of a past decision.

### 6.2 Static and dynamic limits

Limits MAY be:

- static configuration;
- tenant-contract limits;
- operation-type limits;
- risk-derived limits;
- health-derived dynamic limits;
- provider-capability limits;
- emergency overrides.

Dynamic limits MUST be bounded by configured minimum and maximum values.

A transient metric spike MUST NOT automatically produce unbounded oscillation in
admission policy.

### 6.3 Hierarchical evaluation

Admission SHOULD evaluate limits from narrowest to broadest scope:

```text
actor
    -> credential
    -> operation type
    -> tenant
    -> provider capability
    -> deployment cell
    -> region
    -> global
```

A request MUST satisfy every mandatory scope that applies to it.

### 6.4 Fairness

The system MUST prevent one tenant, actor or operation type from consuming all
shared capacity.

Permitted mechanisms include:

- reserved minimum capacity;
- weighted fair sharing;
- token buckets;
- concurrency partitions;
- bulkheads;
- queue partitions;
- maximum share limits;
- priority classes.

Fairness policy MUST be explicit and testable.

### 6.5 Priority

Priority MAY influence ordering and reserved capacity, but MUST NOT bypass:

- authentication;
- authorization;
- tenant isolation;
- payload limits;
- idempotency conflict detection;
- terminal-state protection;
- stale-worker fencing;
- evidence requirements.

Emergency priority MUST be attributable to an authorized policy decision.

## 7. Reservation semantics

### 7.1 Admission is not enough

An admission decision that is separated in time from execution MAY become stale.

A conforming implementation SHOULD use a bounded reservation for scarce
resources.

### 7.2 Reservation identity

A reservation SHOULD include:

```text
reservation_id
tenant_id
operation_reference
resource_class
quantity
created_at
expires_at
policy_snapshot_id
state
```

### 7.3 Reservation states

- `RESERVED`
- `CONSUMED`
- `RELEASED`
- `EXPIRED`
- `CANCELLED`

### 7.4 Reservation requirements

A reservation MUST:

- be scoped to the authorized tenant and operation;
- have a bounded lifetime;
- be consumed at most once;
- be released on terminal failure before consumption;
- expire deterministically;
- be excluded from public logs when it exposes sensitive capability details;
- produce evidence for material state transitions.

A reservation MUST NOT be reused for a different operation.

## 8. Idempotency-aware admission

### 8.1 Existing identities

An existing idempotency identity MUST be classified before new durable state is
allocated.

The following outcomes do not require a new execution reservation:

- completed record replay;
- failed terminal record response;
- pending existing operation response;
- conflict response.

### 8.2 New identities

A new identity MUST pass new-allocation limits before creating a durable or
in-memory record.

A storm of valid but unique keys MUST NOT grow the registry without bound.

### 8.3 Reacquisition

Reacquiring an expired operation MUST consume:

- an execution-attempt budget;
- a current capacity reservation;
- any applicable retry budget;
- any applicable provider-call budget.

Reacquisition MUST NOT bypass current policy because the identity was admitted
under an earlier policy.

## 9. Queueing and backpressure

### 9.1 Queueing is explicit

The system MUST NOT silently convert an immediate operation into an unbounded
queue.

A queued admission path MUST define:

- maximum queue depth;
- maximum queue age;
- ordering policy;
- fairness policy;
- cancellation semantics;
- retry semantics;
- evidence requirements;
- client-visible status semantics.

### 9.2 Backpressure

When downstream capacity is constrained, upstream components MUST receive an
explicit backpressure signal.

Permitted signals include:

- `RETRY_LATER`;
- bounded `Retry-After` metadata;
- queue-full rejection;
- degraded-mode admission;
- paused event consumption;
- reduced worker concurrency;
- reduced provider-call concurrency.

Components MUST NOT respond to backpressure by creating recursive retries.

### 9.3 Queue overflow

When a queue reaches its limit, the implementation MUST follow a documented
policy such as:

- reject newest;
- reject lowest priority;
- reserve protected capacity;
- spill to a bounded durable queue;
- pause upstream consumption.

Dropping an already accepted critical operation without evidence is prohibited.

## 10. Load shedding and degraded operation

### 10.1 Shedding principle

Load shedding MUST occur before the protected system enters uncontrolled
failure.

The system SHOULD shed work in this order:

1. optional projections and non-authoritative enrichments;
2. expensive synchronous result expansion;
3. low-priority new work;
4. non-critical status polling;
5. new operations that exceed protected capacity.

The system MUST preserve authoritative state transitions and evidence before
optional projections.

### 10.2 Degraded admission

`ADMITTED_DEGRADED` MAY be used only when the protected domain effect remains
safe and contractually defined.

The decision MUST identify what is degraded, for example:

- delayed projection;
- asynchronous evidence export;
- reduced provider set;
- reduced result detail;
- bounded deferred notification.

A degraded mode MUST NOT weaken authentication, authorization, idempotency,
fencing or tenant isolation.

### 10.3 Fail-open and fail-closed

Protected irreversible operations SHOULD fail closed when authoritative
capacity state cannot be determined.

Read-only or non-critical operations MAY fail open only under an explicit,
versioned policy with a documented risk boundary.

## 11. Provider-capacity control

### 11.1 Separate provider health and capacity

Provider health state and provider concurrency capacity MUST remain separate.

A provider MAY be healthy but saturated.

A provider MAY be degraded but still able to serve a protected minimum load.

### 11.2 Provider limits

The system SHOULD support:

- concurrency per provider;
- concurrency per provider capability;
- request rate per provider;
- retry budget per provider;
- timeout budget per provider;
- tenant share per provider;
- recovery ramp limits;
- failback ramp limits.

### 11.3 No retry amplification

A provider timeout MUST NOT cause every upstream layer to retry independently.

Only one governed layer SHOULD own each retry decision.

External irreversible effects MUST NOT be performed inside a database callback
that may be transparently retried.

## 12. Recovery and hysteresis

### 12.1 Recovery is capacity-controlled

After an outage, failover or quarantine, recovery MUST NOT immediately restore
full traffic.

Recovery SHOULD use:

- minimum cooldown;
- progressive concurrency increase;
- bounded probe traffic;
- success thresholds;
- failure thresholds;
- retry-budget reset policy;
- rollback to degraded or quarantined state.

### 12.2 Recovery backlog

Backlog replay MUST be admitted against current capacity.

Historical backlog MUST NOT starve current protected traffic unless policy
explicitly prioritizes recovery.

### 12.3 Flapping containment

A single success MUST NOT restore full capacity.

A single failure MUST NOT reduce capacity to zero unless the failure is
classified as terminal or integrity-threatening.

## 13. Time semantics

All capacity windows, reservation expiries and retry schedules MUST use
unambiguous time semantics.

Implementations MUST:

- use timezone-aware timestamps;
- distinguish occurrence time from recording time;
- define monotonic-duration behaviour where available;
- define behaviour under wall-clock adjustment;
- avoid negative or unbounded windows;
- bound clock-skew tolerance.

A policy MUST define whether window evaluation is fixed, sliding, token-bucket
based or concurrency based.

## 14. Evidence and observability

### 14.1 Authoritative evidence

Material admission and reservation transitions MUST preserve:

- decision;
- reason code;
- tenant and operation references;
- policy snapshot identifier and hash;
- applicable limit name;
- configured limit value;
- observed value or safe range;
- reservation reference;
- retry-after value when present;
- correlation and causation references;
- occurrence and recording timestamps;
- evidence reference.

### 14.2 Sensitive data

Evidence and logs MUST NOT expose:

- raw execution lease tokens;
- raw reservation capabilities;
- credentials;
- authorization tokens;
- unredacted secrets;
- full sensitive payloads unless separately authorized and protected.

Sensitive identifiers SHOULD use stable fingerprints where correlation is
required.

### 14.3 Metrics

The implementation SHOULD expose provider-neutral metrics for:

- admitted operations;
- rejected operations by reason;
- degraded admissions;
- active reservations;
- reservation expiry;
- pending operations;
- queue depth and age;
- tenant capacity consumption;
- provider concurrency;
- retry-budget consumption;
- load-shed decisions;
- recovery-ramp state;
- decision latency.

High-cardinality identifiers MUST NOT be used as unbounded metric labels.

## 15. Error and client response semantics

Rejections MUST be explicit and safe to retry only when policy permits.

A response SHOULD distinguish:

- malformed input;
- unauthorized input;
- idempotency conflict;
- existing pending operation;
- completed replay;
- rate limit;
- tenant capacity;
- global capacity;
- provider saturation;
- queue saturation;
- temporary policy hold.

`Retry-After` MUST be bounded and MUST NOT promise capacity at a time the system
cannot reasonably estimate.

Clients MUST NOT be instructed to retry an operation classified as non-retryable
or conflicting.

## 16. Configuration integrity

Capacity policy is security-sensitive configuration.

Changes MUST support:

- authenticated authorship;
- authorization;
- review or dual control where required;
- versioning;
- integrity hashing;
- bounded values;
- rollback;
- activation time;
- evidence of activation;
- environment and tenant scope.

Emergency overrides MUST expire automatically unless renewed through an
authorized process.

A missing policy MUST NOT default to unlimited capacity.

## 17. Current implementation boundary

The repository currently verifies:

- process-local idempotency identity;
- deterministic request hashing;
- conflict detection;
- pending lease creation;
- expiry and reacquisition;
- lease rotation;
- stale-worker fencing;
- terminal-state protection;
- tenant-like scope isolation;
- limited process-local duplicate concurrency.

The repository does not yet verify:

- admission quotas;
- capacity reservations;
- unique-key flood containment;
- bounded queueing;
- load shedding;
- provider concurrency governance;
- distributed counters;
- multi-process admission;
- regional capacity control;
- recovery ramping;
- sustained industrial load.

These capabilities remain contractual targets until implemented and validated.

## 18. Validation gates

A conforming implementation MUST pass reproducible tests for at least:

### 18.1 Payload and parser limits

- rejection before expensive allocation;
- compressed-expansion limits;
- multipart part-count limits;
- nesting and cardinality limits;
- bounded error responses.

### 18.2 Tenant and actor limits

- tenant isolation;
- actor isolation;
- one tenant cannot exhaust all capacity;
- configured reserved capacity is preserved;
- quota reset follows declared window semantics.

### 18.3 Unique-key flood

- many valid unique keys do not create unbounded registry growth;
- rejection occurs before durable allocation when the limit is exceeded;
- existing completed and pending identities remain queryable;
- evidence remains bounded.

### 18.4 Concurrency

- execution-slot limits hold under parallel submissions;
- reservations are consumed at most once;
- expired reservations release capacity;
- race conditions do not exceed configured limits;
- multi-process behaviour is tested for durable adapters.

### 18.5 Queueing and backpressure

- queue depth and age remain bounded;
- overflow follows the documented policy;
- accepted operations are not silently lost;
- upstream retry amplification is absent;
- cancellation and expiry are deterministic.

### 18.6 Provider saturation

- provider concurrency limits hold;
- retries consume a bounded budget;
- recovery ramps progressively;
- failback does not create a surge;
- provider saturation does not corrupt execution state.

### 18.7 Degraded operation

- optional work is shed before authoritative work;
- degraded decisions are evidenced;
- security and idempotency controls remain enforced;
- normal mode is restored through governed recovery.

### 18.8 Fault injection

- counter-store timeout;
- reservation-store timeout;
- queue-store timeout;
- provider timeout;
- provider flapping;
- partial regional degradation;
- clock skew;
- process crash after reservation;
- process crash after domain commit but before response.

## 19. Claim boundary

After this document is merged, the project MAY state:

- admission and execution are governed as separate concerns;
- the architecture defines bounded capacity and reservation semantics;
- unique-key floods are explicitly included in the threat and validation model;
- provider-capacity and recovery controls are defined as provider-neutral
  contracts.

The project MUST NOT yet state:

- admission control is implemented;
- the system withstands a specified request volume;
- tenant fairness is production-validated;
- provider flapping is contained in production;
- the system is DDoS-proof;
- distributed capacity enforcement is complete;
- regional recovery objectives have been demonstrated;
- industrial load limits are known.

## 20. Acceptance criteria for implementation

A future implementation may be declared conforming to this contract only when:

1. admission decisions are versioned and observable;
2. mandatory limits are configured with safe finite values;
3. new state is allocated only after applicable admission checks;
4. reservations are bounded and single-consumption;
5. tenant and global limits are enforced atomically enough for the declared
   threat model;
6. retries and queues are bounded;
7. provider concurrency and recovery are governed;
8. material decisions produce reconstructable evidence;
9. failure behaviour is explicit and tested;
10. claims are updated from target to verified only after reproducible evidence
    is stored.

## 21. Non-goals

This contract does not:

- guarantee network availability;
- replace carrier or edge DDoS mitigation;
- define commercial tenant entitlements;
- guarantee exactly-once execution end to end;
- select a specific datastore or queue;
- define a customer-specific priority model;
- establish regulatory certification;
- establish production readiness by itself.
