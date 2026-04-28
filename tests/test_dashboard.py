from __future__ import annotations

import json
import re
from pathlib import Path

from graph_harness_maintain.dashboard import build_dashboard, build_dashboard_data, collect_file_inventory, render_preview

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
        "applyZoom",
        "panZoomState",
    ]:
        assert needle in html
    assert "<script src=" not in html
    assert "<link rel=\"stylesheet\"" not in html


def test_dashboard_embeds_graph_logs_sessions_and_safety_data() -> None:
    report = build_dashboard(ROOT)
    html = (ROOT / report["path"]).read_text(encoding="utf-8")
    data = _embedded_data(html)

    assert data["graph"]["nodes"]
    assert data["graph"]["edges"]
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
    assert "session-index.json" in html


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
