from __future__ import annotations

import json
from pathlib import Path

from agent_memory_graph.archive import archive_session
from agent_memory_graph.context_index import build_context_index
from agent_memory_graph.repo_adapter import init_repo_manifest


COMPILED_SESSION = {
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
            "text": "The Graph page should make the graph the primary focus and support View in Logs lineage mapping.",
            "source": "session:v2-dashboard-planning",
        }
    ],
    "constraints": [
        {
            "id": "constraint:raw-sessions-last",
            "text": "Raw sessions are source material and last-resort context.",
            "source": "session:v2-dashboard-planning",
        },
        {
            "id": "constraint:no-hub-llm-api",
            "text": "No Hub-side LLM API in this phase.",
            "source": "session:v2-dashboard-planning",
        },
    ],
    "graph_links": [
        {
            "source": "decision:v2-core-graph-logs",
            "target": "requirement:graph-main-focus",
            "type": "supports",
        }
    ],
}


def seed_memory(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo_manifest(repo, "general", "harness-self-governance")
    memory_root = tmp_path / "memory"
    compiled = tmp_path / "compiled-session.json"
    compiled.write_text(json.dumps(COMPILED_SESSION), encoding="utf-8")
    archive_session(memory_root, "general", "harness-self-governance", compiled)
    return repo, memory_root


def test_build_index_creates_deterministic_context_index_json(tmp_path: Path) -> None:
    repo, memory_root = seed_memory(tmp_path)

    report = build_context_index(repo, memory_root)
    first = (memory_root / "index" / "context-index.json").read_text(encoding="utf-8")
    second_report = build_context_index(repo, memory_root)
    second = (memory_root / "index" / "context-index.json").read_text(encoding="utf-8")

    assert report["status"] == "PASS"
    assert second_report["status"] == "PASS"
    assert first == second
    index = json.loads(first)
    assert index["schema_version"] == "2.0"
    assert index["routing_table_type"] == "graph_traversal_context_index"
    assert index["not_search_database"] is True
    assert index["profiles"]["general"]["entry_node"] == "profile:general"
    assert index["projects"]["general/harness-self-governance"]["entry_node"] == "project:general:harness-self-governance"
    assert "view-in-logs" in index["topics"]
    assert "log定位" in index["aliases"]
    assert index["aliases"]["log定位"] == "view-in-logs"
    assert index["budget_hints"]["forensic"]["raw_sessions_allowed"] is True
    assert index["budget_hints"]["fast"]["raw_sessions_allowed"] is False
    assert "agent_memory_graph" in index["graph_layers"]
