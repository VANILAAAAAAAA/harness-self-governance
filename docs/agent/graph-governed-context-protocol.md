# Graph-Governed Context Protocol

## Default context order

Use graph-governed context loading in this order:

1. global graph
2. active profile
3. active project
4. project summary
5. decision ledger
6. requirements
7. constraints
8. lineage index
9. mapped logs / artifacts
10. raw sessions

`raw sessions` are source material and must remain the last-resort context layer.

## Semantics

- **graph** = navigation layer
- **project artifacts** = stable knowledge layer
- **lineage / logs** = evidence layer
- **raw sessions** = source material / recovery layer

## Profile and project boundaries

- `general` is the governance hub for global protocol rules, cross-project stewardship, and reusable exports.
- `ehrlab` is the domain knowledge profile for EHR and healthcare work.
- Profiles are stable context partitions, not raw-session dumps.
- Projects hold deterministic artifacts that can be re-read without replaying whole sessions.

## Repo adoption

A repository opts into the protocol by committing `.agent/context.json`.

That manifest binds the repo to:

- one active profile
- one active project
- a global memory source
- deterministic repo-local export targets

## Budgeted traversal router

Agent work should now pass through the budgeted graph traversal router:

```text
repo manifest -> profile -> project -> context index -> Agent Memory Graph entry node -> bounded traversal -> context packet
```

The router is structured context routing, not RAG. It does not use embeddings, vector search, reranking, or broad fallback search.

Budgets:

- `fast`: context index, project summary, direct entry artifacts
- `normal`: fast plus selected decisions / requirements / constraints and lineage paths
- `deep`: normal plus mapped logs and session summaries
- `forensic`: deep plus explicit raw-session permission

Routing semantics:

- new information becomes a pending update
- retrieval miss becomes a context gap
- ambiguous intent sets `requires_llm_gate=true` and does not deepen context automatically
- raw sessions are explicit forensic-only

## Phase boundary

This phase is local-only:

- no backend
- no Hub-side LLM API
- no external CDN
- no graph mutation execution
- no destructive apply flow
- no embeddings, vector DB, or reranker

## Dual graph architecture

- `artifacts/v2/graph/governance-graph.json` is the repo-wide Governance Graph for dashboard exploration, observability, and evidence navigation.
- `artifacts/v2/graph/agent-memory-graph.json` is the Agent Memory Graph for graph-governed context loading and protocol routing.
- The dashboard defaults to Governance mode and offers a separate Memory mode.
- The two graphs stay separate; they are not flattened into one dataset.
