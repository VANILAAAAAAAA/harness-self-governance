from __future__ import annotations

import json
import re
from pathlib import Path

from graph_harness_maintain.dashboard import build_dashboard, build_dashboard_data
from graph_harness_maintain.pipeline import run_v2_0_rc

ROOT = Path(__file__).parents[1]


def _embedded_data(html: str) -> dict:
    match = re.search(r'<script id="governance-data" type="application/json">(.*?)</script>', html, flags=re.S)
    assert match, "embedded governance-data script not found"
    return json.loads(match.group(1))


def test_v2_pipeline_reports_archive_lifecycle_governance_fields() -> None:
    data = run_v2_0_rc(ROOT)

    assert data["status"] in {"PASS", "PASS_WITH_WARNINGS"}
    assert data["live_session_boundary_supported"] is True
    assert data["archive_gate_available"] is True
    assert data["archive_maintenance_available"] is True
    assert data["archive_trigger_policy_available"] is True
    assert data["archive_trigger_report_available"] is True
    assert data["archive_auto_apply_enabled"] is False
    assert data["user_requested_archive_supported"] is True
    assert data["milestone_archive_recommendation_supported"] is True
    assert data["live_session_priority"] is True
    assert data["pending_update_supported"] is True
    assert data["compiled_candidate_requires_review"] is True
    assert data["forensic_raw_sessions_explicit_only"] is True
    assert data["raw_sessions_default_read"] is False
    assert data["archive_quality_status"] in {"PASS", "PASS_WITH_WARNINGS"}
    assert data["pending_updates_count"] >= 0
    assert data["context_gaps_count"] >= 0
    assert data["stale_summaries_count"] >= 0
    assert data["compiled_candidates_count"] >= 0
    assert data["forensic_only_count"] >= 0
    for rel in [
        "artifacts/v2/maintenance/archive-gate-report.json",
        "artifacts/v2/maintenance/archive-maintenance-report.json",
        "artifacts/v2/maintenance/archive-maintenance-proposal.json",
        "artifacts/v2/maintenance/archive-trigger-report.json",
    ]:
        assert rel in data["artifacts"]
        assert (ROOT / rel).exists()


def test_dashboard_embeds_archive_lifecycle_summary_in_graph_page() -> None:
    report = build_dashboard(ROOT)
    html = (ROOT / report["path"]).read_text(encoding="utf-8")
    data = _embedded_data(html)

    assert "Archive Lifecycle" in html
    assert "live session: active" in html.lower()
    assert "pending updates" in html.lower()
    assert "compiled candidates" in html.lower()
    assert "context gaps" in html.lower()
    assert "stale summaries" in html.lower()
    assert "archive quality" in html.lower()
    assert "raw sessions: forensic only" in html.lower()
    assert "trigger policy: active" in html.lower()
    assert "auto archive: disabled" in html.lower()
    assert "manual archive: required" in html.lower()
    assert "latest recommendation count" in html.lower()
    assert "archive-lifecycle-summary" in html

    lifecycle = data["archive_lifecycle"]
    assert lifecycle["live_session_priority"] is True
    assert lifecycle["raw_sessions_default_read"] is False
    assert lifecycle["raw_sessions_policy"] == "explicit_forensic_only"
    assert lifecycle["compiled_candidate_requires_review"] is True
    assert lifecycle["trigger_policy_active"] is True
    assert lifecycle["archive_auto_apply_enabled"] is False
    assert lifecycle["manual_archive_required"] is True
    assert lifecycle["latest_recommendation_count"] >= 0
    assert lifecycle["pending_updates_count"] >= 0
    assert lifecycle["context_gaps_count"] >= 0
    assert lifecycle["stale_summaries_count"] >= 0
    assert lifecycle["compiled_candidates_count"] >= 0
    assert lifecycle["forensic_only_count"] >= 0


def test_dashboard_data_exposes_archive_lifecycle_projection() -> None:
    data = build_dashboard_data(ROOT)
    lifecycle = data["archive_lifecycle"]
    pipeline_status = data["pipeline_status"]

    assert lifecycle["summary_path"] == "artifacts/v2/maintenance/archive-maintenance-report.json"
    assert lifecycle["proposal_path"] == "artifacts/v2/maintenance/archive-maintenance-proposal.json"
    assert lifecycle["gate_path"] == "artifacts/v2/maintenance/archive-gate-report.json"
    assert lifecycle["trigger_report_path"] == "artifacts/v2/maintenance/archive-trigger-report.json"
    assert pipeline_status["archive_gate_available"] is True
    assert pipeline_status["archive_maintenance_available"] is True
    assert pipeline_status["archive_trigger_policy_available"] is True
    assert pipeline_status["archive_trigger_report_available"] is True
    assert pipeline_status["archive_auto_apply_enabled"] is False
