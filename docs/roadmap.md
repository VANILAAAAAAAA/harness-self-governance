# Roadmap

## v1.0 — pre-release read-only adapter

Goals:

- read-only graph and event validation;
- dependency-closed subgraph retrieval;
- factor-based safety review;
- sanitized dry-run export;
- capacity-only storage audit;
- proposal-only raw archive planning;
- public-source hardening and documentation.

Non-goals:

- apply;
- delete;
- quarantine execution;
- rehydrate execution;
- provenance upgrade;
- graph/events mutation;
- release publishing automation.

## v1.1 — diagnostics and ergonomics

Possible additions:

- richer schema diagnostics;
- clearer machine-readable reports;
- stronger fixture generation;
- better packaging checks;
- more granular policy explanations.

v1.1 should preserve the v1.0 read-only/proposal-only safety boundary.

## v2.0 — reviewed apply-capable designs

Any apply-capable workflow belongs in a future major design and must include:

- explicit human approval;
- manifest generation;
- hash verification;
- rollback plan;
- independent final review;
- no raw-sensitive export by default.
