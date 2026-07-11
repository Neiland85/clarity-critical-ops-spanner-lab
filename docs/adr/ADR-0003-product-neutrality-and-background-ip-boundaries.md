# ADR-0003: Product neutrality and background-IP boundaries

- Status: Proposed
- Date: 2026-07-11
- Product: Clarity Critical Operations
- Technical class: Provider-Neutral Critical Execution Control Plane

## Context

Clarity Critical Operations must remain a reusable execution-control product,
not an implementation detail defined by one customer, sector, integrator,
datastore, network or deployment.

Customer projects may require adapters, policies, protocol mappings,
configuration and deployment assets. Those deliverables must not silently
redefine the reusable core or transfer generalizable technology.

The repository must also distinguish authoritative product material from
external research, private commercial strategy, raw AI output and unverified
claims.

## Decision

### Product identity

Clarity Critical Operations controls the admission, execution, repetition,
recovery, degradation and evidence of critical operations.

Its purpose is to prevent retries, redeliveries, reconnections, concurrency,
failovers, unstable dependencies or hostile load from producing duplicated,
contradictory or unreconstructable effects.

The product is provider-neutral and sector-neutral.

### Reusable core

The reusable product core includes:

- versioned execution contracts;
- tenant-scoped idempotency semantics;
- leases, attempts and stale-worker fencing;
- replay and conflict decisions;
- admission and capacity contracts;
- provider-health and anti-flapping state machines;
- evidence and causal-reconstruction models;
- provider-neutral ports;
- validation procedures and claim-governance rules.

### Background technology

Generalizable mechanisms, contracts, patterns, documentation and test methods
are Background Technology.

The repository licence and notices reserve commercial exploitation rights.
The complete legal chain of title must be documented privately and must not be
inferred solely from this ADR.

### Customer-specific work

Customer-specific work may include:

- mission or sector adapters;
- deployment configuration;
- protocol and interface mappings;
- customer policies;
- data transformations;
- integration scripts;
- environment-specific acceptance tests.

Customer-specific work does not redefine the product or transfer reusable
Background Technology unless an explicit written agreement states otherwise.

### Provider neutrality

General contracts use provider classes rather than company names:

- transactional datastore;
- network-trust provider;
- edge-security provider;
- event-stream provider;
- connectivity provider;
- critical-system integrator;
- mission-system adapter.

Specific providers or customers may appear only in controlled material such
as NDAs, evaluation annexes, statements of work, adapter specifications,
pilots or transaction agreements.

### Documentation authority

External research is non-authoritative.

Material becomes authoritative only after review and promotion into:

- `docs/adr/`;
- `docs/contracts/`;
- `docs/security/`;
- `docs/testing/`;
- `claims/claims.yaml`;
- product source code and tests.

Raw AI logs, private strategy, unsupported figures and confidential customer
material must remain outside the repository.

## Consequences

- Providers remain replaceable behind stable ports.
- Customer funding does not silently transfer the reusable core.
- Specific integrations cannot redefine the public product.
- Claims must remain scoped to reproducible evidence.
- Incompatible contracts require explicit versioning.
- ADR-0001 remains a historical implementation baseline.

## Non-decisions

This ADR does not:

- select a production datastore;
- grant a commercial licence;
- transfer intellectual-property title;
- define a customer-specific integration;
- claim industrial readiness;
- guarantee protection from volumetric network attacks.
