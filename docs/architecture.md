# Architecture

`graph-harness-maintain` is a thin adapter for graph-governed agent-harness maintenance.

## Design principles

- Keep graph records external and read-only.
- Retrieve dependency-closed subgraphs instead of isolated top-k nodes.
- Treat provenance, policy, and safety gates as first-class control-plane inputs.
- Emit reports and proposals rather than mutating protected state.
- Keep v1.0 small enough to audit.

## Core modules

- `schema.py`: typed graph, edge, event, sidecar, and policy data structures.
- `store.py`: read-only JSONL graph/event loader and integrity checks.
- `events.py`: event-log validation and lightweight event-derived summaries.
- `factors.py`: dependency, provenance, boundary, causal, and safety factor checks.
- `retrieve.py`: minimal dependency-closed subgraph retrieval.
- `score.py`: subgraph scoring report assembly.
- `export.py`: sanitized dry-run export generation.
- `sidecar.py`: evidence candidate and weak-association sidecar loading with recursive redaction.
- `storage.py`: capacity-only storage audit and proposal-only archive planning.
- `policy.py`: command, output-path, sensitivity, and boundary gates.
- `cli.py`: limited public command surface.

## Boundaries

The adapter does not own prompt assembly, daemon scheduling, graph mutation, archive application, quarantine, rehydration, or provenance upgrades in v1.0.
