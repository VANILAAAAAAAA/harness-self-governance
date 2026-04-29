# Harness Self Governance compiled-session examples

This directory contains production-style **compiled-session** inputs for the Agent Memory Graph archive flow.

These files are curated examples for profile `general` and project `harness-self-governance`.
They are **not raw sessions**, **not screenshots**, and **not generated runtime exports**.

## Why these files exist

This repository now has a reusable Agent Memory Graph protocol, but the project history was originally captured across milestone work rather than an automatic archive pipeline.
The first manual archive pass turns that history into stable, reviewable fixtures:

- gold-standard `compiled-session` examples for future archive automation
- deterministic inputs for `agent-graph archive-session`
- meaningful seed knowledge for the Memory Graph and context router
- regression fixtures for tests and dashboard/export validation

## Included milestones

- `compiled-session-v1-baseline.json`
- `compiled-session-v1-1-baseline.json`
- `compiled-session-v2-dashboard-architecture.json`
- `compiled-session-frontend-visual-qa.json`
- `compiled-session-profile-project-lineage.json`
- `compiled-session-global-agent-memory-graph.json`
- `compiled-session-context-router.json`

## Curation rules

Each file follows schema version `2.0` and must stay:

- local-only
- concise and architectural
- free of raw transcript dumps
- free of secrets and token names
- free of private local absolute paths
- focused on decisions, requirements, constraints, and graph links

## Archive them into a temporary memory root

```bash
TMP_MEM=$(mktemp -d)
agent-graph init-repo --repo . --profile general --project harness-self-governance
for f in docs/examples/agent-memory-graph/harness-self-governance/compiled-session-*.json; do
  agent-graph archive-session     --profile general     --project harness-self-governance     --input "$f"     --memory-root "$TMP_MEM"
done
agent-graph validate --repo . --memory-root "$TMP_MEM"
agent-graph export --repo . --memory-root "$TMP_MEM"
```

The export updates repo-local dashboard inputs under `artifacts/v2/`, especially:

- `artifacts/v2/projects/general/harness-self-governance/`
- `artifacts/v2/graph/agent-memory-graph.json`
- `artifacts/v2/lineage/log-index.json`
- `artifacts/v2/profiles/profile-index.json`

Those runtime outputs remain generated local artifacts and should not be committed.
