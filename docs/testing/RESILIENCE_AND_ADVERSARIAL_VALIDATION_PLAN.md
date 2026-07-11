# Resilience and Adversarial Validation Plan

- Status: Proposed
- Version: 1.0-draft
- Date: 2026-07-11
- Product: Clarity Critical Operations
- Applies to: provider-neutral critical execution control plane
- Related:
  - `docs/adr/ADR-0002-edge-idempotency-execution-contracts.md`
  - `docs/adr/ADR-0004-multi-vector-disruption-and-flapping-control.md`
  - `docs/security/THREAT-MODEL-0001-multi-vector-disruption-flapping-and-duplicate-execution.md`
  - `docs/contracts/IDEMPOTENCY_RETENTION_AND_CAPACITY_CONTRACT.md`
  - `docs/contracts/ADMISSION_AND_CAPACITY_CONTRACT.md`

## 1. Purpose

This plan defines how resilience, adversarial behaviour and claim boundaries are
validated for Clarity Critical Operations.

It is not a production-readiness certificate and does not establish a service
level agreement. It defines reproducible tests, evidence requirements, stop
conditions and promotion gates for capabilities that must not be claimed until
they have been demonstrated.

The plan protects against two opposite failures:

1. shipping a control-plane capability without enough evidence; and
2. treating a local reference implementation as if it had already demonstrated
   distributed or industrial behaviour.

## 2. Validation principles

### 2.1 Evidence before claim

A capability may be described as implemented only when the corresponding code
exists and is reviewable.

A capability may be described as verified only when:

- the validation scenario is versioned;
- the execution environment is recorded;
- the result is reproducible;
- the observed behaviour satisfies the gate;
- the evidence bundle is preserved;
- the claim registry references that evidence.

### 2.2 Failure is a result

A failed validation run is not to be hidden, retried until green without
explanation or replaced by an unsupported narrative.

The evidence bundle must preserve:

- the attempted configuration;
- the failed gate;
- the observed failure mode;
- the relevant logs and metrics;
- the corrective action, if any;
- the subsequent run as a separate record.

### 2.3 Provider neutrality

Tests must validate observable contracts and failure semantics rather than rely
on one provider's branding or undocumented behaviour.

Provider-specific adapters may have dedicated test profiles, but the core
validation language must remain stable across:

- transactional backends;
- message transports;
- deployment platforms;
- edge providers;
- external service providers.

### 2.4 Safety before stress

Adversarial scenarios must run in isolated environments with bounded resource
budgets.

Tests must not target third-party systems without explicit authorization.

Tests must not generate uncontrolled traffic, exhaust shared infrastructure or
create irreversible external effects.

## 3. Current verified boundary

At the date of this draft, the repository has verified process-local behaviour
for:

- deterministic request hashing;
- idempotency identity isolation by scope and key;
- duplicate suppression for the same logical request;
- conflict detection for the same key with different content;
- completed-response replay;
- terminal failed-state handling;
- pending leases;
- expiry and reacquisition;
- lease rotation;
- stale-worker fencing;
- terminal-transition protection;
- deterministic local expiry;
- limited thread-based concurrency in one process.

The current local concurrency evidence covers 64 submissions using 16 worker
threads and produces one `CREATED` decision with the remaining submissions
observing `PENDING`.

This does not verify:

- multi-process convergence;
- distributed idempotency;
- real Spanner behaviour;
- sustained industrial load;
- admission control under unique-key floods;
- provider-health hysteresis;
- load shedding or backpressure;
- message redelivery across independent workers;
- regional failover or recovery;
- outbox delivery guarantees;
- network DDoS resistance;
- RF anti-jamming capability;
- end-to-end exactly-once execution.

## 4. Validation layers

The plan uses six validation layers.

```text
L0  STATIC AND CONTRACT VALIDATION
L1  PROCESS-LOCAL SEMANTIC VALIDATION
L2  MULTI-PROCESS AND DURABLE-REGISTRY VALIDATION
L3  ADMISSION, CAPACITY AND PROVIDER-FAILURE VALIDATION
L4  FAILOVER, RECOVERY AND EVIDENCE VALIDATION
L5  CONTROLLED PRE-PRODUCTION SOAK AND OPERATIONAL REVIEW
```

A higher layer does not replace the lower layers.

Each layer must preserve evidence that the previous guarantees still hold.

## 5. Required test environment record

Every non-trivial validation run must record:

- repository commit SHA;
- branch or tag;
- scenario identifier and version;
- date and UTC time;
- operator;
- operating system and architecture;
- Python version;
- dependency lock or resolved package list;
- container image digest, when applicable;
- configuration hash;
- policy snapshot identifier and hash;
- backend adapter and version;
- transport adapter and version;
- number of processes, workers and threads;
- resource limits;
- dataset seed;
- load-generator version;
- start and end timestamps;
- termination reason;
- result summary;
- evidence bundle hash.

Secrets, raw credentials and lease tokens must not be written into the bundle.

## 6. Common metrics

The following metrics must be available where applicable:

### 6.1 Correctness

- authoritative records created;
- domain effects committed;
- duplicate effects observed;
- conflicts detected;
- replays served;
- stale completions rejected;
- expired completions rejected;
- terminal rewrites rejected;
- evidence events emitted;
- evidence gaps detected.

### 6.2 Admission and capacity

- submissions received;
- submissions admitted;
- submissions rejected;
- rejections by reason code;
- new idempotency keys per tenant and globally;
- pending operations per tenant and globally;
- active leases;
- queue depth;
- queue wait time;
- concurrent provider calls;
- shed load;
- memory use;
- CPU use;
- storage growth;
- file descriptors or connection-pool use.

### 6.3 Latency

- decision latency p50, p95 and p99;
- domain-effect latency p50, p95 and p99;
- replay latency p50, p95 and p99;
- recovery time;
- quarantine time;
- failback time;
- evidence publication delay.

### 6.4 Provider health

- state transitions;
- consecutive failure and success counts;
- retry-budget consumption;
- requests attempted while degraded;
- requests attempted while quarantined;
- probe results;
- progressive recovery percentage;
- oscillation count;
- uncontrolled failback count.

## 7. Global invariants

All scenarios must evaluate the following invariants when relevant.

### INV-001: one authoritative identity

At most one authoritative record may represent the same
`(tenant_id, idempotency_key)`.

### INV-002: request binding

The same key with a different operation type or request hash must not be treated
as the same request.

### INV-003: no stale terminal transition

A stale or expired lease holder must not complete or fail a newer attempt.

### INV-004: terminal-state integrity

A terminal record must not be silently reacquired or rewritten.

### INV-005: bounded allocation

Rejected requests must not create unbounded durable or in-memory state.

### INV-006: bounded amplification

Retries, reconnects and redeliveries must not recursively amplify work beyond
the configured policy.

### INV-007: tenant isolation

One tenant must not consume another tenant's identity, quota, evidence or
execution state.

### INV-008: evidence reconstruction

Every authoritative transition must be reconstructable from preserved evidence.

### INV-009: provider-state separation

A provider-health transition must not silently alter execution state.

### INV-010: claim restraint

A failed or unexecuted gate must not be represented as verified capability.

## 8. Validation gates

## Gate V0: static integrity

### Objective

Confirm that the repository and contracts are internally consistent before
runtime validation.

### Required checks

- clean dependency resolution;
- no known dependency vulnerabilities in the declared manifests;
- formatting and import-order checks;
- unit-test collection succeeds;
- YAML and JSON parse successfully;
- Markdown fences are balanced;
- contract references resolve;
- claims reference known evidence identifiers;
- no secrets or lease tokens are committed;
- no customer-confidential material is present.

### Pass criteria

All blocking checks pass with no unexplained exception.

## Gate V1: local semantic correctness

### Objective

Verify the process-local idempotency contract.

### Required scenarios

- stable hashing ignores object-key order;
- payload changes alter the request hash;
- first valid request creates one pending record;
- duplicate pending request receives no lease;
- same key and different payload returns `CONFLICT`;
- completed operation returns `REPLAY`;
- failed operation returns `FAILED`;
- same key remains isolated across tenants;
- expired pending operation is reacquired with a rotated lease;
- stale worker cannot complete a newer attempt;
- worker cannot complete after lease expiry;
- terminal operation cannot be completed twice;
- completed operation remains terminal after pending TTL;
- non-positive TTL is rejected;
- naive clocks are rejected.

### Pass criteria

- all required tests pass;
- no duplicate domain effect is observed;
- no stale or expired transition succeeds;
- no terminal state is rewritten.

## Gate V2: multi-process authoritative convergence

### Objective

Verify that independent processes converge on one durable authoritative
idempotency decision.

### Preconditions

- a durable registry adapter exists;
- schema and uniqueness constraints are versioned;
- test isolation and cleanup are defined;
- transaction retry behaviour is observable.

### Required scenarios

- concurrent first submission from multiple processes;
- concurrent same-key/same-hash submission;
- concurrent same-key/different-hash submission;
- worker termination after lease acquisition;
- reacquisition after lease expiry;
- stale completion after another process reacquires;
- process restart during pending state;
- database transaction retry;
- database connection interruption;
- duplicate delivery through two transport adapters;
- clock skew within the supported bound;
- schema migration with pending and terminal records present.

### Pass criteria

- exactly one authoritative acquisition is granted per attempt;
- all other same-request contenders observe a non-executing decision;
- conflicting requests do not execute;
- stale workers are fenced;
- terminal records remain stable;
- no duplicate protected effect occurs;
- evidence identifies the winning attempt and rejected contenders.

### Claim unlocked

Only after this gate passes may the product claim distributed idempotency for the
validated adapter and topology.

## Gate V3: admission and capacity control

### Objective

Verify that resource allocation remains bounded under duplicate and unique-key
pressure.

### Required scenarios

- duplicate storm against one key;
- high-cardinality unique-key storm;
- one noisy tenant;
- multiple tenants sharing global capacity;
- payloads at, below and above the maximum size;
- pending-operation saturation;
- queue saturation;
- provider-concurrency saturation;
- status polling storm;
- replay storm against completed records;
- conflict storm using one key and changing hashes;
- slow consumer or backpressured downstream;
- storage-latency increase;
- memory-pressure threshold crossing.

### Required observations

- admission decision before durable allocation where policy requires it;
- bounded pending records;
- bounded queue depth;
- bounded provider calls;
- explicit rejection reason codes;
- tenant fairness or configured priority;
- no unbounded retry loop;
- recovery after load returns below the safe threshold.

### Pass criteria

- configured hard limits are not exceeded beyond documented tolerance;
- memory and storage growth remain bounded;
- rejected unique keys do not create authoritative execution records unless the
  policy explicitly requires a minimal rejection record;
- one tenant cannot exhaust reserved capacity for another tenant;
- the system recovers without manual data repair.

### Claim unlocked

Only after this gate passes may the product claim bounded admission and capacity
control for the validated configuration.

## Gate V4: provider flapping and retry containment

### Objective

Verify that unstable dependencies do not cause oscillation, duplicate effects or
retry amplification.

### Provider fault profiles

- deterministic timeout;
- intermittent timeout;
- connection reset;
- HTTP 429 or equivalent throttling;
- retryable server error;
- non-retryable client error;
- malformed response;
- delayed success;
- success after caller timeout;
- alternating success and failure;
- regional endpoint instability;
- provider returns inconsistent operation status.

### Required scenarios

- single failure while healthy;
- consecutive failures crossing degraded threshold;
- failures crossing quarantine threshold;
- probes during quarantine;
- one successful probe after repeated failure;
- consecutive successes crossing recovery threshold;
- progressive traffic restoration;
- failure during recovery;
- controlled failback;
- retry-budget exhaustion;
- simultaneous flapping of two dependencies;
- provider timeout after irreversible external success.

### Pass criteria

- one failure does not cause immediate quarantine unless explicitly configured;
- one success does not restore full traffic;
- retry budgets are enforced;
- backoff and jitter are observable;
- quarantine stops normal traffic while allowing controlled probes;
- recovery is progressive;
- provider-state transitions are evidenced separately;
- execution-state integrity remains intact;
- no recursive retry storm occurs.

### Claim unlocked

Only after this gate passes may the product claim provider-flapping containment
for the validated provider policy.

## Gate V5: failover, recovery and evidence

### Objective

Verify that failover and recovery preserve one authoritative history.

### Required scenarios

- active process failure;
- worker-pool restart;
- durable-backend failover;
- message-broker redelivery after consumer restart;
- delayed outbox publication;
- duplicate outbox delivery;
- evidence sink interruption;
- partial regional isolation;
- recovery from backup or replica where supported;
- policy rollback;
- configuration rollback;
- failover while provider is degraded;
- failback after recovery.

### Pass criteria

- the recovered system uses the same authoritative execution history;
- no completed operation is re-executed;
- pending operations follow an explicit recovery policy;
- evidence gaps are detected and reconciled;
- outbox redelivery does not duplicate the protected effect;
- failover and failback are explicit, observable and reversible;
- recovery point and recovery time are measured rather than assumed.

### Claim unlocked

Only after this gate passes may the product claim failover and recovery for the
validated topology and recovery procedure.

## Gate V6: controlled soak and operational review

### Objective

Verify sustained behaviour under a realistic but authorized pre-production
workload.

### Required execution

- representative traffic mix;
- sustained run duration defined before execution;
- normal, burst and degraded periods;
- scheduled provider fault injection;
- scheduled worker restart;
- retention and purge jobs active;
- metrics, logs and traces enabled;
- operator runbook exercised;
- alert routing tested;
- rollback procedure tested.

### Pass criteria

- no invariant breach;
- no unexplained duplicate effect;
- no silent evidence loss;
- no unbounded resource trend;
- latency remains within the predeclared test objective;
- operator actions match the runbook;
- all exceptions are classified;
- post-run reconciliation succeeds.

### Claim unlocked

Passing V6 supports a controlled pre-production readiness statement for the
validated configuration. It does not establish universal production readiness or
an SLA.

## 9. Adversarial scenario catalogue

Scenario definitions must live in `tests/resilience/scenarios.yaml` and include a
stable identifier.

The minimum catalogue is:

```text
IDEMP-001  same key, same hash, concurrent local submissions
IDEMP-002  same key, different hash
IDEMP-003  expired lease and reacquisition
IDEMP-004  stale completion after reacquisition
IDEMP-005  terminal replay
DIST-001   same key across multiple processes
DIST-002   transaction retry during acquisition
DIST-003   process death after acquisition
ADMIT-001  duplicate storm
ADMIT-002  unique-key flood
ADMIT-003  noisy tenant
ADMIT-004  global pending saturation
ADMIT-005  oversized payload
ADMIT-006  queue saturation
PROV-001   intermittent timeout
PROV-002   consecutive failures and quarantine
PROV-003   premature recovery attempt
PROV-004   failure during progressive recovery
PROV-005   retry-budget exhaustion
PROV-006   timeout after external success
FAIL-001   worker restart with pending operations
FAIL-002   durable-registry failover
FAIL-003   broker redelivery after restart
FAIL-004   delayed outbox publication
FAIL-005   evidence sink interruption
RECOV-001  controlled failback
RET-001    purge after idempotency horizon
RET-002    purge blocked by legal or evidence hold
RET-003    terminal record retained through duplicate window
CLAIM-001  unsupported claim rejected by registry validation
```

## 10. Fault-injection controls

Fault injection must be deterministic where possible.

Each injected fault must record:

- fault identifier;
- start time;
- end time;
- target component;
- affected percentage or request count;
- latency, error or disconnection profile;
- seed;
- expected state transition;
- actual state transition;
- cleanup result.

Fault injection must support an immediate stop mechanism.

A fault must not be left active after the run.

## 11. Stop conditions

A validation run must stop automatically when any of the following occurs:

- duplicate irreversible effect;
- tenant-boundary violation;
- stale worker commits a terminal transition;
- terminal record is overwritten;
- evidence contains a secret or raw lease token;
- memory, CPU, storage or connection use exceeds the authorized ceiling;
- queue depth exceeds the hard safety bound;
- retry amplification exceeds the configured budget;
- external provider receives traffic outside the authorization envelope;
- cleanup cannot be guaranteed;
- operator activates the emergency stop.

Stopping the run is a successful safety action, not a test failure concealment.

## 12. Evidence bundle

Each validation run must produce an immutable or tamper-evident bundle containing:

```text
manifest.json
scenario.yaml
configuration.redacted.json
policy-snapshot.json
commit.txt
environment.txt
result.json
metrics-summary.json
invariant-results.json
fault-timeline.json
logs/
traces/
reports/
checksums.sha256
```

The manifest must include:

- bundle identifier;
- scenario identifier and version;
- commit SHA;
- start and end timestamps;
- operator;
- pass, fail or aborted result;
- failed invariants;
- known limitations;
- hash of each included artifact.

Raw lease tokens, credentials, personal data and customer-confidential payloads
must be excluded or irreversibly redacted.

## 13. Reconciliation

Every run that creates authoritative records or simulated domain effects must end
with reconciliation.

Reconciliation must compare:

- accepted executions;
- authoritative idempotency records;
- domain effects;
- outbox records;
- emitted evidence events;
- replay responses;
- rejected conflicts;
- purged records;
- unresolved pending operations.

The run must fail if counts or causal references cannot be reconciled within the
predeclared rules.

## 14. Claim registry integration

The file `claims/claims.yaml` is the authoritative repository index for public
technical claims.

Each claim must include:

- claim identifier;
- statement;
- status;
- scope;
- required gate;
- evidence references;
- limitations;
- last validation date;
- repository commit;
- owner.

Allowed status values are:

```text
PROPOSED
IMPLEMENTED_UNVERIFIED
VERIFIED_LOCAL
VERIFIED_DISTRIBUTED
VERIFIED_PREPRODUCTION
DEPRECATED
REVOKED
```

A claim must be downgraded or revoked when:

- its evidence is invalidated;
- the implementation changes materially;
- the supporting test no longer passes;
- the validated environment is no longer representative;
- a new failure contradicts the statement.

## 15. Pull-request validation requirements

A pull request that changes execution semantics, retention, admission, provider
health, recovery or evidence must include:

- the affected contract or ADR reference;
- updated scenarios;
- updated tests;
- claim impact;
- backward-compatibility analysis;
- migration impact;
- rollback plan;
- security impact;
- local validation output.

Changes that alter a public contract must not be merged as incidental refactoring.

## 16. CI integration sequence

The recommended CI sequence is:

```text
1. dependency and secret checks
2. formatting and static checks
3. unit and contract tests
4. local semantic resilience tests
5. scenario-schema validation
6. claim-registry consistency check
7. optional durable-adapter integration tests
8. evidence-bundle publication for authorized branches
```

Distributed, load and fault-injection tests should run in isolated workflows with
explicit resource and cost controls.

They must not run automatically against shared or production infrastructure.

## 17. Promotion decision

A promotion decision must answer:

1. Which exact capability is being promoted?
2. Which gate has passed?
3. Which topology and configuration were validated?
4. Which evidence bundle supports the decision?
5. Which limitations remain?
6. Which rollback path exists?
7. Which public claim becomes permitted?

A broad statement such as "resilient", "production-ready" or "exactly once" is
not an acceptable promotion decision without a narrower validated scope.

## 18. Explicit non-goals

This plan does not validate or claim:

- immunity from volumetric DDoS attacks;
- RF anti-jamming capability;
- universal exactly-once execution;
- legal or regulatory compliance;
- guaranteed regional availability;
- a contractual SLA;
- safety for untested workloads;
- correctness of third-party systems;
- production readiness outside the validated configuration.

## 19. Initial execution order

The first implementation sequence is:

1. preserve V1 as the local semantic baseline;
2. add `tests/resilience/scenarios.yaml`;
3. add `claims/claims.yaml`;
4. add schema validation for both files;
5. implement a durable registry adapter behind the existing contract;
6. execute V2 with multiple processes;
7. implement admission controls;
8. execute V3 under bounded load;
9. implement provider-health state and hysteresis;
10. execute V4 fault profiles;
11. implement evidence reconciliation and outbox validation;
12. execute V5;
13. run an authorized V6 soak.

Until these gates pass, the repository must continue to state that the verified
boundary is process-local and that distributed, capacity, flapping and failover
capabilities remain targets.
