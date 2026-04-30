# Agent-Readable Graph Memory Retriever Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Make the graph-harness project memory system an agent-facing context control plane: Hermes retrieves compact, task-relevant project context from compiled graph memory instead of relying on generic Hermes memory or reading wiki-like documents wholesale.

**Architecture:** Keep markdown/dashboard as observability only. The runtime path is `query -> project router -> summary/plan entry nodes -> weighted subgraph traversal -> context packet -> prompt injection candidate`. Summaries are optimized for model parsing, not human readability; graph retrieval selects a dependency/provenance-closed small subgraph, not a Top-K document list.

**Tech Stack:** Python 3.11+, existing `agent_memory_graph` package, JSON artifacts, pytest, optional future graph libraries only after baseline algorithms are validated.

---

## Strategic Positioning

This is **not** llmwiki-lite.

```text
llmwiki:
  compiled knowledge pages -> LLM reads wiki/documents

graph-harness target:
  compiled project memory graph -> agent context router chooses what to read, what not to read, and why
```

The graph is the control plane. Documents are payloads or evidence bodies.

Primary runtime contract:

```text
User query
  -> identify candidate project/profile
  -> load agent-readable project summary and plan
  -> traverse graph with typed edge weights and budget constraints
  -> emit compact context packet
  -> agent answers/acts using packet
  -> new information goes to pending update, not compiled memory
```

Core principles:

1. **Agent-readable over human-readable.** Summary format should be structured, repetitive, low ambiguity, and easy for a model to parse.
2. **Small graph over big wiki.** Retrieve a bounded subgraph with dependency/provenance closure; never load all project docs by default.
3. **Compiled memory over raw sessions.** Raw sessions are forensic fallback only.
4. **Memory lifecycle is explicit.** `live_session_ram -> pending_update -> compiled_candidate -> archive_gate -> compiled_memory`.
5. **Misses are first-class.** If the graph does not know, record a context gap or pending update instead of hallucinating from nearby docs.
6. **Dashboard is read-only observability.** Users need a visual audit surface to see what the agent has compiled and selected, but dashboard must not become the runtime source of truth.
7. **Human-readable explanations are generated on demand.** If a user asks what a summary/plan/decision node means, the agent reads the agent-readable node and produces a human-readable explanation. The stored canonical node remains optimized for model parsing.
8. **No expensive fallback ladder by default.** A zero-hit or low-confidence retrieval must stop cheaply, emit a miss packet, and decide whether to ask, create a pending project/update, or run one explicit deeper pass. It must not silently cascade through all docs/raw sessions.

---

## Current Code Baseline

Relevant existing files:

```text
src/agent_memory_graph/router.py
src/agent_memory_graph/context_index.py
src/agent_memory_graph/context_packet.py
src/agent_memory_graph/traversal.py
src/agent_memory_graph/context_gaps.py
src/agent_memory_graph/pending_updates.py
src/agent_memory_graph/archive_gate.py
src/graph_harness_maintain/graph_export.py
src/graph_harness_maintain/dashboard.py
tests/test_agent_memory_graph_routing.py
tests/test_agent_memory_graph_traversal.py
tests/test_dashboard.py
```

Existing strengths:

- Router already emits context packets.
- Context budgets already exist: `fast`, `normal`, `deep`, `forensic`.
- Traversal already avoids raw sessions by default.
- Context gaps and pending updates already exist conceptually.
- Dashboard now shows project summary and plan nodes.

Main gaps:

- Router is still alias/topic oriented, not summary/plan-first.
- Traversal is BFS-like, not weighted, typed, or dependency/provenance-closed.
- Context packet returns artifact references, not enough normalized agent-readable content.
- Summary schema exists in docs but is not yet the runtime contract.
- Hermes itself does not yet automatically call this retriever before task reasoning.

---

## Target Runtime Contract

Create one stable high-level API:

```python
from agent_memory_graph.retrieve import retrieve_project_context

packet = retrieve_project_context(
    repo_root=Path('/home/vanila/code/graph-harness-maintain'),
    query='用户问题或任务',
    profile_hint='general',
    project_hint=None,
    budget='fast',
)
```

Return shape:

```json
{
  "status": "PASS|MISS|AMBIGUOUS|BLOCKED",
  "query": "...",
  "selected_profile": "general",
  "selected_project": "harness-self-governance",
  "confidence": 0.0,
  "budget": "fast",
  "context_role": "compiled_project_memory",
  "summary_first": {
    "project_identity": "...",
    "project_goal": "...",
    "current_state": "...",
    "active_phase": "...",
    "open_problems": [],
    "hard_constraints": [],
    "read_order": []
  },
  "plan": {
    "completed": [],
    "todo": [],
    "update_mode": "agent_plan_command_compatible"
  },
  "selected_nodes": [],
  "selected_edges": [],
  "selected_evidence_paths": [],
  "do_not_read_by_default": ["sessions/raw/"],
  "miss_policy": {},
  "warnings": [],
  "blockers": []
}
```

---

## Agent-Readable Summary Format

Human-friendly prose is secondary. Use stable field names and directive-like content.

Recommended compiled summary payload:

```json
{
  "summary_contract": "agent_readable_project_context_v1",
  "project_identity": {
    "profile": "general",
    "project": "harness-self-governance",
    "one_line": "Hermes self-governance memory/control-plane project."
  },
  "routing_hints": {
    "aliases": ["graph harness", "self governance", "dashboard v2", "agent memory graph"],
    "negative_aliases": ["raw EHR", "dirtycsv data cleaning"],
    "default_entry_nodes": ["project_summary:general:harness-self-governance", "plan:general:harness-self-governance"]
  },
  "agent_priority_order": [
    "hard_constraints",
    "current_state",
    "active_phase",
    "plan.todo",
    "key_decisions",
    "evidence_paths"
  ],
  "hard_constraints": [],
  "current_state": [],
  "open_problems": [],
  "phase_boundaries": [],
  "key_decisions": [],
  "requirements": [],
  "evidence_paths": [],
  "miss_policy": {
    "if_no_project_match": "return_zero_hit_packet_then_offer_create_pending_project_or_run_explicit_discovery",
    "if_project_match_but_no_claim_match": "return_low_confidence_packet_with_summary_and_plan_only_then_require_user_or_single_deepening_decision",
    "if_claim_not_in_summary": "traverse_evidence_once_before_answering; if still absent record_context_gap",
    "if_new_user_decision": "capture_pending_update_not_compiled_memory",
    "if_user_supplies_new_knowledge": "create_pending_update_with_source=this_turn_then_wait_for_archive_gate",
    "fallback_budget_rule": "at_most_one_automatic_deepening_step; never_scan_all_docs_or_raw_sessions_by_default"
  }
}
```

---

## Retrieval Algorithm Roadmap

### Stage A — Deterministic baseline

Use no heavy dependency. Implement predictable graph scoring.

Scoring:

```text
node_score =
  query_match
+ type_priority
+ summary_priority
+ plan_priority
+ recency_hint
+ project_match
- context_cost
- raw_session_penalty

edge_score =
  edge_type_priority
+ evidence_strength
+ dependency_criticality
- traversal_cost
```

High-priority node types:

```text
project_summary > plan > constraint > requirement > decision > evidence > skill/tool > raw/session
```

High-priority edges:

```text
constrains, requires, decided_by, planned_by, summarizes, supports, cites, derived_from
```

### Stage B — Personalized PageRank / random-walk retrieval

Use project summary and plan nodes as seeds.

```text
seeds = query-matched entry nodes + project_summary + plan
personalized_pagerank(seeds)
select top nodes under budget
then close over constraints/evidence/dependencies
```

This prevents toy wiki behavior because the graph topology, not document order, determines what enters context.

### Stage C — Steiner-style connector expansion

When query touches multiple concepts, find low-cost connector paths between them:

```text
query nodes: [requirement:A, decision:B, constraint:C]
connectors: shortest weighted paths among query nodes and project summary
```

This preserves causal/decision chains instead of isolated snippets.

### Stage D — Optional embeddings only as candidate generator

Embeddings can propose candidate nodes, but graph policy decides final packet.

```text
semantic candidates -> graph scoring -> closure -> budgeted packet
```

Do not make vector search the primary memory system.

---

## Implementation Tasks

### Task 1: Add agent-readable summary contract tests

**Objective:** Lock the summary schema as runtime contract.

**Files:**
- Create: `tests/test_agent_memory_graph_agent_summary_contract.py`
- Modify later: compiled summary JSON files under `docs/examples/agent-memory-graph/`

**Test cases:**

```python
def test_compiled_summaries_expose_agent_contract():
    # load harness + dirtycsv compiled summaries
    # assert summary_contract == 'agent_readable_project_context_v1'
    # assert project_identity, routing_hints, agent_priority_order exist
    # assert hard_constraints/current_state/open_problems/phase_boundaries exist
    # assert miss_policy includes no-project, unknown-claim, new-user-decision behavior
```

**Command:**

```bash
cd /home/vanila/code/graph-harness-maintain
.venv/bin/python -m pytest tests/test_agent_memory_graph_agent_summary_contract.py -q
```

Expected first run: FAIL until summaries are migrated.

---

### Task 2: Migrate compiled summaries to agent-readable schema

**Objective:** Make summaries optimized for model routing, not human reading.

**Files:**
- Modify: `docs/examples/agent-memory-graph/harness-self-governance/compiled-session-project-scope-and-phase-boundary.json`
- Modify: `docs/examples/agent-memory-graph/ehrlab-dirtycsv/compiled-session-project-scope.json`

**Required fields:**

```text
summary_contract
project_identity
routing_hints.aliases
routing_hints.negative_aliases
routing_hints.default_entry_nodes
agent_priority_order
hard_constraints
current_state
open_problems
phase_boundaries
key_decisions
requirements
evidence_paths
miss_policy
project_plan.completed
project_plan.todo
```

**Verification:** Task 1 test passes.

---

### Task 3: Create `retrieve.py` high-level API

**Objective:** Add a single runtime entry point for Hermes/tooling.

**Files:**
- Create: `src/agent_memory_graph/retrieve.py`
- Create: `tests/test_agent_memory_graph_retrieve.py`

**Initial API:**

```python
def retrieve_project_context(
    repo_root: Path | str,
    query: str,
    profile_hint: str | None = None,
    project_hint: str | None = None,
    memory_root: Path | str | None = None,
    budget: str = "fast",
) -> dict[str, Any]:
    ...
```

**Behavior:**

1. Load context index.
2. Load governance graph and compiled project summaries.
3. Select project using hints + summary routing aliases.
4. Always include summary and plan entry nodes for selected project.
5. Call weighted traversal.
6. Render normalized packet.

**Verification:**

```bash
.venv/bin/python -m pytest tests/test_agent_memory_graph_retrieve.py -q
```

---

### Task 4: Add typed weighted traversal

**Objective:** Replace BFS-only traversal with budgeted weighted graph retrieval.

**Files:**
- Modify: `src/agent_memory_graph/traversal.py`
- Create: `tests/test_agent_memory_graph_weighted_traversal.py`

**Add function:**

```python
def traverse_weighted_subgraph(
    graph: dict[str, Any],
    seed_nodes: list[str],
    query: str,
    budget_nodes: int = 24,
    budget_edges: int = 40,
    max_depth: int = 2,
) -> dict[str, Any]:
    ...
```

**Rules:**

- Always retain seed nodes.
- Prefer `project_summary`, `plan`, `constraint`, `requirement`, `decision`.
- Exclude raw session nodes unless budget is `forensic`.
- Keep edge closure among selected nodes.
- Add constraint/requirement closure for selected project.

**Verification:**

- Query about plan includes `plan:*` node.
- Query about dashboard includes relevant decision/constraint nodes.
- Query under fast budget does not include raw sessions.

---

### Task 5: Add context packet renderer with normalized content

**Objective:** Return content, not only artifact paths.

**Files:**
- Modify: `src/agent_memory_graph/context_packet.py`
- Modify: `tests/test_agent_memory_graph_retrieve.py`

**Add normalized sections:**

```json
{
  "summary_first": {},
  "plan": {},
  "active_constraints": [],
  "relevant_requirements": [],
  "relevant_decisions": [],
  "evidence_paths": [],
  "read_order": []
}
```

**Policy:**

- Fast budget: summary + plan + top constraints/requirements.
- Normal budget: add decisions and evidence paths.
- Deep budget: add selected artifact references.
- Forensic budget: raw sessions allowed only if explicitly requested.

---

### Task 6: Add CLI command for agent retrieval

**Objective:** Make retriever callable before an agent task.

**Files:**
- Modify: `src/agent_memory_graph/cli.py`
- Modify: `tests/test_agent_memory_graph_cli.py`

**Command:**

```bash
.venv/bin/python -m agent_memory_graph retrieve \
  --repo /home/vanila/code/graph-harness-maintain \
  --query "怎么继续 dashboard v2 memory graph 工作" \
  --budget fast
```

**Expected output:** JSON context packet.

---

### Task 7: Add Hermes-facing context injection document

**Objective:** Define how Hermes should use graph memory before normal memory.

**Files:**
- Create: `docs/runtime/graph-memory-context-contract.md`

**Contract:**

```text
Before answering project-specific tasks:
1. call agent_memory_graph retrieve with current workspace and user query
2. if PASS, use summary_first + plan + constraints as primary context
3. use Hermes memory only for routing pointer and user preferences
4. if MISS, record context gap and ask/continue with explicit uncertainty
5. never read raw sessions unless forensic budget is explicit
```

This document is intentionally agent-facing, not user-facing.

---

### Task 8: Dashboard remains read-only observability plus explanation target

**Objective:** Keep the dashboard as the user's audit surface while preventing UI concerns from driving memory semantics.

**Files:**
- Modify: `src/graph_harness_maintain/dashboard.py` only if needed
- Modify: `tests/test_dashboard.py`
- Create/modify: `docs/runtime/graph-memory-context-contract.md`

**Acceptance criteria:**

- Dashboard stays read-only and does not mutate graph memory.
- Dashboard displays retrieval packet preview if available.
- Dashboard does not define summary semantics.
- Summary/plan display is derived from compiled contract.
- Node IDs and node metadata are stable enough that a user can ask: `这个 summary 节点是什么意思？`
- Agent can answer by reading the agent-readable node and rendering a human-readable explanation on demand.
- Human-readable explanation is not stored as canonical memory unless the user explicitly asks for documentation.

---

### Task 9: Add zero-hit, miss-policy, and pending-update integration

**Objective:** Unknown information flows into an explicit low-cost lifecycle instead of triggering an expensive fallback ladder.

**Files:**
- Modify: `src/agent_memory_graph/retrieve.py`
- Modify: `src/agent_memory_graph/context_gaps.py`
- Modify: `src/agent_memory_graph/pending_updates.py`
- Create: `tests/test_agent_memory_graph_miss_policy.py`

**Cases:**

```text
0-hit query:
  -> return status=MISS, hit_count=0, confidence=0.0
  -> do not scan all docs
  -> do not read raw sessions
  -> record context_gap
  -> recommended_action=create_pending_project | ask_for_scope | explicit_discovery

project hit but claim miss:
  -> return status=LOW_CONFIDENCE or MISS
  -> include only summary_first + plan + miss_policy
  -> allow at most one explicit evidence deepening step under normal/deep budget
  -> if still absent, record context_gap

new user decision or correction:
  -> status=NEW_INFORMATION
  -> create pending_update with source=current_turn
  -> link to candidate project/profile if confidence is high
  -> do not mutate compiled_memory directly

user supplies entirely new knowledge:
  -> create pending_update or pending_project_seed
  -> assign lifecycle_state=pending_update
  -> require archive_gate before compiled_memory
  -> after gate passes, update compiled summary/plan/evidence edges

conflicting summary/evidence:
  -> return BLOCKED or WARNING
  -> create pending_update(type=conflict)
  -> require archive_gate/manual review before replacing compiled memory
```

**Fallback budget rule:**

```text
automatic fallback depth <= 1
raw_sessions_allowed == false unless budget=forensic and user explicitly requests forensic lookup
if hit_count == 0, do not escalate through fast -> normal -> deep -> forensic automatically
agent must either ask, create a pending update/project seed, or request explicit discovery authorization
```

**New knowledge ingestion path:**

```text
current user message
  -> classify as new fact / correction / decision / requirement / constraint / plan item
  -> write pending_update JSONL record
  -> attach source=this_turn and project candidate
  -> expose in retrieval packet as pending_context, not compiled_memory
  -> archive gate compiles it later into summary/plan/graph edges
```

**Verification:**

```bash
.venv/bin/python -m pytest tests/test_agent_memory_graph_miss_policy.py -q
```

---

### Task 10: Add retrieval quality tests

**Objective:** Make efficiency measurable.

**Files:**
- Create: `tests/test_agent_memory_graph_retrieval_quality.py`

**Metrics:**

```text
selected_node_count <= budget
raw_sessions_allowed == false under fast/normal/deep
summary_first exists for PASS
plan exists for PASS
constraints included for project-specific tasks
misses recorded instead of hallucinated routing
0-hit retrieval does not trigger automatic deep/raw fallback
new user knowledge creates pending_update rather than compiled_memory mutation
human-readable node explanations can be generated from agent-readable node metadata
```

Optional later metrics:

```text
estimated_tokens
coverage_score
closure_score
routing_confidence
```

---

## Acceptance Criteria

The implementation is acceptable when:

```bash
cd /home/vanila/code/graph-harness-maintain
.venv/bin/python -m pytest tests/test_agent_memory_graph_agent_summary_contract.py tests/test_agent_memory_graph_retrieve.py tests/test_agent_memory_graph_weighted_traversal.py tests/test_agent_memory_graph_retrieval_quality.py -q
.venv/bin/python -m pytest tests/test_dashboard.py tests/test_archive_lifecycle_dashboard_pipeline.py -q
/usr/bin/python3 -m py_compile src/agent_memory_graph/retrieve.py src/agent_memory_graph/traversal.py src/agent_memory_graph/context_packet.py
.venv/bin/agent-graph validate --repo .
```

Expected:

```text
all tests pass
validate status: PASS
retrieval packets include summary_first and plan
fast/normal retrieval does not include raw sessions
zero-hit retrieval returns MISS with hit_count=0 and no automatic deep/raw fallback
new knowledge is recorded as pending_update or pending_project_seed before archive_gate
read-only dashboard remains an audit/observability surface, not the source of truth
```

---

## Rollback Plan

All changes are additive until Task 8.

Rollback:

```bash
git restore src/agent_memory_graph/retrieve.py \
  src/agent_memory_graph/traversal.py \
  src/agent_memory_graph/context_packet.py \
  src/agent_memory_graph/cli.py

git restore tests/test_agent_memory_graph_agent_summary_contract.py \
  tests/test_agent_memory_graph_retrieve.py \
  tests/test_agent_memory_graph_weighted_traversal.py \
  tests/test_agent_memory_graph_retrieval_quality.py

git restore docs/runtime/graph-memory-context-contract.md
```

If compiled summary migration causes issues, restore only the affected JSON files:

```bash
git restore docs/examples/agent-memory-graph/harness-self-governance/compiled-session-project-scope-and-phase-boundary.json
git restore docs/examples/agent-memory-graph/ehrlab-dirtycsv/compiled-session-project-scope.json
```

---

## Next Recommended Step

Start with Tasks 1-3 in one iteration:

1. lock the agent-readable summary contract;
2. migrate harness + dirtycsv summaries;
3. add `retrieve_project_context()` returning summary-first packets.

Do not start with dashboard. Dashboard is now secondary observability.
