# Harness Self Governance — Project Book

## Purpose

This file is the human-readable **project handbook** compiled from the session corpus for project `harness-self-governance`.

It does two things at once:

1. defines **project scope** for session-to-project compilation;
2. preserves **phase boundaries** so future retrieval can distinguish `v1.0`, `v1.1`, and `v2.0` while still treating them as one project lineage.

## Scope decision used for this compilation

### Included

- **general**: all `78` sessions are treated as part of `harness-self-governance`, per user instruction.
- **ehrlab**: only **1** boundary-governance session is imported into this project compilation:
  - `20260426_171423_4714c0` — `mode=export_sanitized profile=ehrlab`

### Excluded

- **ehrlab**: the remaining `19` sessions are excluded from this project **because they belong to the separate ehrlab `dirtycsv` project**, not because they are irrelevant.
- **default/root**: `22` raw root sessions exist locally, but they are excluded from this project compilation by scope rule.

## Why the ehrlab seed is kept

The retained ehrlab session is not included as a feature-delivery session. It is included because it captures the **cross-profile governance contract**:

- `ehrlab` exports **sanitized capability / health summaries**;
- `general` consumes those summaries for **governance audit**;
- raw sensitive material must **not** cross the profile boundary.

That boundary is part of the harness-self-governance architecture, so it belongs in the project book.

## Phase model

`harness-self-governance` is **one project** with **phase-separated history**.

| Phase | Date range | Role in project lineage | Anchor sessions |
|---|---|---|---|
| Cross-profile bootstrap | 2026-04-26 | Establish `general` / `ehrlab` governance split, review bundle flow, and session ledger groundwork | `20260426_171927_83a85a`, `20260426_181237_540979` |
| v1.0 | 2026-04-26 → 2026-04-27 | Local closed-loop governance baseline: identity gates, approval gates, provenance state, release-readiness and operational governance | `20260427_123812_20e432`, `20260427_163949_a426ef`, `771b363d6790` |
| v1.1 | 2026-04-27 | Reviewed action layer: reviewed proposal manifest, schema validation, template validation, adapter report, v1.1 RC | `20260427_183159_9fbae8`, `e7e1765c4093` |
| v2.0 | 2026-04-27 → 2026-04-28 | Graph/dashboard/router/memory-graph phase: dual graph, logs UX, profile-project-lineage, context router, archive bootstrap | `8cf7b5d3e23b`, `20260428_173942_9e3863`, `701d40e9621c` |

## Phase summaries

### 1. Cross-profile bootstrap

This phase established the governance architecture before the main versioned pipeline work stabilized.

Key outcomes:
- `general` became the governance hub.
- `ehrlab` was treated as a protected domain-local profile.
- shared schema / patch-review / final-review / apply / verify flows were trialed as governance mechanics.
- session-ledger work began, which later enabled manual session compilation and archive thinking.

Interpretation rule:
- This phase is part of the same project, but it should be read as **architectural governance groundwork**, not yet as the polished release baseline.

### 2. v1.0 — local governance baseline

This is the first stable project baseline.

Key outcomes:
- built the local closed-loop governance pipeline;
- enforced git identity checks and approval gates;
- added provenance current-state outputs and evidence indexing;
- established read-only / audit-first governance posture;
- added operational governance around session cleanup, autopilot policy, continuation rules, and artifact-based state.

Canonical interpretation:
- `v1.0` is where the project became a real reusable governance harness instead of a loose experiment.

### 3. v1.1 — reviewed action layer

This is the control-layer refinement phase between v1.0 and v2.0.

Key outcomes:
- reviewed proposal manifest and schema versioning;
- proposal validation command;
- template validation;
- adapter report;
- explicit reviewed-action / proposal-only safety posture;
- v1.1 RC pipeline with clearer artifact separation.

Canonical interpretation:
- `v1.1` is a **safety and structure upgrade**, not a separate product.

### 4. v2.0 — graph, dashboard, router, compiled memory

This phase turns the governance harness into a graph-driven system with local observability and memory protocol.

Key outcomes:
- read-only graph/dashboard foundation;
- graph + logs interaction iteration;
- dense-graph readability improvements;
- profile / project / lineage model;
- dual graph split: Governance Graph vs Agent Memory Graph;
- graph-governed context loading and budgeted router work;
- manual archive bootstrap with curated compiled-session fixtures;
- project knowledge moved from placeholder memory into real Memory Graph structure.

Canonical interpretation:
- `v2.0` is still the same project, but now the control plane becomes **graph-native and archive-aware**.

## Retrieval rule for future reference

When using this project book as retrieval context:

1. first resolve **phase** (`cross-profile bootstrap`, `v1.0`, `v1.1`, `v2.0`);
2. then resolve whether the question is about:
   - pipeline / release baseline,
   - proposal/review safety,
   - graph/dashboard/router,
   - or cross-profile governance boundary;
3. only then jump to detailed session artifacts.

This avoids mixing:
- `v1.0 baseline rules`
- `v1.1 reviewed-action rules`
- `v2.0 graph-native protocol rules`

into one undifferentiated narrative.

## Machine-readable companions

- `docs/examples/agent-memory-graph/harness-self-governance/project-session-scope.json`
- `docs/examples/agent-memory-graph/harness-self-governance/compiled-session-project-scope-and-phase-boundary.json`
- `docs/examples/agent-memory-graph/harness-self-governance/compiled-session-ehrlab-export-sanitized-boundary.json`

## Related project split

The excluded ehrlab sessions are not discarded. They are tracked as the separate ehrlab project `dirtycsv`:

- project book: `docs/projects/ehrlab-dirtycsv-project-book.md`
- project scope: `docs/examples/agent-memory-graph/ehrlab-dirtycsv/project-session-scope.json`
- project compiled session: `docs/examples/agent-memory-graph/ehrlab-dirtycsv/compiled-session-project-scope.json`

Dashboard rule: selecting profile `ehrlab` must show project `dirtycsv`, not only the `ehrlab` profile node.

## Direct source anchors already present in compiled-session examples

Existing curated examples still matter and should be read together with this project book:

- `compiled-session-v1-baseline.json`
- `compiled-session-v1-1-baseline.json`
- `compiled-session-v2-dashboard-architecture.json`
- `compiled-session-frontend-visual-qa.json`
- `compiled-session-profile-project-lineage.json`
- `compiled-session-global-agent-memory-graph.json`
- `compiled-session-context-router.json`

## Practical reading order

Recommended human reading order:

1. this project book;
2. `compiled-session-project-scope-and-phase-boundary.json`;
3. `compiled-session-v1-baseline.json`;
4. `compiled-session-v1-1-baseline.json`;
5. `compiled-session-v2-dashboard-architecture.json`;
6. `compiled-session-profile-project-lineage.json`;
7. `compiled-session-global-agent-memory-graph.json`;
8. `compiled-session-context-router.json`;
9. `compiled-session-ehrlab-export-sanitized-boundary.json`.
