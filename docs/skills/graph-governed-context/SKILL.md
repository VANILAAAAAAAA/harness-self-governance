---
name: graph-governed-context
description: Use graph-governed context loading before repository work.
version: 0.2.0
---

# Graph-Governed Context

Use graph-governed context loading.

Before repository work, run:

```bash
agent-graph bootstrap --repo . --context-budget fast
agent-graph build-index --repo .
```

Then route task-specific context:

```bash
agent-graph route --repo . --query "<task or question>" --context-budget fast
```

Use the returned graph, project summary, decision ledger, requirements, constraints, lineage index, traversal paths, and selected artifacts as primary context.

Do not start from raw sessions. Raw sessions are explicit forensic-only and require `--context-budget forensic` plus a task that actually needs forensic reconstruction or archive repair.

## Rules

- graph-first read order
- route through the Agent Memory Graph, not the Governance Graph
- keep Governance Graph and Agent Memory Graph separate
- this is graph traversal and structured context routing, not RAG
- no embeddings, vector DB, or reranker in this phase
- new information becomes a pending update via `agent-graph capture-update`
- retrieval miss becomes a context gap via router/list-gaps
- raw sessions are not a default fallback
- use `--memory-root <path>` in tests and CI
- do not enable Hub-side LLM API in this phase

## Budget defaults

- `fast`: context index, project summary, direct entry artifacts
- `normal`: fast plus selected decisions/requirements/constraints and lineage paths
- `deep`: normal plus mapped logs and session summaries
- `forensic`: deep plus explicit raw-session permission
