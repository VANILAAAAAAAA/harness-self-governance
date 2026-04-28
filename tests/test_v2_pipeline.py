from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from graph_harness_maintain.pipeline import run_v2_0_rc

ROOT = Path(__file__).parents[1]
PY = sys.executable


def _env() -> dict[str, str]:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    env.setdefault("GIT_AUTHOR_NAME", "VANILAAAAAAAA")
    env.setdefault("GIT_AUTHOR_EMAIL", "xchen247@uw.edu")
    env.setdefault("GIT_COMMITTER_NAME", "VANILAAAAAAAA")
    env.setdefault("GIT_COMMITTER_EMAIL", "xchen247@uw.edu")
    env.setdefault("GHM_RECURSIVE_PYTEST", "1")
    return env


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([PY, "-m", "graph_harness_maintain", *args], cwd=ROOT, text=True, capture_output=True, env=_env())


def test_v2_pipeline_reports_read_only_safety_boundary() -> None:
    data = run_v2_0_rc(ROOT)

    assert data["status"] in {"PASS", "PASS_WITH_WARNINGS"}
    assert data["release_ready_local"] is True
    assert data["read_only_ui"] is True
    assert data["proposal_only"] is True
    assert data["destructive_operations_allowed"] is False
    assert data["graph_mutation_allowed"] is False
    assert data["remote_publication_allowed"] is False
    assert data["sensitive_export_allowed"] is False
    assert data["session_raw_committed"] is False
    assert "artifacts/v2/graph/governance-graph.json" in data["artifacts"]
    assert "artifacts/v2/dashboard/index.html" in data["artifacts"]
    assert "artifacts/v2/sessions/session-index.json" in data["artifacts"]
    assert "artifacts/v2/profiles/profile-index.json" in data["artifacts"]
    assert "artifacts/v2/projects/general/harness-self-governance/project-manifest.json" in data["artifacts"]
    assert "artifacts/v2/lineage/log-index.json" in data["artifacts"]
    assert data["profile_support"] is True
    assert data["active_profile"] == "general"
    assert data["project_support"] is True
    assert data["default_project"] == "harness-self-governance"
    assert data["lineage_index_available"] is True
    assert data["view_in_logs_requires_mapping"] is True
    assert data["llm_hub_api_enabled"] is False
    assert data["agent_triggered_archive"] is True
    assert data["global_agent_memory_graph_supported"] is True
    assert data["repo_context_manifest_available"] is True
    assert data["graph_governed_context_protocol"] is True
    assert data["raw_sessions_default_read"] is False
    assert data["agent_graph_cli_available"] is True


def test_v2_pipeline_cli_command_writes_pipeline_run() -> None:
    result = _run("pipeline", "v2.0-rc")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["read_only_ui"] is True
    path = ROOT / "artifacts" / "v2" / "pipeline-run.json"
    assert path.exists()
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted["graph_mutation_allowed"] is False


def test_v2_cli_help_commands_work() -> None:
    commands = [
        ("--help",),
        ("graph", "--help"),
        ("graph", "export", "--help"),
        ("dashboard", "--help"),
        ("dashboard", "build", "--help"),
        ("sessions", "--help"),
        ("sessions", "compress", "--help"),
        ("profile", "--help"),
        ("profile", "index", "--help"),
        ("profile", "validate", "--help"),
        ("project", "--help"),
        ("project", "init", "--help"),
        ("project", "validate", "--help"),
        ("lineage", "--help"),
        ("lineage", "build", "--help"),
        ("lineage", "validate", "--help"),
        ("pipeline", "v2.0-rc", "--help"),
    ]
    for args in commands:
        result = _run(*args)
        assert result.returncode == 0, (args, result.stderr)
        assert "usage:" in result.stdout


def test_agent_memory_graph_module_help_commands_work() -> None:
    commands = [
        ("--help",),
        ("init-repo", "--help"),
        ("bootstrap", "--help"),
        ("validate", "--help"),
        ("archive-session", "--help"),
        ("export", "--help"),
    ]
    for args in commands:
        result = subprocess.run([PY, "-m", "agent_memory_graph", *args], cwd=ROOT, text=True, capture_output=True, env=_env())
        assert result.returncode == 0, (args, result.stderr)
        assert "usage:" in result.stdout
