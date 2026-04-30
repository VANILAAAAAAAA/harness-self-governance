from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).parents[1]
SUMMARY_PATHS = [
    REPO / "docs/examples/agent-memory-graph/harness-self-governance/compiled-session-project-scope-and-phase-boundary.json",
    REPO / "docs/examples/agent-memory-graph/ehrlab-dirtycsv/compiled-session-project-scope.json",
]


def test_compiled_summaries_expose_agent_readable_contract() -> None:
    required = {
        "summary_contract", "project_identity", "routing_hints", "agent_priority_order",
        "project_goal", "current_state", "open_problems", "phase_boundaries",
        "key_decisions", "requirements", "evidence_paths", "miss_policy", "project_plan",
    }
    for path in SUMMARY_PATHS:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["summary_contract"] == "agent_readable_project_context_v1", path
        assert required <= set(data), path
        assert data["routing_hints"]["aliases"]
        assert data["routing_hints"]["default_entry_nodes"]
        assert "hard_constraints" in data["agent_priority_order"]
        assert data["miss_policy"]["if_no_project_match"].startswith("return_zero_hit_packet")
        assert "fallback_budget_rule" in data["miss_policy"]
        assert isinstance(data["project_plan"]["completed"], list)
        assert isinstance(data["project_plan"]["todo"], list)
