# ehrlab DirtyCSV — Project Book

## Purpose

`dirtycsv` is now the standalone project under profile `ehrlab`.

The earlier `dataprocess project -> dirtycsv work tree` hierarchy has been removed for dashboard/manageability. Future data-processing work can be added later as separate ehrlab projects or explicitly linked sibling projects.

## Scope

### Included

- **ehrlab**: `19` sessions assigned to project `dirtycsv`.
- These include the governance/provenance/adapter safety scaffolding plus the concrete dirty CSV temporal-table delivery request.

### Excluded

- `20260426_171423_4714c0` remains the cross-profile `export_sanitized` boundary seed for `harness-self-governance`.
- `general` sessions remain under `harness-self-governance`.
- `default/root` sessions remain excluded.

## Project interpretation

`dirtycsv` should be shown in the dashboard as a first-class project node:

```text
profile: ehrlab
└── project: dirtycsv
```

Do not render `ehrlab` as the only visible node when the user selects profile `ehrlab`; the project node must be visible and connected to its profile.

## Phases

| Phase | Date range | Meaning |
|---|---|---|
| bootstrap and safety scaffolding | 2026-04-26 | establish safe ehrlab-local control surface |
| adapter implementation and hardening | 2026-04-26 | make the processing path safe and reviewable |
| dirtycsv delivery | 2026-04-27 | explicit dirty CSV temporal-table/script/doc task |


## Compiled project summary contract

A project summary node is not just a taxonomy label. It must answer:

- **Purpose** — why the project exists.
- **Actions** — what was done across the compiled sessions.
- **Results** — what durable outputs/decisions now exist.
- **Cautions** — privacy, boundary, and maintenance constraints.
- **Evidence** — canonical docs/artifacts to read instead of raw sessions.
- **Key skills/tools** — procedural capabilities and executable tools that governed or enabled the project.

For `dirtycsv`, the canonical machine-readable summary is:

- `docs/examples/agent-memory-graph/ehrlab-dirtycsv/compiled-session-project-scope.json`

## Dashboard retrieval rule

For user-facing dashboard views, prioritize:

1. profile
2. project
3. project summary / sessions
4. safety/router/archive internals only as secondary diagnostics

## Machine-readable companions

- `docs/examples/agent-memory-graph/ehrlab-dirtycsv/project-session-scope.json`
- `docs/examples/agent-memory-graph/ehrlab-dirtycsv/compiled-session-project-scope.json`
