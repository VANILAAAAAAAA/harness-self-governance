from __future__ import annotations

import json
import socket
from pathlib import Path

from agent_memory_graph.archive import archive_session
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


def test_archive_session_accepts_compiled_json_and_preserves_local_only(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo_manifest(repo, "general", "harness-self-governance")
    memory_root = tmp_path / "memory"
    input_path = tmp_path / "compiled-session.json"
    input_path.write_text(json.dumps(SAMPLE, indent=2) + "\n", encoding="utf-8")

    def fail_connect(*args, **kwargs):  # pragma: no cover - should never run
        raise AssertionError("archive-session attempted a network call")

    monkeypatch.setattr(socket, "create_connection", fail_connect)
    report = archive_session(memory_root, "general", "harness-self-governance", input_path)

    assert report["status"] == "PASS"
    assert report["privacy"] == "local_only"
    project_root = memory_root / "projects" / "general" / "harness-self-governance"
    summary = json.loads((project_root / "project-summary.json").read_text(encoding="utf-8"))
    sessions = json.loads((project_root / "session-index.json").read_text(encoding="utf-8"))
    fragment = json.loads((project_root / "graph-fragment.json").read_text(encoding="utf-8"))
    assert summary["privacy"] == "local_only"
    assert summary["decisions"][0]["id"] == "decision:v2-core-graph-logs"
    assert sessions["sessions"][0]["session_id"] == "session:v2-dashboard-planning"
    assert any(edge["type"] == "supports" for edge in fragment["edges"])
