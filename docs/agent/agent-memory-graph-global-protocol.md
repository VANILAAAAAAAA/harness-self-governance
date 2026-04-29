# Agent Memory Graph Global Protocol

## Goal

`graph-harness-maintain` is the reference implementation and dashboard/export target for a reusable global Agent Memory Graph protocol.

Agents should not start from raw sessions by default. They should start from graph-governed artifacts and only fall back to raw sessions when artifacts are missing, stale, or explicitly requested.

## Global memory root

Default root:

```text
~/.agent-memory-graph/
```

Test override:

```text
agent-graph ... --memory-root <path>
```

## Layout

```text
~/.agent-memory-graph/
  config.json
  profiles/
    general/profile.json
    ehrlab/profile.json
  projects/
    general/harness-self-governance/
      project-manifest.json
      project-summary.json
      decision-ledger.json
      requirements.json
      constraints.json
      session-index.json
      graph-fragment.json
      lineage-index.json
  graph/
    global-graph.json
    global-lineage-index.json
  index/
    context-index.json
  routing/
    pending-updates.json
    context-gaps/
  reports/
    context-bootstrap-report.json
```

## Budgeted graph traversal router

Run:

```bash
agent-graph build-index --repo . --memory-root <path>
agent-graph route --repo . --query "view in logs lineage mapping" --memory-root <path> --context-budget fast
agent-graph traverse --repo . --node project:general:harness-self-governance --max-depth 2 --memory-root <path>
```

The router uses structured graph traversal over the Agent Memory Graph. It is not RAG: no embeddings, no vector database, no reranking, and no broad fallback search.

New information is captured as a pending update:

```bash
agent-graph capture-update --repo . --text "..." --profile general --project harness-self-governance --memory-root <path>
```

Retrieval misses are recorded as context gaps and can be inspected with:

```bash
agent-graph list-gaps --repo . --memory-root <path>
```

Raw sessions are explicit forensic-only. The default `fast` budget never reads raw sessions.

## Archive flow

`agent-graph archive-session` is agent-triggered and deterministic.

It does **not** call an LLM or external API. It accepts compiled JSON and merges:

- decisions
- requirements
- constraints
- session summaries
- graph links

It updates:

- `project-summary.json`
- `decision-ledger.json`
- `requirements.json`
- `constraints.json`
- `session-index.json`
- `graph-fragment.json`

`local_only` privacy markers must be preserved.

## Compiled input schema

```json
{
  "schema_version": "2.0",
  "profile_id": "general",
  "project_id": "harness-self-governance",
  "session_id": "session:v2-dashboard-planning",
  "privacy": "local_only",
  "summary": "v2 focuses on Graph and Logs as the core pages.",
  "decisions": [
    {
      "id": "decision:v2-core-graph-logs",
      "text": "v2.0 uses Graph and Logs as core pages.",
      "status": "accepted",
      "source": "session:v2-dashboard-planning"
    }
  ],
  "requirements": [
    {
      "id": "requirement:graph-main-focus",
      "text": "The Graph page should make the graph the primary focus.",
      "source": "session:v2-dashboard-planning"
    }
  ],
  "constraints": [
    {
      "id": "constraint:raw-sessions-last",
      "text": "Raw sessions are source material and last-resort context.",
      "source": "session:v2-dashboard-planning"
    }
  ],
  "graph_links": [
    {
      "source": "decision:v2-core-graph-logs",
      "target": "requirement:graph-main-focus",
      "type": "supports"
    }
  ]
}
```

## Export-to-repo flow

Run:

```bash
agent-graph export --repo . --memory-root <path>
```

This projects global memory artifacts into repo-local paths:

- `artifacts/v2/projects/general/harness-self-governance/`
- `artifacts/v2/graph/agent-memory-graph.json`
- `artifacts/v2/graph/governance-graph.json`
- `artifacts/v2/lineage/log-index.json`
- `artifacts/v2/profiles/profile-index.json`

The dashboard reads those repo-local exports. Governance Graph remains the repo-wide exploration/evidence graph, while Agent Memory Graph remains the context/protocol graph. The dashboard does not read `~/.agent-memory-graph/` directly in CI.

## Future repo adoption

Future repositories can adopt the protocol by:

1. committing `.agent/context.json`
2. running `agent-graph init-repo`
3. bootstrapping a temporary or user-owned memory root
4. exporting graph/project/lineage artifacts into repo-local paths
