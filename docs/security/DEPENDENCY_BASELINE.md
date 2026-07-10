# Python Dependency Security Baseline

- **Date:** 2026-07-10
- **Status:** Baseline under remediation
- **Product state:** Under construction and validation

## Initial observation

GitHub Dependabot initially reported 86 open alerts:

- 2 critical;
- 35 high;
- 35 moderate;
- 14 low.

This count included repeated findings across multiple requirement manifests
and findings from a generated security-tool environment that did not represent
the deployed application.

## Authoritative runtime manifest

`/requirements.txt` is the only authoritative Python runtime manifest.

It is consumed by:

- the Docker image build;
- the Vercel installation command;
- local runtime installation;
- dependency vulnerability auditing.

## Removed duplicate or misleading manifests

The following files were removed:

- `/api/requirements.txt`;
- `/requirements-for-safety.txt`.

`api/requirements.txt` duplicated the runtime dependency set.

`requirements-for-safety.txt` represented a previously resolved tooling
environment containing unrelated direct and transitive dependencies. It was
not a valid product runtime manifest and produced misleading repeated alerts.

## Development dependencies

Testing and quality tools are not installed into the runtime image.

The existing `/requirements-dev.txt` remains a development-only manifest and
will be normalized in a separate change after the runtime baseline is known.

## Current audit policy

Bandit remains blocking for application-code findings at the configured
severity.

The Python dependency audit is temporarily report-only while inherited
runtime findings are identified and remediated.

The audit must become blocking after:

1. the authoritative runtime dependency tree is resolved;
2. direct vulnerable dependencies are upgraded;
3. remaining transitive findings are evaluated;
4. any exception is documented with advisory identifier, applicability,
   compensating controls, owner and review date.

## Integrity rules

- Vulnerabilities must not be manually dismissed merely to reduce the count.
- A finding may be accepted only through a documented risk decision.
- Runtime and development findings must be classified separately.
- A green CI result must not be described as a zero-vulnerability result while
  the dependency audit remains report-only.
- Spanner integration, production readiness, regulatory compliance and
  exactly-once execution are not implied by this baseline.
