from __future__ import annotations

from pathlib import Path

from agent_memory_graph.bootstrap import bootstrap_repo
from agent_memory_graph.context_index import build_context_index
from agent_memory_graph.traversal import traverse_memory_graph
from graph_harness_maintain.pipeline import run_v2_0_rc

from tests.test_agent_memory_graph_context_index import seed_memory


def test_traverse_from_known_node_returns_nodes_edges_and_artifacts(tmp_path: Path) -> None:
    repo, memory_root = seed_memory(tmp_path)
    build_context_index(repo, memory_root)

    report = traverse_memory_graph(repo, "project:general:harness-self-governance", memory_root, max_depth=2)

    assert report["status"] == "PASS"
    assert report["start_node"] == "project:general:harness-self-governance"
    assert report["max_depth"] == 2
    assert "project:general:harness-self-governance" in report["visited_nodes"]
    assert report["visited_edges"]
    assert report["selected_artifacts"]
    assert report["traversal_reason"] == "bounded_agent_memory_graph_traversal"
    assert report["budget_used"]["raw_sessions_allowed"] is False


def test_bootstrap_reports_router_availability_and_forensic_only_raw_sessions(tmp_path: Path) -> None:
    repo, memory_root = seed_memory(tmp_path)

    report = bootstrap_repo(repo, memory_root, context_budget="fast")

    assert report["status"] == "PASS"
    assert report["default_budget"] == "fast"
    assert report["graph_traversal_router_available"] is True
    assert report["context_index_available"] is True
    assert report["novelty_aware_routing"] is True
    assert report["raw_sessions_policy"] == "explicit_forensic_only"
    assert report["raw_sessions_default_read"] is False


def test_v2_pipeline_reports_budgeted_context_router_support() -> None:
    data = run_v2_0_rc(Path(__file__).parents[1])

    assert data["status"] in {"PASS", "PASS_WITH_WARNINGS"}
    assert data["budgeted_context_router_supported"] is True
    assert data["context_index_available"] is True
    assert data["graph_traversal_context_protocol"] is True
    assert data["novelty_aware_context_policy"] is True
    assert data["raw_sessions_default_read"] is False
