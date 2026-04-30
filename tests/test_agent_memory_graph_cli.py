from __future__ import annotations

from pathlib import Path

from agent_memory_graph import cli
from agent_memory_graph.schemas import DEFAULT_MEMORY_ROOT


def test_archive_session_cli_resolves_default_memory_root(monkeypatch, tmp_path: Path) -> None:
    input_path = tmp_path / "compiled-session.json"
    input_path.write_text("{}\n", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_archive(memory_root, profile_id, project_id, input_arg):
        captured["memory_root"] = memory_root
        captured["profile_id"] = profile_id
        captured["project_id"] = project_id
        captured["input"] = input_arg
        return {"status": "PASS"}

    monkeypatch.setattr(cli, "archive_session", fake_archive)
    assert cli.main([
        "archive-session",
        "--profile",
        "general",
        "--project",
        "harness-self-governance",
        "--input",
        str(input_path),
    ]) == 0
    assert Path(captured["memory_root"]) == DEFAULT_MEMORY_ROOT


def test_export_cli_resolves_default_memory_root(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    captured: dict[str, object] = {}

    def fake_export(repo_root, memory_root):
        captured["repo_root"] = repo_root
        captured["memory_root"] = memory_root
        return {"status": "PASS"}

    monkeypatch.setattr(cli, "export_repo_projection", fake_export)
    assert cli.main(["export", "--repo", str(repo)]) == 0
    assert Path(captured["repo_root"]) == repo
    assert Path(captured["memory_root"]) == DEFAULT_MEMORY_ROOT


def test_retrieve_cli_calls_agent_readable_retriever(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    captured: dict[str, object] = {}

    def fake_retrieve(
        repo_root,
        query,
        profile_hint=None,
        project_hint=None,
        memory_root=None,
        budget="fast",
        evidence_depth="anchor",
        refresh_index=False,
        refresh_graph=False,
    ):
        captured.update({
            "repo_root": repo_root,
            "query": query,
            "profile_hint": profile_hint,
            "project_hint": project_hint,
            "memory_root": memory_root,
            "budget": budget,
            "evidence_depth": evidence_depth,
            "refresh_index": refresh_index,
            "refresh_graph": refresh_graph,
        })
        return {"status": "PASS", "summary_first": {}, "plan": {}}

    monkeypatch.setattr(cli, "retrieve_project_context", fake_retrieve)
    assert cli.main([
        "retrieve",
        "--repo", str(repo),
        "--query", "continue project",
        "--profile", "general",
        "--project", "harness-self-governance",
        "--budget", "normal",
    ]) == 0
    assert Path(captured["repo_root"]) == repo
    assert captured["query"] == "continue project"
    assert captured["profile_hint"] == "general"
    assert captured["project_hint"] == "harness-self-governance"
    assert captured["budget"] == "normal"
    assert captured["evidence_depth"] == "anchor"
    assert captured["refresh_index"] is False
    assert captured["refresh_graph"] is False


def test_archive_gate_compile_pending_cli(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    memory = tmp_path / "memory"
    captured: dict[str, object] = {}

    def fake_compile(repo_root, memory_root=None, profile=None, project=None):
        captured.update({"repo_root": repo_root, "memory_root": memory_root, "profile": profile, "project": project})
        return {"status": "PASS", "compiled_count": 1}

    monkeypatch.setattr(cli, "compile_pending_updates", fake_compile)
    assert cli.main([
        "archive-gate", "compile-pending",
        "--repo", str(repo),
        "--memory-root", str(memory),
        "--profile", "general",
        "--project", "harness-self-governance",
    ]) == 0
    assert Path(captured["repo_root"]) == repo
    assert captured["memory_root"] == str(memory)
    assert captured["profile"] == "general"
    assert captured["project"] == "harness-self-governance"


def test_runtime_traces_export_cli(monkeypatch, tmp_path: Path) -> None:
    trace_dir = tmp_path / "traces"
    out = tmp_path / "runtime" / "graph-memory-traces.json"
    captured: dict[str, object] = {}

    def fake_export(trace_dir_arg, out_arg, limit=50):
        captured.update({"trace_dir": trace_dir_arg, "out": out_arg, "limit": limit})
        return {"status": "PASS", "event_count": 2}

    monkeypatch.setattr(cli, "export_graph_memory_traces", fake_export)
    assert cli.main([
        "runtime-traces", "export",
        "--trace-dir", str(trace_dir),
        "--out", str(out),
        "--limit", "7",
    ]) == 0
    assert captured == {"trace_dir": str(trace_dir), "out": str(out), "limit": 7}
