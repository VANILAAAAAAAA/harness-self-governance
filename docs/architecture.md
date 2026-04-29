# Architecture

`graph-harness-maintain` v2.0 is a local-first governance and graph-context harness for agent-maintained repositories.

## v2.0 architecture summary

The release-ready v2.0 surface is intentionally narrow:

- **Graph page**: primary dashboard view for graph exploration and protocol visibility
- **Logs page**: artifact, evidence, and lineage browser
- **Governance Graph**: repo-wide asset/evidence/navigation graph
- **Agent Memory Graph**: agent context/protocol graph used for graph-governed context loading
- **Context Router**: deterministic, budgeted graph traversal over the Agent Memory Graph
- **Archive Lifecycle**: manual archive bootstrap, archive gate, maintenance, and trigger-policy reporting

The system is static, local, and auditable.

## Hard boundaries

v2.0 does **not** include:

- backend services
- Hub-side LLM API
- model/provider UI
- Settings / Policies / Health pages as product pages
- embeddings, vector DB, reranker, or RAG fallback
- automatic archival
- destructive apply
- graph mutation execution
- sensitive export

## Core surfaces

### 1. Governance Graph

Purpose:
- repo-wide exploration
- evidence navigation
- dashboard overview
- lineage-aware inspection support

Typical repo-local export:
- `artifacts/v2/graph/governance-graph.json`

### 2. Agent Memory Graph

Purpose:
- stable archived project knowledge
- graph-governed context loading
- routing and traversal substrate
- archive lifecycle reporting target

Typical repo-local export:
- `artifacts/v2/graph/agent-memory-graph.json`

Typical global source:
- `~/.agent-memory-graph/` or caller-supplied `--memory-root`

### 3. Graph + Logs dashboard

The dashboard has only two core routes in v2.0:

- `#/graph`
- `#/logs`

Graph route:
- defaults to Governance Graph mode
- can expose Memory Graph visibility
- shows Context Router and Archive Lifecycle summaries

Logs route:
- file explorer/tree
- file table/list
- preview + metadata + lineage panel
- `View in Logs` only when exact lineage mapping exists

### 4. Archive lifecycle governance

The archive lifecycle remains review-based and explicit:

- `archive-session` ingests curated `compiled-session` JSON
- `archive-gate` classifies live/pending/compiled/forensic boundaries
- `maintenance` reports and proposal outputs are non-destructive
- `triggers` produce recommendations only

Archive trigger policy is active, but:
- `archive_auto_apply_enabled = false`
- manual archive review is required

## CLI surfaces

### Main package CLI

- `ghm`
- `python -m graph_harness_maintain`

Primary release-validation flow:

```bash
python -m graph_harness_maintain pipeline local-rc --ci
python -m graph_harness_maintain pipeline v2.0-rc
```

### Agent Memory Graph CLI

- `agent-graph init-repo`
- `agent-graph bootstrap`
- `agent-graph validate`
- `agent-graph archive-session`
- `agent-graph export`
- `agent-graph build-index`
- `agent-graph route`
- `agent-graph traverse`
- `agent-graph capture-update`
- `agent-graph list-gaps`
- `agent-graph archive-gate`
- `agent-graph maintenance`
- `agent-graph triggers`

## Data flow

```text
repo manifest (.agent/context.json)
-> bootstrap / validate
-> curated compiled-session inputs
-> archive-session
-> project memory artifacts
-> export
-> repo-local dashboard artifacts
-> Graph + Logs review
```

Context routing flow:

```text
repo manifest
-> context index
-> Agent Memory Graph entry node
-> bounded traversal
-> context packet
-> pending updates / context gaps when needed
```

## Release-readiness expectations

A v2.0-ready repo state means:

- README, CHANGELOG, package metadata, and CLI help agree on the v2.0 surface
- Graph + Logs docs match the dashboard
- Archive lifecycle docs match implementation
- generated `artifacts/v2/`, screenshots, raw sessions, and concept images are not committed
- no private local paths or secrets appear in public files

## Safety model

v2.0 remains safe by default:

- local-first outputs
- read-only dashboard
- proposal-only archive maintenance
- manual archive review
- raw sessions as forensic-only fallback
- no remote publication until explicit human approval
