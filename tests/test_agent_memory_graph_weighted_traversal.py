from __future__ import annotations

from agent_memory_graph.traversal import traverse_weighted_subgraph


def test_weighted_traversal_prefers_summary_plan_constraints_and_excludes_raw_sessions() -> None:
    graph = {
        "nodes": [
            {"id": "project:general:harness", "type": "project", "label": "harness"},
            {"id": "project_summary:general:harness", "type": "project_summary", "label": "summary"},
            {"id": "plan:general:harness", "type": "plan", "label": "plan"},
            {"id": "constraint:no-raw", "type": "constraint", "label": "raw sessions last"},
            {"id": "session:raw", "type": "session", "label": "raw session"},
        ],
        "edges": [
            {"id": "e1", "source": "project:general:harness", "target": "project_summary:general:harness", "type": "summarizes"},
            {"id": "e2", "source": "project:general:harness", "target": "plan:general:harness", "type": "planned_by"},
            {"id": "e3", "source": "project_summary:general:harness", "target": "constraint:no-raw", "type": "constrains"},
            {"id": "e4", "source": "project:general:harness", "target": "session:raw", "type": "archives_session"},
        ],
    }

    report = traverse_weighted_subgraph(graph, ["project_summary:general:harness", "plan:general:harness"], "raw sessions policy", budget_nodes=4)

    assert report["status"] == "PASS"
    assert "project_summary:general:harness" in report["selected_nodes"]
    assert "plan:general:harness" in report["selected_nodes"]
    assert "constraint:no-raw" in report["selected_nodes"]
    assert "session:raw" not in report["selected_nodes"]
    assert report["raw_sessions_allowed"] is False
