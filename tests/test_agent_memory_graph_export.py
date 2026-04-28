from __future__ import annotations

import json
from pathlib import Path

from agent_memory_graph.archive import archive_session
from agent_memory_graph.bootstrap import bootstrap_repo
from agent_memory_graph.export import export_repo_projection
from agent_memory_graph.repo_adapter import init_repo_manifest


SAMPLE = {
    "schema_version": "2.0",
    "profile_id": "general",
    "project_id": "harness-self-governance",
    "session_id": "session:v2-dashboard-planning",
    "privacy": "local_only",
    "summary": "v2 focuses on Graph and Logs as the core pages.",
    "decisions": [
        {
            "id": "decision:v2-core-graph-logs",
            "text": "v2.0 uses Graph and Logs as core pages.",
            "status": "accepted",
            "source": "session:v2-dashboard-planning",
        }
    ],
    "requirements": [
        {
            "id": "requirement:graph-main-focus",
            "text": "The Graph page should make the graph the primary focus.",
            "source": "session:v2-dashboard-planning",
        }
    ],
    "constraints": [
        {
            "id": "constraint:raw-sessions-last",
            "text": "Raw sessions are source material and last-resort context.",
            "source": "session:v2-dashboard-planning",
        }
    ],
    "graph_links": [
        {
            "source": "decision:v2-core-graph-logs",
            "target": "requirement:graph-main-focus",
            "type": "supports",
        }
    ],
}


def test_export_writes_repo_artifacts_to_expected_paths(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo_manifest(repo, "general", "harness-self-governance")
    memory_root = tmp_path / "memory"
    bootstrap_repo(repo, memory_root)
    input_path = tmp_path / "compiled-session.json"
    input_path.write_text(json.dumps(SAMPLE, indent=2) + "\n", encoding="utf-8")
    archive_session(memory_root, "general", "harness-self-governance", input_path)

    report = export_repo_projection(repo, memory_root)

    assert report["status"] == "PASS"
    graph = json.loads((repo / "artifacts" / "v2" / "graph" / "governance-graph.json").read_text(encoding="utf-8"))
    lineage = json.loads((repo / "artifacts" / "v2" / "lineage" / "log-index.json").read_text(encoding="utf-8"))
    project_summary = json.loads((repo / "artifacts" / "v2" / "projects" / "general" / "harness-self-governance" / "project-summary.json").read_text(encoding="utf-8"))
    assert graph["summary"]["global_agent_memory_graph_supported"] is True
    assert graph["summary"]["raw_sessions_default_read"] is False
    assert project_summary["privacy"] == "local_only"
    assert lineage["nodes"]["project_summary:general:harness-self-governance"]["preferred_path"] == "artifacts/v2/projects/general/harness-self-governance/project-summary.json"
