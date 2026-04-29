from __future__ import annotations

import json
from pathlib import Path

from agent_memory_graph.repo_adapter import init_repo_manifest, read_repo_manifest


def test_init_repo_creates_context_manifest_in_temp_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    report = init_repo_manifest(repo, "general", "harness-self-governance")

    assert report["status"] == "PASS"
    manifest_path = repo / ".agent" / "context.json"
    assert manifest_path.exists()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["schema_version"] == "2.0"
    assert data["memory_graph"]["source"] == "global"
    assert data["memory_graph"]["export_to"]["graph"] == "artifacts/v2/graph/agent-memory-graph.json"
    assert read_repo_manifest(repo)["project"] == "harness-self-governance"
