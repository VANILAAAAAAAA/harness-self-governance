# Archive lifecycle governance

## Purpose

Archive lifecycle governance defines how project knowledge moves from active session work into reviewable, graph-readable, local-only memory artifacts.

In v2.0-dev this remains conservative:

- no automatic archival
- no raw transcript commits
- no destructive apply
- no graph mutation execution
- no backend or Hub-side LLM API
- no embeddings, vector DB, or reranker

The goal is observability and review, not silent memory mutation.

## Lifecycle states

### 1. `transient`

Material that is useful only inside the current reasoning loop.
Examples:

- scratch notes
- temporary debug observations
- unstable design speculation

Handling:

- do not archive
- do not route as durable memory
- keep only in live session context unless explicitly promoted

### 2. `pending_update`

Potentially durable knowledge that still needs review.
Examples:

- new policy candidate
- unresolved context gap follow-up
- stale summary review note

Handling:

- record as maintenance signal
- expose in router / maintenance reports
- never auto-promote to compiled memory

### 3. `compiled_candidate`

Curated, structured knowledge ready for reviewed archive.
This is the expected class for committed `compiled-session-*.json` fixtures.

Handling:

- must satisfy compiled-session schema and quality rules
- must use explicit reviewed archive command path
- may be archived with `agent-graph archive-session`
- remains local-only structured knowledge

### 4. `forensic_only`

Raw sessions and transcript-like source artifacts.

Handling:

- exclude from default context loading
- keep local only
- access only for explicit forensic recovery
- never commit as archive fixtures

## Review boundary rules

These rules are normative for v2.0-dev:

- live session has priority for active reasoning
- pending updates never become compiled memory automatically
- compiled candidates require explicit reviewed archive command path
- forensic-only raw sessions stay last-resort
- `raw_sessions_required` is false by default

## CLI surface

### Archive gate

Classify a single input:

```bash
agent-graph archive-gate classify --input path/to/file.json
```

Generate a repo-aware report:

```bash
agent-graph archive-gate report --repo . --memory-root "$TMP_MEM"
```

Report output:

- `reports/archive-gate-report.json`
- repo-local projection: `artifacts/v2/maintenance/archive-gate-report.json`

### Maintenance

Write the maintenance summary:

```bash
agent-graph maintenance report --repo . --memory-root "$TMP_MEM"
```

Validate lifecycle governance state:

```bash
agent-graph maintenance validate --repo . --memory-root "$TMP_MEM"
```

Emit a proposal-only next-action plan:

```bash
agent-graph maintenance propose --repo . --memory-root "$TMP_MEM"
```

Outputs:

- `reports/archive-maintenance-report.json`
- `reports/archive-maintenance-proposal.json`
- repo-local projections under `artifacts/v2/maintenance/`

## Quality rules for compiled-session inputs

A `compiled_candidate` must be:

- valid JSON
- schema version `2.0`
- correct `profile_id` and `project_id`
- local-only privacy
- concise summary
- non-empty structural sections:
  - `summary`
  - `decisions`
  - `requirements`
  - `constraints`
  - `graph_links`
- free of transcript dumps
- free of private local absolute paths
- free of secret/token names

These rules are intentionally stricter than plain schema validity because the examples act as gold fixtures for future automation.

## How this connects to the dashboard

The Graph page remains a read-only graph page.
It now includes a compact Archive Lifecycle summary showing:

- live session boundary is active
- pending update count
- compiled candidate count
- context gap count
- stale summary count
- archive quality status
- raw sessions are forensic only

This summary is derived from exported maintenance artifacts, not from a backend.

## How this connects to the v2 pipeline

The v2.0 RC pipeline now:

1. bootstraps a temporary memory root
2. archives curated compiled-session examples into that temporary root
3. writes archive gate and maintenance reports
4. exports repo-local maintenance projections
5. builds dashboard artifacts from those projections

This keeps CI deterministic while avoiding committed generated artifacts.

## Gold fixture role

The committed compiled-session examples under:

- `docs/examples/agent-memory-graph/harness-self-governance/`

are the first production-quality gold fixtures.

Future automatic archival must match or improve them on:

- correctness
- privacy
- stability
- graph usefulness
- routing usefulness
- reviewability

Automation should be judged against these fixtures before it is trusted to archive new sessions without manual compilation.
