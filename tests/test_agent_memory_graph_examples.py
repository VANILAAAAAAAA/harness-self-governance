from __future__ import annotations

import json
from pathlib import Path

from agent_memory_graph.archive import archive_session
from agent_memory_graph.bootstrap import bootstrap_repo, validate_repo
from agent_memory_graph.export import export_repo_projection
from agent_memory_graph.repo_adapter import init_repo_manifest
from agent_memory_graph.schemas import SCHEMA_VERSION, validate_compiled_session

ROOT = Path(__file__).parents[1]
EXAMPLES = ROOT / "docs" / "examples" / "agent-memory-graph" / "harness-self-governance"
BANNED_SNIPPETS = (
    "/" + "home" + "/" + "vanila",
    "c:" + "\\\\",
    "d:" + "\\\\",
    "github" + "_token",
    "gh" + "_token",
    "openai" + "_api_key",
)


def _compiled_examples() -> list[Path]:
    return sorted(EXAMPLES.glob("compiled-session-*.json"))


def test_compiled_session_examples_are_valid_and_curated() -> None:
    examples = _compiled_examples()
    assert len(examples) == 9
    for path in examples:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["schema_version"] == SCHEMA_VERSION
        assert payload["profile_id"] == "general"
        assert payload["project_id"] == "harness-self-governance"
        assert payload["privacy"] == "local_only"
        assert payload["summary"].strip()
        assert payload["decisions"]
        assert payload["requirements"]
        assert payload["constraints"]
        assert payload["graph_links"]
        assert validate_compiled_session(payload) == []
        text = json.dumps(payload, ensure_ascii=False).lower()
        assert "raw transcript" not in text
        for banned in BANNED_SNIPPETS:
            assert banned not in text, (path.name, banned)


def test_archive_session_examples_bootstrap_meaningful_memory_graph(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo_manifest(repo, "general", "harness-self-governance")
    memory_root = tmp_path / "memory"
    bootstrap_repo(repo, memory_root)

    for path in _compiled_examples():
        report = archive_session(memory_root, "general", "harness-self-governance", path)
        assert report["status"] == "PASS", (path.name, report)

    validate = validate_repo(repo, memory_root)
    assert validate["status"] == "PASS"
    export = export_repo_projection(repo, memory_root)
    assert export["status"] == "PASS"

    graph = json.loads((repo / "artifacts" / "v2" / "graph" / "agent-memory-graph.json").read_text(encoding="utf-8"))
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    assert len(nodes) >= 30
    assert len(edges) >= 25

    text = json.dumps(graph, ensure_ascii=False).lower()
    for needle in [
        "dual graph",
        "graph and logs",
        "frontend visual qa",
        "profile",
        "project",
        "lineage",
        "agent memory graph",
        "raw sessions",
        "context router",
    ]:
        assert needle in text, needle
    assert graph["raw_sessions_default_read"] is False

    sessions = json.loads((repo / "artifacts" / "v2" / "projects" / "general" / "harness-self-governance" / "session-index.json").read_text(encoding="utf-8"))
    assert len(sessions["sessions"]) == len(_compiled_examples())


def test_examples_do_not_require_committed_raw_sessions_and_generated_artifacts_stay_ignored() -> None:
    for path in _compiled_examples():
        text = path.read_text(encoding="utf-8").lower()
        assert "sessions/raw/" not in text
        assert "state.db" not in text

    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "artifacts/v2/" in gitignore
    assert "sessions/raw/" in gitignore
