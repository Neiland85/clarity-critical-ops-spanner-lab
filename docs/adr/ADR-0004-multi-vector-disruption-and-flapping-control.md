# ADR-0004: Multi-vector disruption and flapping control

- Status: Proposed
- Date: 2026-07-11
- Product: Clarity Critical Operations

## Context

Critical operations may be affected simultaneously by:

- retries and redeliveries;
- duplicate or conflicting submissions;
- reconnect storms;
- stale workers;
- application floods;
- provider timeouts;
- oscillating dependencies;
- faulty failover;
- event redelivery and reordering;
- partial network or regional degradation.

Idempotency alone prevents some repeated effects, but it does not provide
admission control, capacity protection or provider-flapping containment.

Execution state and provider-health state must remain separate.

## Decision

### Layered responsibility

Clarity uses the following control stack:

```text
NETWORK EDGE
carrier filtering / DDoS mitigation / WAF
        |
ADMISSION CONTROL
quotas / rate limits / load shedding / payload limits
        |
EXECUTION CONTROL
idempotency / leases / fencing / replay policy
        |
RESILIENCE CONTROL
retry budgets / backpressure / bulkheads / hysteresis
        |
DOMAIN CORE
one authorized business effect
        |
EVIDENCE
outbox / hashes / causal trace / reconstruction
```

Network-capacity protection remains the responsibility of carriers, edge
providers and dedicated mitigation systems.

Clarity controls execution consistency after traffic reaches the defined
application boundary.

### Execution-state machine

The current execution states remain:

- `PENDING`;
- `COMPLETED`;
- `FAILED`;
- `EXPIRED`.

The current decisions remain:

- `CREATED`;
- `REACQUIRED`;
- `PENDING`;
- `REPLAY`;
- `CONFLICT`;
- `FAILED`.

`COMPLETED` and `FAILED` are terminal in version 1.

A stale lease holder cannot complete or fail a newer attempt.

### Provider-health state machine

Provider health is represented separately:

```text
UNKNOWN
   |
PROBING
   |
HEALTHY
   |
DEGRADED
   |
QUARANTINED
   |
RECOVERING
   |
HEALTHY
```

A provider transition requires policy-defined evidence.

The health policy must support:

- consecutive-failure thresholds;
- consecutive-success thresholds;
- observation windows;
- minimum state duration;
- cooldown periods;
- retry budgets;
- exponential backoff;
- jitter;
- progressive recovery;
- controlled failback.

A single failure must not cause immediate quarantine.

A single successful response must not immediately restore full traffic.

### Admission before allocation

A storm of unique idempotency keys must be rejected before creating
unbounded durable or in-memory state.

Admission policy must be able to constrain:

- payload size;
- new keys per window;
- pending operations per tenant;
- concurrent acquisitions per tenant;
- operations per actor;
- global pending operations;
- external provider calls;
- inline result size.

### Retry containment

Retries must be:

- bounded;
- classified;
- delayed with backoff and jitter;
- charged against a retry budget;
- prevented from producing recursive amplification.

External irreversible effects must not occur inside a transaction callback
that may be retried.

### Evidence

Every authoritative transition must preserve:

- operation reference;
- attempt;
- decision;
- reason code;
- policy snapshot identifier and hash;
- correlation and causation references;
- occurrence and recording timestamps;
- evidence reference.

Provider-health transitions must be evidenced independently from execution
transitions.

## Claim boundary

Currently verified:

- process-local idempotency semantics;
- conflict detection;
- expiry and reacquisition;
- lease rotation;
- stale-worker fencing;
- terminal-state protection;
- limited process-local concurrency.

Not yet verified:

- sustained industrial load;
- distributed idempotency;
- provider hysteresis;
- load shedding;
- multi-process failover;
- regional recovery;
- multi-vector disruption containment.

These capabilities remain targets until their validation gates produce
reproducible evidence.

## Consequences

- Provider instability cannot silently redefine execution state.
- Admission and execution remain separate decisions.
- Unique-key floods require capacity controls beyond idempotency.
- Failover must use the same authoritative execution registry.
- Public claims cannot exceed the tested boundary.
- Network DDoS, RF anti-jamming and universal exactly-once guarantees remain
  outside the product claim.

## Non-goals

This ADR does not claim:

- DDoS immunity;
- anti-jamming capability;
- exactly-once execution end to end;
- production readiness;
- guaranteed regional availability;
- resistance to untested attack volumes.
