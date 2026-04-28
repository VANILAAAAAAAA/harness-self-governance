---
name: graph-governed-context
description: Use graph-governed context loading before repository work.
version: 0.1.0
---

# Graph-Governed Context

Use graph-governed context loading.

Before repository work, run:

```bash
agent-graph bootstrap --repo .
```

Use the returned graph, project summary, decision ledger, requirements, constraints, and lineage index as primary context.

Do not start from raw sessions unless graph/project artifacts are missing, stale, or explicitly requested.

## Rules

- graph-first read order
- raw sessions last
- prefer project artifacts over raw session replay
- use `--memory-root <path>` in tests and CI
- do not enable Hub-side LLM API in this phase
