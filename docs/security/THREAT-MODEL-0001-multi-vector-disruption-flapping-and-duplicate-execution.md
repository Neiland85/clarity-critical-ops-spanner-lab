# THREAT-MODEL-0001: Multi-vector disruption, flapping and duplicate execution

- Status: Proposed
- Date: 2026-07-11
- Product: Clarity Critical Operations
- Applies to: provider-neutral critical execution control plane
- Related: `ADR-0004-multi-vector-disruption-and-flapping-control.md`

## 1. Purpose

This document defines the security and resilience threats that can cause a
critical operation to execute more than once, execute under contradictory
state, exceed bounded capacity, lose reconstructable evidence or amplify an
external disruption.

It separates three concerns that must not be collapsed into one mechanism:

1. network and edge-capacity protection;
2. application admission and execution control;
3. provider-health and recovery control.

The model is intentionally provider-neutral. It applies whether the
transactional backend, message transport, external provider or deployment
platform changes.

## 2. Security objectives

The control plane must preserve the following properties:

- one authoritative execution record per `(tenant_id, idempotency_key)`;
- deterministic conflict detection for the same key with different content;
- no terminal transition by a stale lease holder;
- bounded admission before expensive or durable allocation;
- bounded retry and redelivery amplification;
- provider-health transitions independent from execution-state transitions;
- controlled degradation, quarantine, recovery and failback;
- tenant isolation for state, policy, evidence and quotas;
- reconstructable authoritative transitions;
- no public claim beyond reproduced validation evidence.

## 3. Scope

### 3.1 In scope

- submission and validation of execution requests;
- idempotency identity and canonical request hashing;
- acquisition, lease rotation, expiry and reacquisition;
- execution-state transitions;
- admission quotas and capacity limits;
- retry budgets, backoff, jitter and bulkheads;
- provider-health observation and hysteresis;
- failover and recovery decisions;
- operational evidence and causal reconstruction;
- policy and configuration integrity;
- tenant-boundary enforcement;
- dependency and build-pipeline integrity.

### 3.2 External shared responsibilities

The following controls may be required but are not implemented by the core
execution control plane:

- carrier filtering;
- volumetric DDoS mitigation;
- WAF and edge bot management;
- upstream identity proofing;
- physical infrastructure security;
- provider-specific fraud controls;
- RF interference and anti-jamming controls.

Traffic that exhausts network or edge capacity before reaching the
application boundary cannot be contained by application idempotency.

### 3.3 Explicit exclusions

This model does not establish:

- DDoS immunity;
- anti-jamming capability;
- universal exactly-once execution;
- guaranteed regional availability;
- protection against untested attack volumes;
- production or industrial readiness.

## 4. Protected assets

### 4.1 Authoritative execution state

The authoritative state includes:

- tenant identifier;
- idempotency key;
- canonical request hash;
- operation type;
- execution state;
- attempt number;
- active lease identity or fingerprint;
- lease expiry;
- result or failure reference;
- transition timestamps.

### 4.2 Policy state

Policy state includes:

- admission limits;
- retry classifications and budgets;
- provider-health thresholds;
- cooldown and recovery windows;
- tenant-specific limits;
- policy version and integrity hash.

### 4.3 Operational evidence

Evidence includes:

- operation reference;
- authoritative decision;
- reason code;
- attempt;
- policy snapshot reference and hash;
- correlation and causation references;
- occurrence and recording timestamps;
- evidence object reference.

### 4.4 Sensitive capabilities

Lease tokens or equivalent fencing capabilities are sensitive internal
values. They must not be returned to clients, emitted in public events or
written to raw logs. Where correlation is required, only a non-reversible
fingerprint should be recorded.

## 5. Trust boundaries

### TB-01: Client to admission boundary

Untrusted or partially trusted requests cross into validation, authentication,
tenant resolution and admission policy.

### TB-02: Admission to execution control

An admitted request may allocate execution state. Rejected traffic must not
create unbounded state.

### TB-03: Execution control to authoritative registry

Correctness depends on atomic compare-and-transition semantics, uniqueness and
consistent lease fencing.

### TB-04: Execution control to external provider

Provider responses may be delayed, duplicated, reordered, incomplete or
incorrect. A timeout does not prove that an irreversible external effect did
not occur.

### TB-05: Event transport and workers

Messages may be redelivered, reordered or consumed concurrently. Workers may
continue after losing ownership.

### TB-06: Policy administration

Administrative policy changes can alter admission, retry, quarantine and
recovery behaviour. Configuration is security-sensitive.

### TB-07: Evidence export and observation

Logs, metrics, traces and evidence bundles may expose sensitive data or become
inconsistent with authoritative state.

### TB-08: Build and dependency pipeline

Compromised dependencies, workflows or artifacts can change runtime behaviour
without changing the intended design.

## 6. Threat actors and failure sources

The model considers:

- unauthenticated remote actors;
- authenticated but abusive clients;
- compromised tenant credentials;
- buggy or retrying client software;
- delayed or stale workers;
- compromised or faulty external providers;
- operator error;
- malicious or accidental policy changes;
- dependency and build-pipeline compromise;
- partial network, process, datastore or regional failure.

A threat does not require malicious intent. Many duplicate-effect failures are
caused by normal retry behaviour during partial failure.

## 7. Threat catalogue

### TM-EXEC-001: Duplicate submission and redelivery

**Scenario:** The same logical operation is submitted or delivered multiple
times because of client retries, broker redelivery, reconnect storms or
ambiguous timeouts.

**Impact:** Duplicate irreversible effects, contradictory results or repeated
provider calls.

**Required controls:**

- identity by `(tenant_id, idempotency_key)`;
- canonical request hashing;
- atomic first-writer registration;
- replay of the authoritative terminal result;
- conflict response for same key with different hash or operation type;
- evidence of every decision.

**Validation evidence:** deterministic replay and conflict tests, including
concurrent acquisition.

**Current status:** process-local semantics verified; distributed semantics not
yet verified.

### TM-EXEC-002: Stale-worker completion

**Scenario:** A worker continues after lease expiry while another worker has
reacquired the operation.

**Impact:** An old attempt overwrites a newer result or records a contradictory
terminal state.

**Required controls:**

- rotating lease identity;
- attempt increment on reacquisition;
- compare-and-transition using the current lease capability;
- rejection of completion or failure by stale holders;
- terminal-state protection.

**Validation evidence:** deterministic lease-expiry, reacquisition and stale
completion tests.

**Current status:** verified in the process-local registry.

### TM-EXEC-003: Hash or canonicalisation ambiguity

**Scenario:** Semantically different requests produce the same comparison
representation, or semantically identical requests produce inconsistent
hashes across components.

**Impact:** False replay, undetected conflict or incompatible cross-service
behaviour.

**Required controls:**

- versioned canonical representation;
- explicit field presence and type rules;
- stable Unicode, number and timestamp handling;
- SHA-256 over canonical bytes;
- contract tests across implementations;
- incompatible changes require a new contract version.

**Validation evidence:** canonicalisation vectors and cross-runtime fixtures.

**Current status:** local canonical hashing exists; cross-runtime vectors are
not yet complete.

### TM-ADM-001: Unique-key state exhaustion

**Scenario:** An actor sends a high rate of validly shaped requests using a new
idempotency key each time.

**Impact:** Unbounded registry growth, memory or storage exhaustion, and denial
of service to legitimate tenants.

**Required controls:**

- admission before state allocation;
- new-key rate limits per tenant and actor;
- maximum pending operations per tenant and globally;
- payload and inline-result limits;
- bounded retention and deterministic expiry;
- rejection evidence without durable allocation where possible.

**Validation evidence:** bounded unique-key storm tests with observable rejection
and stable resource use.

**Current status:** planned; not yet verified.

### TM-ADM-002: Oversized or pathological input

**Scenario:** A request uses excessive body size, multipart headers, deeply
nested content or expensive validation paths.

**Impact:** CPU, memory or parser exhaustion before execution control.

**Required controls:**

- edge and application body limits;
- parser and field-count limits;
- time-bounded validation;
- rejection before durable allocation;
- maintained dependency versions and vulnerability scanning.

**Validation evidence:** boundary tests for maximum accepted and first rejected
sizes.

**Current status:** dependency vulnerabilities are scanned; complete admission
limits are not yet defined.

### TM-RES-001: Retry amplification

**Scenario:** Clients, workers, brokers and providers each retry independently
during degradation.

**Impact:** Multiplicative load, provider collapse and prolonged recovery.

**Required controls:**

- classified retryability;
- bounded retry count;
- exponential backoff with jitter;
- per-operation and per-provider retry budgets;
- no recursive retry loops;
- backpressure and load shedding;
- no irreversible external effect inside a transaction callback that may be
  retried.

**Validation evidence:** injected timeout and redelivery scenarios showing a
bounded number of attempts.

**Current status:** planned; not yet verified end to end.

### TM-PROV-001: Provider flapping

**Scenario:** A provider alternates between success and failure, causing rapid
routing, quarantine or failback changes.

**Impact:** Oscillation, request storms, inconsistent routing and repeated
partial execution.

**Required controls:**

- provider-health state independent from execution state;
- consecutive-failure and consecutive-success thresholds;
- observation windows;
- minimum state duration;
- cooldown periods;
- quarantine and progressive recovery;
- controlled failback;
- evidence for every health transition.

**Validation evidence:** deterministic flapping scenarios that demonstrate
bounded transitions and no immediate full recovery after one success.

**Current status:** specified in ADR-0004; not yet implemented or verified.

### TM-PROV-002: Ambiguous provider timeout

**Scenario:** The external provider times out after possibly accepting or
executing an irreversible effect.

**Impact:** A retry may duplicate the external effect even when internal
idempotency is correct.

**Required controls:**

- provider-supported idempotency where available;
- stable outbound operation reference;
- status reconciliation before retrying ambiguous effects;
- classification of operations by reversibility;
- manual or compensating workflow where automated certainty is unavailable;
- evidence of outbound request, ambiguity and resolution.

**Validation evidence:** fault injection after provider acceptance but before
response delivery.

**Current status:** provider-specific control; not yet verified.

### TM-FAIL-001: Split-brain or inconsistent failover

**Scenario:** Two regions, processes or registries concurrently believe they
are authoritative after partial failure.

**Impact:** Duplicate ownership, conflicting terminal states or divergent
replay results.

**Required controls:**

- one authoritative execution registry;
- globally enforced uniqueness for the idempotency identity;
- fencing that remains valid across failover;
- explicit consistency and recovery assumptions;
- failover cannot bypass the authoritative record;
- reconciliation evidence after recovery.

**Validation evidence:** multi-process and regional fault tests with partition,
recovery and replay.

**Current status:** not yet verified.

### TM-TEN-001: Cross-tenant collision or disclosure

**Scenario:** A key, lookup, cache, quota or evidence query omits tenant scope.

**Impact:** One tenant can replay, block, inspect or influence another tenant's
operation.

**Required controls:**

- tenant identifier in every authoritative identity and query;
- tenant-aware uniqueness constraints;
- tenant-aware admission and retention;
- authorization checks on result and evidence access;
- tests using identical idempotency keys across tenants.

**Validation evidence:** cross-tenant isolation tests for create, replay,
conflict, result and evidence retrieval.

**Current status:** tenant-scoped idempotency exists; complete evidence and
administrative isolation remain validation targets.

### TM-EVID-001: Missing, contradictory or mutable evidence

**Scenario:** Logs and traces omit a transition, use inconsistent timestamps or
can be changed independently from authoritative state.

**Impact:** An incident cannot be reconstructed, or evidence presents a false
sequence.

**Required controls:**

- authoritative transition events;
- correlation and causation identifiers;
- occurrence and recording timestamps;
- policy snapshot reference and hash;
- append-oriented evidence storage;
- deterministic export and integrity verification;
- explicit treatment of clock uncertainty.

**Validation evidence:** replayable scenario bundles that reconstruct the same
transition sequence from recorded evidence.

**Current status:** structured logging exists; complete authoritative evidence
pipeline is planned.

### TM-CONF-001: Lease or secret disclosure

**Scenario:** Lease tokens, credentials or sensitive provider responses are
returned to clients or written to logs, traces, exceptions or evidence bundles.

**Impact:** Unauthorized state transition, credential abuse or sensitive data
exposure.

**Required controls:**

- internal-only lease capabilities;
- log redaction and allow-listed structured fields;
- fingerprints rather than raw tokens;
- secret scanning in CI;
- bounded and classified evidence payloads;
- no secrets in exception messages.

**Validation evidence:** log-capture tests and repository secret scanning.

**Current status:** lease capability is treated as internal; complete redaction
coverage remains a validation target.

### TM-OPS-001: Unsafe policy or configuration change

**Scenario:** An operator or compromised automation changes limits, retry
classification, provider thresholds or recovery behaviour without controlled
review.

**Impact:** Disabled protection, accidental outage, rapid failback or unbounded
retry.

**Required controls:**

- versioned policy;
- authenticated and authorized change path;
- review and approval appropriate to risk;
- policy integrity hash;
- staged rollout and rollback;
- evidence of who changed what and when;
- safe defaults when configuration is missing.

**Validation evidence:** configuration mutation, rollback and missing-policy
tests.

**Current status:** policy governance is specified; implementation is pending.

### TM-SUP-001: Dependency or build-pipeline compromise

**Scenario:** A vulnerable or malicious dependency, workflow change or artifact
alters runtime behaviour.

**Impact:** Remote compromise, parser failure, secret exposure or invalid build
output.

**Required controls:**

- pinned direct dependencies;
- automated vulnerability scanning;
- secret scanning;
- isolated CI permissions;
- reviewed workflow changes;
- reproducible dependency installation where practical;
- artifact provenance and integrity controls as the release process matures.

**Validation evidence:** clean dependency audit, passing security workflows and
reviewable dependency diffs.

**Current status:** pinned dependencies and multiple CI security checks exist;
full release provenance is not yet established.

### TM-NET-001: Volumetric edge exhaustion

**Scenario:** Traffic saturates network, load balancer or edge capacity before
requests reach application admission.

**Impact:** The application is unreachable even if its execution semantics are
correct.

**Required controls:** carrier and edge mitigation, WAF, traffic filtering and
capacity engineering outside the core control plane.

**Validation evidence:** provider-specific edge testing under a separately
approved plan.

**Current status:** external shared responsibility; no immunity claim.

## 8. Abuse and failure combinations

Validation must include combined scenarios rather than testing each mechanism
only in isolation. Priority combinations are:

1. duplicate submission plus stale worker;
2. unique-key flood plus provider timeout;
3. broker redelivery plus process restart;
4. provider flapping plus retry budget exhaustion;
5. failover plus delayed completion from the previous owner;
6. policy change during active degradation;
7. evidence delay or partial loss during recovery;
8. cross-tenant key reuse under concurrent load.

The expected result is not always successful execution. Safe rejection,
quarantine, deterministic failure or manual escalation may be the correct
outcome.

## 9. Detection and evidence requirements

The system must be able to distinguish at least:

- admission rejection;
- new execution creation;
- pending duplicate;
- terminal replay;
- conflicting reuse;
- lease expiry and reacquisition;
- stale-worker rejection;
- retry budget exhaustion;
- provider degradation, quarantine and recovery;
- load shedding;
- failover and reconciliation;
- evidence or policy integrity failure.

Each authoritative record should include a stable reason code. Free-text logs
must not be the only source for incident reconstruction.

## 10. Validation gates

A capability may move from target to verified only when all applicable gates
are satisfied:

1. the contract and invariant are documented;
2. deterministic automated tests exist;
3. failure injection reproduces the threat;
4. the control produces bounded, observable behaviour;
5. evidence reconstructs the authoritative sequence;
6. resource use is measured for the declared test boundary;
7. the test environment, versions and parameters are recorded;
8. the result is independently repeatable from the repository or retained
   evidence bundle.

Passing a unit test does not establish industrial load, distributed failover or
regional recovery.

## 11. Current claim boundary

Verified today:

- process-local idempotency semantics;
- conflict detection;
- deterministic expiry and reacquisition;
- lease rotation;
- stale-worker fencing;
- terminal-state protection;
- limited process-local concurrency;
- current runtime and development dependency audits with no known findings at
  the recorded validation point.

Not yet verified:

- sustained industrial load;
- distributed idempotency;
- unique-key load shedding;
- provider hysteresis;
- bounded end-to-end retry amplification;
- multi-process failover;
- regional recovery;
- multi-vector disruption containment;
- complete authoritative evidence reconstruction.

## 12. Residual risk

Even after planned controls are implemented:

- an external provider may not support idempotent irreversible effects;
- an ambiguous timeout may require reconciliation or human review;
- edge capacity can fail before application controls execute;
- common-mode dependency or control-plane failure may defeat redundancy;
- operator error can still create unsafe policy if governance is bypassed;
- evidence can be incomplete if external systems do not expose reliable
  identifiers or timestamps.

Residual risk must be documented per deployment and cannot be hidden by a
general exactly-once claim.

## 13. Review triggers

This threat model must be reviewed when:

- an execution contract changes version;
- a durable or distributed registry is introduced;
- a new external provider adapter is added;
- retry, failover or provider-health logic changes;
- evidence storage or export changes;
- a new tenant-isolation boundary is introduced;
- a material dependency advisory affects the deployed stack;
- validation reveals a new failure mode;
- a customer-specific integration attempts to redefine reusable core
  guarantees.
