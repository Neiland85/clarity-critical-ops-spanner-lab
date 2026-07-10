# Clarity Critical Operations

### Deterministic execution and anti-flapping control for critical integrations

Clarity Critical Operations is a proprietary execution-control product under
construction and validation by **Clarity Structures Digital S.L.**

It is designed for financial and non-financial systems that require controlled
idempotency, deterministic execution contracts, operational traceability,
duplicate suppression and recovery from unstable integration behaviour.

> **Current maturity:** validated technical core with an in-memory reference
> implementation. Google Cloud Spanner integration is the next architectural
> milestone and is not yet complete.

---

## The problem

Critical operations are frequently exposed to:

- duplicate client submissions;
- retry storms;
- reconnect loops;
- repeated callbacks;
- concurrent workers;
- delayed responses;
- transport instability;
- contradictory retries;
- uncertain in-flight execution state.

These behaviours can create integration flapping: the same business intention
crosses the system boundary repeatedly or inconsistently and risks producing
multiple effects.

Clarity Critical Operations addresses that problem through a strict execution
contract and an authoritative idempotency decision layer.

---

## Validated capabilities

The current reference implementation includes:

- versioned `ExecutionEnvelope` contracts;
- canonical request hashing;
- tenant-scoped idempotency;
- duplicate detection;
- stable replay of completed operations;
- conflict detection for reused keys with different requests;
- explicit `PENDING`, `COMPLETED`, `FAILED` and `EXPIRED` states;
- bounded execution leases;
- controlled lease reacquisition;
- monotonically increasing execution attempts;
- stale-worker fencing;
- deterministic pending-operation expiry;
- validation of incompatible state transitions;
- automated concurrency and recovery tests.

The current `main` baseline passes 75 automated tests.

---

## Anti-flapping contract

Within the defined idempotency boundary, the product is designed to provide the
following behaviour:

| Condition | Expected decision |
|---|---|
| Same scope, key and request | Pending response or stable replay |
| Same scope and key, different request | Conflict |
| Concurrent acquisition | One active execution lease |
| Expired in-flight execution | Controlled reacquisition |
| Previous worker uses an obsolete lease | Fenced as stale |
| Completed execution is retried | Existing response is replayed |

This capability mitigates integration flapping and duplicate execution. It does
not claim to eliminate every network fault, third-party outage or failure
outside the defined transactional boundary.

The project does not currently claim universal end-to-end exactly-once
delivery.

---

## Architecture

```text
Client / Partner / External System
                |
                v
Load Balancer / Ingress / Edge Gateway
                |
                v
ExecutionEnvelope validation
                |
                v
Security integration boundary
                |
                v
Authoritative idempotency decision
                |
                v
Domain operation
                |
                v
Transactional outbox / operational evidence
                |
                v
Events / projections / WebSockets / webhooks
The edge may participate in duplicate suppression, but it is not the
authoritative source of execution truth.

WebSockets, webhooks, caches and load-balancer affinity are transports or
projections. They are not treated as the authoritative decision record.

Google Cloud Spanner target

Google Cloud Spanner is the intended authoritative persistence layer for:

idempotency decisions;
execution leases;
domain writes;
transactional outbox records;
operational evidence references.

The target design is to coordinate the idempotency decision, business write and
outbox/evidence record inside a defined transactional boundary.

The production Spanner adapter and distributed failure validation remain
roadmap work.

Candidate integration adapters

The architecture can incorporate external adapters such as:

telecommunications risk signals, including SIM-swap or device-location
checks;
API gateways and WAF services;
event-stream platforms;
Rust or WebAssembly domain components;
partner APIs, webhooks and WebSocket transports.

Telefónica Open Gateway, Cloudflare, Redpanda, Rust and WebAssembly are
integration targets or architectural options. Their mention does not imply
that they are currently integrated, contracted, required or validated.

External risk signals are supporting inputs. They do not replace the
authoritative execution decision.

Evidence levels

Project statements are separated into four levels:

Implemented — present in the repository.
Verified — covered by tests, logs or generated evidence.
Target architecture — formally designed but not yet integrated.
Industrialization roadmap — requires further implementation and
operational validation.

The project does not currently claim:

production readiness;
regulatory certification;
universal exactly-once execution;
completed Spanner integration;
absolute immutability;
immunity from all forms of flapping;
guaranteed availability of third-party infrastructure.
Current roadmap
Remediate the authoritative runtime dependency baseline.
Define the persistence-port contract.
Implement the Google Cloud Spanner adapter.
Coordinate idempotency, domain write and outbox/evidence transactionally.
Add distributed concurrency and failure-recovery tests.
Integrate HTTP, WebSocket and webhook transports over the same envelope.
Establish operational telemetry, SLOs and controlled deployment evidence.
Produce separate regulatory and sector-specific mappings where required.
Local validation
python3.12 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m pytest -q

Formatting:

./.venv/bin/python -m black --check app
./.venv/bin/python -m isort --check-only app
Security status

The repository includes quality, source-security and container-security
workflows.

Dependency auditing currently records the inherited baseline while remediation
is in progress. A green workflow must not be interpreted as evidence that the
dependency baseline contains zero known vulnerabilities.

CodeQL execution remains capability-gated according to repository availability.

Intellectual property and commercial use

This is proprietary software.

Repository access does not grant permission to use, execute, reproduce, modify,
distribute, sublicense, commercialize, deploy or create derivative works.

Evaluation, pilots, commercial licensing, strategic partnerships, investment
and acquisition discussions require a separate written agreement with
Clarity Structures Digital S.L.

See:

LICENSE
NOTICE.md
COMMERCIAL_EVALUATION_AND_LICENSING.md
CONTRIBUTING.md

Commercial contact:

Clarity Structures Digital S.L.
Neil Muñoz Lago
admin@claritystructures.com
+34 613 722 441
