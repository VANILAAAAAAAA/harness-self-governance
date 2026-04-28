from __future__ import annotations

from pathlib import Path

from graph_harness_maintain.dashboard import build_dashboard

ROOT = Path(__file__).parents[1]


def test_dashboard_file_generated_with_required_panels() -> None:
    report = build_dashboard(ROOT, ROOT / "artifacts" / "v2" / "dashboard" / "test-index.html")

    assert report["status"] == "PASS"
    dashboard = ROOT / report["path"]
    assert dashboard.exists()
    html = dashboard.read_text(encoding="utf-8")
    for needle in [
        "System Health",
        "Governance Graph",
        "Logic Flow",
        "Tools",
        "Knowledge",
        "Sessions",
        "Artifacts",
        "Safety Boundary",
        "status-card",
        "No external CDN",
        "read-only",
    ]:
        assert needle in html
    assert "https://" not in html
    assert "http://" not in html
    assert "<script" in html


def test_dashboard_uses_local_graph_and_session_data() -> None:
    report = build_dashboard(ROOT)
    html = (ROOT / report["path"]).read_text(encoding="utf-8")

    assert "governance-graph.json" in html
    assert "session-index.json" in html
    assert "pipeline status" in html.lower()
    assert "destructive operations" in html.lower()
    assert "graph mutation" in html.lower()
