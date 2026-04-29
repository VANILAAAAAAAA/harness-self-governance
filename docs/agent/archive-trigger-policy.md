# Archive trigger policy

## Purpose

The Archive Trigger Policy is the production recommendation layer for the Agent Memory Graph.
It does **not** archive sessions automatically.
It classifies durable project events into explicit archive recommendations so the agent, reviewer, and dashboard can see when manual archive work should be considered.

The policy exists because v2.0 now has:

- live session vs compiled memory boundaries
- manual `compiled-session` fixtures
- archive gate and archive maintenance reporting
- graph-governed context loading
- dashboard Archive Lifecycle visibility

What is still intentionally missing is automatic archive execution.

## Core boundary

The trigger policy is recommendation-only.

It must preserve these constraints:

- `archive_auto_apply_enabled: false`
- manual archive review remains required
- no raw sessions are required by default
- no graph mutation execution
- no destructive apply
- no Hub-side LLM API
- no backend dependency

A trigger can recommend one of the following actions:

- `no_action`
- `capture_pending_update`
- `create_compiled_candidate`
- `create_maintenance_proposal`
- `recommend_manual_archive`

These are advisory outcomes, not execution permissions.

## Supported trigger types

| Trigger type | Recommended action | Why |
|---|---|---|
| `milestone_completed` | `recommend_manual_archive` | milestone closure usually marks durable project knowledge |
| `pr_merged` | `recommend_manual_archive` | merged implementation may justify curated archive review |
| `release_tagged` | `recommend_manual_archive` | release points are durable memory boundaries |
| `architecture_decision` | `create_compiled_candidate` | architecture choices should become curated compiled memory |
| `new_long_term_requirement` | `create_compiled_candidate` | new long-lived requirements belong in project memory |
| `new_constraint` | `create_compiled_candidate` | new durable constraints should be captured explicitly |
| `context_gap_detected` | `create_maintenance_proposal` | unresolved gaps require reviewed maintenance work |
| `pending_update_accumulated` | `capture_pending_update` | new information should stay buffered until reviewed |
| `stale_summary_detected` | `create_maintenance_proposal` | stale summaries need maintenance before archive quality degrades |
| `user_requested_archive` | `recommend_manual_archive` | explicit operator intent should surface the manual archive path |

Unknown or transient events fall back to `no_action`.

## CLI

### Evaluate one event

```bash
agent-graph triggers evaluate --input /tmp/archive-event.json --memory-root "$TMP_MEM"
```

Expected input schema:

```json
{
  "schema_version": "2.0",
  "event_type": "architecture_decision",
  "profile_id": "general",
  "project_id": "harness-self-governance",
  "summary": "v2.0 keeps archive automation proposal-based and disables auto-apply.",
  "source": "manual-test"
}
```

The command records the evaluated event under the memory root and returns the recommended action.

### Build the report

```bash
agent-graph triggers report --repo . --memory-root "$TMP_MEM"
```

Output path:

- `<memory-root>/reports/archive-trigger-report.json`

Repo-local projection after `agent-graph export --repo . --memory-root "$TMP_MEM"`:

- `artifacts/v2/maintenance/archive-trigger-report.json`

## Report shape

The report summarizes policy availability, recommendation counts, and latest recommendations.

Key fields:

- `trigger_policy_active`
- `archive_auto_apply_enabled`
- `manual_archive_required`
- `user_requested_archive_supported`
- `milestone_archive_recommendation_supported`
- `raw_sessions_default_read`
- `counts_by_action`
- `counts_by_trigger`
- `recommendation_count`
- `latest_recommendation_count`
- `latest_recommendations`

## Dashboard projection

The v2 dashboard remains Graph + Logs only.
The Archive Lifecycle summary now adds compact trigger policy state:

- `trigger policy: active`
- `auto archive: disabled`
- `manual archive: required`
- `latest recommendation count`

This keeps recommendation visibility in the read-only UI without enabling auto-archive behavior.

## Relationship to manual archive bootstrap

Trigger policy does not replace curated `compiled-session` examples.
It sits one layer earlier in the lifecycle:

```text
project event
-> trigger evaluation
-> recommendation
-> human/agent review
-> compiled-session candidate or maintenance proposal
-> archive-session (manual, explicit)
-> export
-> dashboard / router projection
```

The committed compiled-session fixtures remain the gold standard for what good archive input looks like.
Trigger policy only decides when archive review should be suggested.

## Validation

Recommended checks:

```bash
python -m pytest -q tests/test_agent_memory_graph_archive_triggers.py tests/test_archive_lifecycle_dashboard_pipeline.py
agent-graph triggers evaluate --help
agent-graph triggers report --help
```

For full repo validation:

```bash
python -m pytest -q
python -m graph_harness_maintain pipeline local-rc --ci
python -m graph_harness_maintain pipeline v2.0-rc
```
