from __future__ import annotations

import json
import re
from pathlib import Path

from graph_harness_maintain.dashboard import build_dashboard, build_dashboard_data, build_graph_summary, collect_file_inventory, render_preview

ROOT = Path(__file__).parents[1]


def _embedded_data(html: str) -> dict:
    match = re.search(r'<script id="governance-data" type="application/json">(.*?)</script>', html, flags=re.S)
    assert match, "embedded governance-data script not found"
    return json.loads(match.group(1))


def test_dashboard_file_generated_as_two_page_graph_logs_app() -> None:
    report = build_dashboard(ROOT, ROOT / "artifacts" / "v2" / "dashboard" / "test-index.html")

    assert report["status"] == "PASS"
    dashboard = ROOT / report["path"]
    assert dashboard.exists()
    html = dashboard.read_text(encoding="utf-8")
    for needle in [
        "Governance Hub",
        "#/graph",
        "#/logs",
        "data-route=\"graph\"",
        "data-route=\"logs\"",
        "Governance Graph",
        "Agent Memory Graph",
        "Governance (default)",
        "Memory",
        "data-graph-dataset=\"governance\"",
        "data-graph-dataset=\"memory\"",
        "Logs",
        "System Health",
        "READ ONLY",
        "graph-canvas",
        "node-inspector",
        "edge-inspector",
        "File Explorer",
        "Preview",
        "Raw",
        "Metadata",
        "Lineage",
        "governance-data",
        "Drag nodes to reposition",
        "Click nodes or edges to inspect",
        "Scroll to zoom",
        "selectNode",
        "selectEdge",
        "startNodeDrag",
        "fitGraphToVisible",
        "applyZoom",
        "panZoomState",
        "type-filter-panel",
        "visible-node-count",
        "filterNodesByType",
        "clearGraphFilters",
        "activeGraphTypes",
        "activeEdgeTypes",
        "renderTypeFilters",
        "renderEdgeFilters",
        "filterEdgesByType",
        "edge-filter-chips",
        "edge-control",
        "edge-hit",
        "data-edge-id",
        "data-node-id",
        "role","button",
        "tabindex",
        "selectEdge(edgeId)",
        "edgeLogPath",
        "locateLogPath",
        "viewSelectedGraphInLogs",
        "No direct log mapping",
        "Profile: general",
        "profile-switcher",
        "data-profile-id=\"general\"",
        "data-profile-id=\"ehrlab\"",
        "Project: harness-self-governance",
        "project-selector",
        "profile_index",
        "projects",
        "lineage_index",
        "mappingStatusForRef",
        "preferred_path",
        "view_in_logs_requires_mapping",
        "No projects archived for this profile yet",
        "Graph diagnostic summary",
        "graph_summary",
        "graphs",
        "graph_summaries",
        "agent-memory-graph.json",
        "Traversal hubs",
        "focus-hubs",
        "data-graph-mode=\"overview\"",
        "data-graph-mode=\"focus\"",
        "data-graph-mode=\"full\"",
        "Overview · curated",
        "Focus · 1-hop",
        "Overview = curated system map",
        "activeGraphMode = 'overview'",
        "setGraphMode('overview')",
        "data-inspector-tab=\"inspect\"",
        "data-inspector-tab=\"edge\"",
        "data-inspector-tab=\"summary\"",
        "setInspectorTab",
        "renderInspector",
        "Connected edges",
        "Exact mapping:",
        "related-log mapping is deferred",
        "#logs-route.active",
        "logs-scroll-hint",
        "Use the File Explorer, Table, and Preview scrollbars",
        "html, body",
        "overflow:hidden",
        "overflow:auto",
        "activeLogGroup",
        "selectLogGroup",
        "file-table-scroll",
        "table-scroll-down",
        "preview-scroll-down",
        "withLineNumbers",
        "scrollById",
        "toggleTheme",
        "startCanvasPan",
        "finishCanvasPan",
        "panCanvasMove",
        "contextmenu",
        "ev.button === 0 || ev.button === 2",
        "isCanvasPanning",
        "folder-row:hover",
        "tr:hover",
        "min-height:0",
    ]:
        assert needle in html
    assert "toggleTheme" in html
    assert "location.hash = '#/logs'" not in html
    assert "\\n\\n[local preview truncated]" in html
    assert "<script src=" not in html
    assert "<link rel=\"stylesheet\"" not in html


def test_dashboard_embeds_graph_logs_sessions_and_safety_data() -> None:
    report = build_dashboard(ROOT)
    html = (ROOT / report["path"]).read_text(encoding="utf-8")
    data = _embedded_data(html)

    assert data["graph"]["nodes"]
    assert data["graph"]["edges"]
    assert data["graphs"]["governance"]["nodes"]
    assert "memory" in data["graphs"]
    assert "sessions" in data
    assert data["safety_boundary"] == {
        "read_only_ui": True,
        "destructive_operations_allowed": False,
        "graph_mutation_allowed": False,
        "remote_publication_allowed": False,
        "sensitive_export_allowed": False,
    }
    assert "file_inventory" in data
    assert any(item["group"] in {"artifacts", "policies", "proposals", "provenance", "system"} for item in data["file_inventory"])
    assert "governance-graph.json" in html
    assert "agent-memory-graph.json" in html
    assert "session-index.json" in html
    assert data["graph_filter_types"]
    assert data["edge_filter_types"]
    assert "governance" in data["graph_filter_catalog"]
    assert "memory" in data["graph_filter_catalog"]
    assert data["graph_summary"]["node_count"] == len(data["graph"]["nodes"])
    assert data["graph_summary"]["edge_count"] == len(data["graph"]["edges"])
    assert data["graph_summary"]["diagnostics"]
    assert data["graph_summary"]["hubs"]
    assert "tool" in data["graph_filter_types"]
    assert "knowledge_source" in data["graph_filter_types"]
    assert data["log_groups"] == ["profiles", "projects", "sessions", "summaries", "decisions", "requirements", "artifacts", "policies", "provenance", "system"]
    assert data["profile_index"]["active_profile"] == "general"
    assert {profile["profile_id"] for profile in data["profile_index"]["profiles"]} >= {"general", "ehrlab"}
    assert data["projects"]["default_project"] == "harness-self-governance"
    assert data["lineage_index"]["schema_version"] == "2.0"
    assert data["pipeline_status"].get("llm_hub_api_enabled") is False
    assert data["pipeline_status"].get("agent_triggered_archive") is True


def test_collect_file_inventory_handles_missing_dirs_and_previews_json(tmp_path: Path) -> None:
    repo = tmp_path
    sample = repo / "artifacts" / "v2" / "graph" / "governance-graph.json"
    sample.parent.mkdir(parents=True)
    sample.write_text(json.dumps({"z": 1, "a": [1, 2]}, sort_keys=True), encoding="utf-8")
    (repo / "policies").mkdir()
    (repo / "policies" / "approval-gates.yaml").write_text("status: read_only\n", encoding="utf-8")

    inventory, warnings = collect_file_inventory(repo)

    assert any(item["path"] == "artifacts/v2/graph/governance-graph.json" for item in inventory)
    assert any("missing optional local directory" in warning for warning in warnings)
    json_item = next(item for item in inventory if item["path"].endswith("governance-graph.json"))
    assert json_item["type"] == "JSON"
    assert json_item["preview"].startswith("{")
    assert '"a"' in json_item["preview"]
    assert json_item["lineage"]


def test_render_preview_truncates_large_text() -> None:
    preview, truncated = render_preview("x" * 5000, max_chars=120)

    assert truncated is True
    assert len(preview) < 180
    assert preview.endswith("… [truncated]")


def test_dashboard_data_is_deterministic_except_timestamps() -> None:
    first = build_dashboard_data(ROOT)
    second = build_dashboard_data(ROOT)

    for data in (first, second):
        data["graph"]["generated_at"] = "normalized"
        data["sessions"]["generated_at"] = "normalized"
        for item in data["file_inventory"]:
            item["modified"] = "normalized"
            item["modified_epoch"] = 0
    assert first == second


def test_build_graph_summary_reports_density_hubs_and_broken_edges() -> None:
    graph = {
        "nodes": [
            {"id": "a", "type": "tool", "label": "A"},
            {"id": "b", "type": "policy", "label": "B"},
            {"id": "c", "type": "report", "label": "C"},
        ],
        "edges": [
            {"id": "e1", "source": "a", "target": "b", "type": "governed_by"},
            {"id": "e2", "source": "a", "target": "c", "relation": "generated"},
            {"id": "e3", "source": "a", "target": "missing", "type": "references"},
        ],
    }

    summary = build_graph_summary(graph)

    assert summary["node_count"] == 3
    assert summary["edge_count"] == 3
    assert summary["broken_edge_count"] == 1
    assert summary["edge_type_counts"]["generated"] == 1
    assert summary["hubs"][0]["id"] == "a"
    assert summary["diagnostics"]
