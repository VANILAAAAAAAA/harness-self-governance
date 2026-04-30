# Graph Memory Plugin

`graph-memory` is a Hermes `pre_llm_call`/`post_llm_call` plugin that injects graph-governed project memory into each LLM turn.

It is designed for mature project memory governance, not a toy wiki/RAG fallback:

- preserve the active Hermes live session as short-term raw context;
- retrieve only a bounded project memory packet from `agent_memory_graph`;
- attach graph-selected procedural skills via `skill_mounts` / `skill_load_order`;
- keep historical raw sessions forbidden by default;
- write per-turn traces for audit;
- optionally capture new decisions/constraints as pending updates for archive-gate promotion.

## Runtime order

```text
incoming user turn
  -> pre_llm_call graph-memory plugin
  -> detect workspace from [Workspace: ...], TERMINAL_CWD, or PWD
  -> detect repo with .agent/context.json
  -> call agent_memory_graph.retrieve_project_context(...)
  -> render bounded <graph_memory_context> block
  -> include mounted skill summaries/contracts
  -> inject ephemeral context into current user message
  -> LLM executes with live session + graph packet + skill mounts
  -> optional post_llm_call pending update capture
```

## Config

Install as an independent project extension from this repository, not as an upstream `hermes-agent` fork:

```bash
cd /home/vanila/code/graph-harness-maintain
./adapters/hermes/install.sh /home/vanila/.hermes/profiles/general
./adapters/hermes/verify.sh /home/vanila/.hermes/profiles/general
```

The adapter manifest is versioned at `adapters/hermes/adapter.yaml`; installed copies go under the target profile's `plugins/` directory.

```yaml
plugins:
  enabled:
    - graph-memory

graph_memory:
  enabled: true
  mode: inject        # off | observe | inject | enforce
  default_budget: fast
  default_evidence_depth: anchor
  max_context_chars: 6000
  auto_skill_mounts: true
  skill_mount_mode: summary   # directive | summary | full
  max_skill_chars: 1600
  trace: true
  trace_dir: ~/.hermes/graph-memory-traces
  memory_root: ~/.agent-memory-graph
  repo_roots:
    - /home/vanila/code/graph-harness-maintain
  repo_project_hints:
    /home/vanila/code/graph-harness-maintain:
      profile: general
      project: harness-self-governance
  raw_span_enabled: false
  capture_pending_updates: false
  search_workspace_children: true
  workspace_child_depth: 1
```

## Modes

| mode | behavior |
|---|---|
| `off` | no retrieval, no injection |
| `observe` | retrieve and trace only; does not inject context |
| `inject` | retrieve, trace, inject bounded context |
| `enforce` | currently same injection behavior; reserved for future hard failures/policy gates |

## Safety policy

- Default `evidence_depth: anchor` returns evidence metadata only.
- `raw_span_enabled: false` downgrades accidental `raw-span` requests to anchor/fast.
- Historical raw sessions are not read by the plugin.
- Live conversation raw context remains untouched; the plugin only adds project memory.
- Failed retrieval writes trace and returns no context instead of crashing the turn.

## Trace

Each turn appends JSONL under `trace_dir`:

```json
{
  "event": "pre_llm_call",
  "status": "PASS",
  "mode": "inject",
  "workspace": "/home/vanila/code",
  "repo": "/home/vanila/code/graph-harness-maintain",
  "selected_profile": "general",
  "selected_project": "harness-self-governance",
  "skill_load_order": ["graph-harness-maintain", "hermes-agent"],
  "raw_sessions_allowed": false,
  "injected": true
}
```

Export bounded trace observability into the read-only dashboard artifact set:

```bash
.venv/bin/python -m agent_memory_graph runtime-traces export \
  --trace-dir /home/vanila/.hermes/profiles/general/graph-memory-traces \
  --out artifacts/v2/runtime/graph-memory-traces.json \
  --limit 50
```

The dashboard treats this as readonly audit evidence. Missing trace export is a warning, not a runtime blocker.

## Archive lifecycle

New facts are not directly archived. The controlled lifecycle is:

```text
live turn -> pending_update -> compiled_candidate -> archive_gate -> compiled_memory
```

Materialize pending updates as review-only candidates:

```bash
.venv/bin/python -m agent_memory_graph archive-gate compile-pending \
  --repo . \
  --profile general \
  --project harness-self-governance
```

This is non-destructive: pending updates remain in place, candidates require review, and auto archive remains disabled.

## Rollback

Disable without removing code:

```yaml
graph_memory:
  enabled: false
  mode: off
plugins:
  enabled: []
```

Or remove only `graph-memory` from `plugins.enabled`.
