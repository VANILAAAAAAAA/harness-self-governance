from __future__ import annotations

import json
from pathlib import Path

from graph_harness_maintain.graph_export import REQUIRED_EDGE_TYPES, REQUIRED_NODE_TYPES, build_governance_graph, write_governance_graph

ROOT = Path(__file__).parents[1]


def test_graph_export_schema_and_required_types() -> None:
    graph = build_governance_graph(ROOT)

    assert graph["schema_version"] == "2.0"
    assert set(graph) == {"schema_version", "generated_at", "summary", "nodes", "edges", "warnings", "blockers"}
    assert graph["blockers"] == []
    assert REQUIRED_NODE_TYPES.issubset({node["type"] for node in graph["nodes"]})
    assert "profile" in {node["type"] for node in graph["nodes"]}
    assert "project" in {node["type"] for node in graph["nodes"]}
    assert "project_summary" in {node["type"] for node in graph["nodes"]}
    assert "owns_project" in {edge["type"] for edge in graph["edges"]}
    assert "maps_to_log" in {edge["type"] for edge in graph["edges"]}


def test_graph_export_is_deterministic_except_timestamp() -> None:
    first = build_governance_graph(ROOT)
    second = build_governance_graph(ROOT)

    first["generated_at"] = "normalized"
    second["generated_at"] = "normalized"
    assert first == second
    assert [node["id"] for node in first["nodes"]] == sorted(node["id"] for node in first["nodes"])
    assert [edge["id"] for edge in first["edges"]] == sorted(edge["id"] for edge in first["edges"])


def test_graph_export_includes_governance_concepts_and_writes_json() -> None:
    out = ROOT / "artifacts" / "v2" / "graph" / "test-governance-graph.json"
    report = write_governance_graph(ROOT, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    labels = "\n".join(node["label"] for node in data["nodes"])

    assert report["status"] == "PASS"
    assert report["path"] == "artifacts/v2/graph/test-governance-graph.json"
    for needle in [
        "v1 local pipeline",
        "v1.1 proposal pipeline",
        "approval gates",
        "adapter report",
        "provenance current-state",
        "release audit",
        "generated artifacts",
    ]:
        assert needle in labels
    assert data["summary"]["read_only"] is True
    assert data["summary"]["destructive_operations_allowed"] is False
    assert all("kind" in node and "status" in node and "tags" in node and "metadata" in node and "description" in node for node in data["nodes"])
    assert all("label" in edge and "relation" in edge and "metadata" in edge for edge in data["edges"])


def test_graph_export_expands_local_capability_inventory() -> None:
    graph = build_governance_graph(ROOT)
    nodes = graph["nodes"]
    edges = graph["edges"]
    node_ids = {node["id"] for node in nodes}

    assert len(nodes) >= 45
    assert len(edges) >= 45
    assert "tool:cli:graph-export" in node_ids
    assert "tool:cli:dashboard-build" in node_ids
    assert "tool:cli:sessions-compress" in node_ids
    assert "tool:cli:pipeline-v2.0-rc" in node_ids
    assert any(node["id"].startswith("knowledge:src-module:") for node in nodes)
    assert any(node["id"].startswith("knowledge:test:") for node in nodes)
    assert any(node["id"].startswith("knowledge:doc:") for node in nodes)
    assert any(node["id"].startswith("knowledge:policy:") for node in nodes)
    assert any(node["type"] == "tool" and "skill" in node["tags"] for node in nodes)
    assert any(edge["type"] == "uses_tool" and edge["target"].startswith("tool:cli:") for edge in edges)
    assert any(edge["type"] == "references" and edge["target"].startswith("knowledge:doc:") for edge in edges)
