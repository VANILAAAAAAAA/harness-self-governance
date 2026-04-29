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
