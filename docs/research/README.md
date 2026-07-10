# External Research Governance

Product research is maintained outside this repository in a controlled
working directory named:

`CCO_RESEARCH_ROOM`

The external directory may contain:

- primary technical sources;
- hypotheses and manual web research;
- private commercial strategy;
- buyer and investment context;
- raw AI-assisted brainstorming;
- unverified claims;
- draft diagrams and validation plans.

None of those materials becomes an authoritative product statement merely
because it exists in the research directory.

## Promotion rule

Material may enter this repository only after explicit review and
classification.

Approved destinations are:

- architectural decisions: `docs/adr/`
- execution and governance contracts: `docs/contracts/`
- threat models: `docs/security/`
- validation procedures: `docs/testing/`
- public product positioning: `README.md`
- verified product claims: `claims/claims.yaml`

## Prohibited repository material

Do not commit:

- private buyer or investor strategy;
- personal or confidential correspondence;
- raw AI conversation logs;
- speculative performance figures;
- unverified legal or regulatory conclusions;
- third-party confidential information;
- customer-specific or mission-specific material without authorization.

## Evidence states

Every technical statement must be classified as one of:

- implemented
- verified
- target
- roadmap
- prohibited

Research remains non-authoritative until it is promoted through a reviewed
pull request.
