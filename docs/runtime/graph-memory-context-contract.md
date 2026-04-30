# Graph Memory Context Contract

This document is agent-facing. It defines how Hermes should use compiled graph memory before relying on generic durable memory or historical raw sessions. It does **not** replace the current live conversation/session context: Hermes must keep using the active session's raw messages as short-term working memory because the live turn stream is the freshest source of intent and corrections.

## Runtime order

```text
user query
  -> preserve current Hermes live session raw context
  -> agent_memory_graph retrieve --budget fast --evidence-depth anchor
  -> summary_first + plan + selected small subgraph + raw evidence anchors + skill_mounts
  -> graph-selected skills are mounted as procedural adapters/load directives
  -> optional evidence deepening to safe_excerpt or explicit forensic raw-span request
  -> agent reasoning/action
```

## Rules

0. Preserve the active Hermes session raw message stream as live short-term context. Compiled graph memory governs long-term/project memory only.
1. Call `agent_memory_graph retrieve` for project-specific tasks when a repo has `.agent/context.json`.
2. Treat `summary_first`, `plan`, `hard_constraints`, `skill_mounts`, `skill_load_order`, and selected graph nodes as primary long-term project memory plus procedural attachment directives.
3. Use Hermes durable memory only for routing pointers, user preferences, and stable environment facts.
4. Do not read historical `sessions/raw/` by default.
5. Under `fast`, `normal`, and `deep` budgets, historical `raw_sessions_allowed` must remain false.
6. Default `--evidence-depth anchor` may return raw evidence anchor metadata only; it must not include raw text.
7. `--evidence-depth excerpt` may return precompiled/redacted `safe_excerpt` stored in the anchor index; it still must not read historical raw sessions.
8. `--evidence-depth raw-span` may only return a raw span request when budget is `forensic` and the query contains an explicit discovery/forensic marker; the retriever itself still returns a request, not an automatic raw dump.
9. A zero-hit retrieval returns `MISS` with `hit_count=0`; do not automatically escalate through all budgets.
10. New user facts, corrections, decisions, requirements, constraints, or plan items are captured as `pending_update`, not `compiled_memory`.
11. Archive gate is required before pending updates become compiled summary/plan/graph edges.
12. Dashboard is read-only observability for user audit; it does not define runtime semantics.
13. Human-readable explanations are generated on demand from agent-readable node metadata.
14. For latency, use existing `context-index.json` and `global-graph.json` cache by default; rebuild only with `--refresh-index` or `--refresh-graph`.

## CLI

```bash
python -m agent_memory_graph retrieve \
  --repo /path/to/repo \
  --query "user task" \
  --budget fast \
  --evidence-depth anchor

# Optional: use precompiled safe excerpts, still without reading historical raw sessions.
python -m agent_memory_graph retrieve \
  --repo /path/to/repo \
  --query "why was Focus Hub scoped?" \
  --budget normal \
  --evidence-depth excerpt

# Optional: request raw span pointers only under explicit forensic mode.
python -m agent_memory_graph retrieve \
  --repo /path/to/repo \
  --query "forensic raw sessions explicit discovery for Focus Hub" \
  --budget forensic \
  --evidence-depth raw-span
```

Expected packet fields:

```text
status
summary_first
plan
selected_nodes
selected_edges
skill_mounts
skill_load_order
selected_evidence_paths
selected_raw_evidence_anchors
raw_span_requests
evidence_depth
latency_ms
cache_events
miss_policy
pending_context
current_session_raw_context
compiled_memory_raw_session_reads
raw_sessions_allowed
```

## Hermes adapter

A mature Hermes integration should use the bundled `graph-memory` plugin instead of relying on the model to remember to call the retriever manually.

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
  skill_mount_mode: summary
  max_skill_chars: 1600
  trace: true
  trace_dir: /home/vanila/.hermes/profiles/general/graph-memory-traces
  memory_root: /home/vanila/.hermes/profiles/general/home/.agent-memory-graph
  repo_roots:
    - /home/vanila/code/graph-harness-maintain
  repo_project_hints:
    /home/vanila/code/graph-harness-maintain:
      profile: general
      project: harness-self-governance
  raw_span_enabled: false
  capture_pending_updates: false
```

The plugin's `pre_llm_call` hook injects a bounded `<graph_memory_context>` block into the current turn. It preserves live session raw context, uses cached graph artifacts by default, mounts graph-selected skills as compact procedural contracts, and writes a JSONL trace per turn.
