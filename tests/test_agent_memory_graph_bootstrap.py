from __future__ import annotations

import json
from pathlib import Path

from agent_memory_graph.bootstrap import bootstrap_repo, validate_repo
from agent_memory_graph.repo_adapter import init_repo_manifest


def test_bootstrap_returns_graph_first_read_order(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo_manifest(repo, "general", "harness-self-governance")
    memory_root = tmp_path / "memory"

    report = bootstrap_repo(repo, memory_root)

    assert report["status"] == "PASS"
    assert report["recommended_read_order"][0] == "global_graph"
    assert report["recommended_read_order"][-1] == "raw_sessions"
    assert report["raw_sessions_policy"] == "last_resort"
    saved = json.loads((memory_root / "reports" / "context-bootstrap-report.json").read_text(encoding="utf-8"))
    assert saved["recommended_read_order"] == report["recommended_read_order"]


def test_validate_passes_on_initialized_temp_memory_root(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo_manifest(repo, "general", "harness-self-governance")
    memory_root = tmp_path / "memory"
    bootstrap_repo(repo, memory_root)

    report = validate_repo(repo, memory_root)

    assert report["status"] == "PASS"
    assert report["raw_sessions_default_read"] is False
    assert report["blockers"] == []
