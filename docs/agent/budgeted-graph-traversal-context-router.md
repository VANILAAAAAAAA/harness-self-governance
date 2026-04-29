# Budgeted Graph Traversal Context Router

## Purpose

The Graph Traversal Context Router is the production routing layer for the Agent Memory Graph.
It turns a repository manifest and a user query into a small context packet by using structured routing tables and bounded graph traversal.

This is **not RAG**:

- no embeddings
- no vector database
- no reranker
- no broad fallback search
- no raw-session replay by default

## Layer boundaries

`graph-harness-maintain` now has two graph layers:

| Layer | File | Purpose |
| --- | --- | --- |
| Governance Graph | `artifacts/v2/graph/governance-graph.json` | repo-wide asset/evidence/navigation graph for dashboard exploration and Logs links |
| Agent Memory Graph | `artifacts/v2/graph/agent-memory-graph.json` and global memory root `graph/global-graph.json` | context/protocol graph used by agents for graph-governed context loading |

The router operates on the **Agent Memory Graph**. It may select lineage artifacts as evidence, but it does not flatten the Governance Graph into Memory.

## Default context flow

```text
repo manifest
  -> active profile
  -> active project
  -> context index
  -> Agent Memory Graph entry node
  -> graph traversal
  -> selected project artifacts
  -> selected lineage artifacts if needed
  -> small context packet
  -> raw sessions only in explicit forensic mode
```

## Commands

### Build index

```bash
agent-graph build-index --repo . --memory-root <path>
```

Writes:

```text
<memory-root>/index/context-index.json
```

The context index is a small routing table, not a search database. It contains profiles, projects, topics, aliases, entry nodes, artifact paths, budget hints, and graph layer references.

### Route query

```bash
agent-graph route --repo . --query "view in logs lineage mapping" --memory-root <path> --context-budget fast
```

The route output includes candidate intent, cheap signals, matched topics/aliases, entry nodes, traversal paths, selected artifacts, recommended context packet, budget, raw-session policy, warnings, and blockers.

### Traverse graph

```bash
agent-graph traverse --repo . --node project:general:harness-self-governance --max-depth 2 --memory-root <path>
```

Traversal is bounded over Agent Memory Graph nodes and edges. It does not do full-text search and does not read raw sessions.

### Capture update

```bash
agent-graph capture-update --repo . --text "v2.0 keeps Hub-side LLM API deferred." --profile general --project harness-self-governance --memory-root <path>
```

New information becomes a pending update under:

```text
<memory-root>/routing/pending-updates.json
```

It does not trigger deep fallback.

### List gaps

```bash
agent-graph list-gaps --repo . --memory-root <path>
```

Retrieval misses become context gaps under:

```text
<memory-root>/routing/context-gaps/
```

## Intent semantics

| Intent | Router behavior |
| --- | --- |
| `retrieve_existing` + hit | route to entry nodes, traverse graph, output context packet |
| `retrieve_existing` + miss | record context gap; do not read raw sessions |
| `new_information` | recommend/capture pending update; do not deepen context |
| `modify_existing` | route through context packet before task execution; no graph mutation execution |
| `task_execution` | route only enough context for task; LLM performs actual reasoning |
| `archive_request` | use agent-triggered compiled archive flow when explicit |
| `ambiguous` | set `requires_llm_gate=true`; output tiny routing packet; do not call LLM |

## Budgets

| Budget | Includes | Raw sessions |
| --- | --- | --- |
| `fast` | context index, project summary, direct entry artifacts | false |
| `normal` | fast + selected decisions/requirements/constraints + selected lineage paths | false |
| `deep` | normal + mapped logs + session summaries | false |
| `forensic` | deep + explicit raw-session permission | true |

Raw sessions are explicit forensic-only. They are not a default fallback for misses.

## Context packet

The recommended packet has this shape:

```json
{
  "schema_version": "2.0",
  "profile": "general",
  "project": "harness-self-governance",
  "intent": "retrieve_existing",
  "budget": "fast",
  "primary_context": [],
  "optional_context": [],
  "traversal_nodes": [],
  "traversal_edges": [],
  "do_not_read_by_default": ["sessions/raw/"],
  "raw_sessions_allowed": false,
  "routing_reason": "matched_context_index_then_bounded_graph_traversal",
  "archive_policy": {
    "new_information": "capture_pending_update",
    "retrieval_miss": "record_context_gap",
    "raw_sessions": "explicit_forensic_only"
  }
}
```


## Repo-local observability artifacts

`python -m graph_harness_maintain pipeline v2.0-rc` generates a deterministic, repo-local projection of router behavior under `artifacts/v2/context/`:

| Artifact | Purpose |
| --- | --- |
| `context-index.json` | exported graph-governed routing table from the temporary memory root |
| `router-samples.json` | fixed production smoke samples covering evidence route, log-location route, and new-information capture |
| `context-packets.json` | the route outputs/context packets selected for each sample query |
| `context-gaps.json` | context-gap audit output; present even when no gaps are found |
| `pending-updates.json` | pending archive/update candidates produced by new-information samples |
| `context-router-report.json` | counts, artifact paths, and safety policy summary |

These artifacts are generated outputs and should not be committed. They let the static dashboard display real router behavior without a backend, Hub-side LLM API, model/provider UI, graph mutation execution, or raw-session fallback.

The dashboard reads the exported artifacts as embedded JSON. The visible Router Panel is therefore an observability surface: it can show sample intent, budget, selected artifacts, packet size, gap count, pending-update count, and `raw_sessions_default_read=false`, but it does not execute archive, graph mutation, delete/move/quarantine/rehydrate, or raw archive apply.

## LLM boundary

The external program owns routing, traversal, artifact path selection, budget control, packet generation, and gap audit.

The LLM owns task reasoning after receiving the context packet. It only makes ambiguous intent decisions when `requires_llm_gate=true`, and it only compiles archive input when explicitly asked.
