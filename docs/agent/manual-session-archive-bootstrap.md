# Manual session archive bootstrap

## Why this manual archive pass exists

The v2.0 branch already has the dual graph architecture, profile/project/lineage model, `agent-graph` CLI, and dashboard visibility for the Memory Graph and context router.
What it does **not** have yet is trustworthy automatic session archival.

This bootstrap pass exists to turn the current project history into a first production-quality set of curated archive inputs for profile `general`, project `harness-self-governance`.
The goal is twofold:

1. seed the Agent Memory Graph with real project knowledge instead of placeholder entries
2. establish gold fixtures that future automation must match or improve

## Why it is agent-triggered, not automatic yet

Automatic archival is deferred until the repository has validated examples, routing behavior, and quality rules for compiled sessions.
At this stage, manual agent-triggered compilation is safer because it keeps review in the loop and prevents low-quality or privacy-unsafe transcript ingestion.

Current boundary:

- the agent compiles milestone knowledge into structured JSON
- `agent-graph archive-session` merges the structured JSON deterministically
- `agent-graph archive-gate report` and `agent-graph maintenance report` expose archive lifecycle state without mutating memory automatically
- the dashboard reads exported artifacts only
- raw sessions remain local-only source material and last-resort context

Deferred until later work:

- automatic archive triggers
- stale summary detection
- context gap repair loops
- pending update review automation

## How compiled-session examples are used

The committed examples under `docs/examples/agent-memory-graph/harness-self-governance/` are curated `compiled-session` inputs.
They are used as:

- reviewable examples for humans
- deterministic test fixtures
- bootstrap inputs for `agent-graph archive-session`
- reference outputs for future archive automation

Each example must contain:

```json
{
  "schema_version": "2.0",
  "profile_id": "general",
  "project_id": "harness-self-governance",
  "session_id": "...",
  "privacy": "local_only",
  "summary": "...",
  "decisions": [],
  "requirements": [],
  "constraints": [],
  "graph_links": []
}
```

These are **compiled** architectural summaries, not transcript dumps.

## How to archive the examples

From the repository root:

```bash
agent-graph bootstrap --repo .
agent-graph validate --repo .
TMP_MEM=$(mktemp -d)
agent-graph init-repo --repo . --profile general --project harness-self-governance
for f in docs/examples/agent-memory-graph/harness-self-governance/compiled-session-*.json; do
  agent-graph archive-session     --profile general     --project harness-self-governance     --input "$f"     --memory-root "$TMP_MEM"
done
agent-graph archive-gate report --repo . --memory-root "$TMP_MEM"
agent-graph maintenance report --repo . --memory-root "$TMP_MEM"
agent-graph maintenance validate --repo . --memory-root "$TMP_MEM"
agent-graph maintenance propose --repo . --memory-root "$TMP_MEM"
agent-graph validate --repo . --memory-root "$TMP_MEM"
agent-graph export --repo . --memory-root "$TMP_MEM"
```

## How export updates repo-local dashboard artifacts

`agent-graph export --repo . --memory-root "$TMP_MEM"` projects the global memory root back into deterministic repo-local artifacts:

- `artifacts/v2/maintenance/archive-gate-report.json`
- `artifacts/v2/maintenance/archive-maintenance-report.json`
- `artifacts/v2/maintenance/archive-maintenance-proposal.json`
- `artifacts/v2/projects/general/harness-self-governance/project-manifest.json`
- `artifacts/v2/projects/general/harness-self-governance/project-summary.json`
- `artifacts/v2/projects/general/harness-self-governance/decision-ledger.json`
- `artifacts/v2/projects/general/harness-self-governance/requirements.json`
- `artifacts/v2/projects/general/harness-self-governance/constraints.json`
- `artifacts/v2/projects/general/harness-self-governance/session-index.json`
- `artifacts/v2/projects/general/harness-self-governance/graph-fragment.json`
- `artifacts/v2/graph/agent-memory-graph.json`
- `artifacts/v2/lineage/log-index.json`
- `artifacts/v2/profiles/profile-index.json`

The dashboard and router read those repo-local projections.
The dashboard does not need direct access to the global memory root in CI.

## Gold fixture expectations for future automation

Future automatic session maintenance should use these examples as gold fixtures.
That means automation should preserve these properties:

- stable session IDs and architectural IDs
- no raw transcript dumps
- no private local absolute paths
- no secrets or token names
- concise but complete milestone summaries
- graph links that improve Memory Graph structure
- no dependence on committed raw sessions

A future automation path can add more sessions, stale-summary detection, context-gap repair, and pending-update review, but it should continue to validate itself against this first curated archive set.
