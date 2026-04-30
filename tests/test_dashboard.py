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
        "includeNodeType",
        "excludeNodeType",
        "excludedGraphTypes",
        "Filter / block types",
        "Search node types, e.g. tool or skill",
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
        "Project-first map",
        "dirtycsv",
        "project-card",
        "Graph diagnostic summary",
        "Context Router",
        "Budgeted traversal",
        "Historical raw sessions: forensic only",
        "Current session raw: live context preserved",
        "data-router-sample=\"view-in-logs\"",
        "data-router-sample=\"log定位\"",
        "data-router-sample=\"new-information\"",
        "context_router",
        "router-samples.json",
        "context-index.json",
        "context-packets.json",
        "context-gaps.json",
        "pending-updates.json",
        "Intent",
        "Matched topics",
        "Entry nodes",
        "Selected artifacts",
        "raw_sessions_allowed",
        "requires_llm_gate",
        "Context packet",
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
        "scopedHubId",
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
    assert "skill" in data["graph_filter_types"]
    assert "plan" in data["graph_filter_types"]
    assert "knowledge_source" in data["graph_filter_types"]
    harness_summary = next(node for node in data["graph"]["nodes"] if node["id"] == "project_summary:general:harness-self-governance")
    harness_sections = harness_summary["metadata"]["summary_sections"]
    assert harness_sections["project_goal"]
    assert harness_sections["project_status"]
    assert harness_sections["current_problems"]
    assert harness_sections["phase_boundaries"]
    assert harness_sections["key_decisions"]
    assert harness_sections["read_order"]
    assert harness_sections["memory_lifecycle"]["archive_gate"]
    assert harness_sections["project_plan"]["completed"]
    assert harness_sections["project_plan"]["todo"]
    assert any(node["id"] == "plan:general:harness-self-governance" for node in data["graph"]["nodes"])
    dirty_summary = next(node for node in data["graph"]["nodes"] if node["id"] == "project_summary:ehrlab:dirtycsv")
    sections = dirty_summary["metadata"]["summary_sections"]
    assert sections["project_goal"]
    assert sections["project_status"]
    assert sections["current_problems"]
    assert sections["phase_boundaries"]
    assert sections["key_decisions"]
    assert sections["purpose"]
    assert sections["actions"]
    assert sections["results"]
    assert sections["requirements"]
    assert sections["constraints"]
    assert sections["cautions"]
    assert sections["evidence_paths"]
    assert sections["read_order"]
    assert sections["memory_lifecycle"]["pending_update"]
    assert sections["memory_lifecycle"]["archive_gate"]
    assert sections["project_plan"]["completed"]
    assert sections["project_plan"]["todo"]
    assert sections["key_skills"]
    assert sections["key_tools"]
    assert any(node["id"] == "plan:ehrlab:dirtycsv" for node in data["graph"]["nodes"])
    assert any(node["id"] == "skill:graph-harness-maintain" for node in data["graph"]["nodes"])
    assert any(node["id"] == "tool:python" for node in data["graph"]["nodes"])
    assert data["log_groups"] == ["profiles", "projects", "sessions", "summaries", "decisions", "requirements", "artifacts", "policies", "provenance", "system"]
    assert data["profile_index"]["active_profile"] == "general"
    assert {profile["profile_id"] for profile in data["profile_index"]["profiles"]} >= {"general", "ehrlab"}
    assert data["projects"]["default_project"] == "harness-self-governance"
    assert data["lineage_index"]["schema_version"] == "2.0"
    assert data["pipeline_status"].get("llm_hub_api_enabled") is False
    assert data["pipeline_status"].get("agent_triggered_archive") is True
    assert data["context_router"]["available"] is True
    assert data["context_router"]["raw_sessions_default_read"] is False
    assert data["context_router"]["raw_sessions_policy"] == "historical_raw_sessions_explicit_forensic_only; current_live_session_raw_context_preserved_by_hermes"
    assert data["context_router"]["current_session_raw_context"] == "preserved_by_hermes_live_context_not_graph_memory"
    assert data["context_router"]["compiled_memory_raw_session_reads"] is False
    router = data["context_router"]
    assert router["index_path"].endswith("context-index.json")
    assert router["context_index"]["routing_table_type"] == "graph_traversal_context_index"
    assert router["artifacts"]["context_packets"].endswith("context-packets.json")
    assert router["artifacts"]["context_gaps"].endswith("context-gaps.json")
    assert router["artifacts"]["pending_updates"].endswith("pending-updates.json")
    assert {sample["id"] for sample in router["sample_queries"]} >= {"view-in-logs", "log定位", "new-information"}
    samples = {sample["id"]: sample for sample in router["sample_queries"]}
    assert samples["new-information"]["candidate_intents"] == ["new_information"]
    assert samples["new-information"]["raw_sessions_allowed"] is False
    assert samples["new-information"]["pending_update"] is True
    assert samples["log定位"]["candidate_intents"] == ["retrieve_existing"]
    assert samples["log定位"]["matched_topics"] or samples["log定位"]["matched_aliases"]
    assert router["context_gaps"]["count"] == len(router["context_gaps"]["gaps"])
    assert router["pending_updates"]["count"] == len(router["pending_updates"]["items"])


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
