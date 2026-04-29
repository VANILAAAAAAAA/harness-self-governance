from __future__ import annotations

import json
from pathlib import Path

from graph_harness_maintain.projects import (
    DEFAULT_PROJECT_ID,
    DEFAULT_PROFILE_ID,
    build_default_project_summary,
    init_project,
    validate_agent_archive_contract,
    validate_project,
)


def test_project_manifest_is_created_for_default_project(tmp_path: Path) -> None:
    report = init_project(tmp_path, DEFAULT_PROFILE_ID, DEFAULT_PROJECT_ID)
    manifest_path = tmp_path / report["manifest_path"]
    data = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert report["status"] == "PASS"
    assert data["schema_version"] == "2.0"
    assert data["profile_id"] == "general"
    assert data["project_id"] == "harness-self-governance"
    assert data["title"] == "Harness Self Governance"
    assert data["status"] == "active"
    assert data["role"] == "governance_project"
    assert data["summary_path"] == "artifacts/v2/projects/general/harness-self-governance/project-summary.json"


def test_project_validate_accepts_deterministic_manifest(tmp_path: Path) -> None:
    init_project(tmp_path, "general", "harness-self-governance")
    report = validate_project(tmp_path, "general", "harness-self-governance")

    assert report["status"] == "PASS"
    assert report["profile_id"] == "general"
    assert report["project_id"] == "harness-self-governance"
    assert report["llm_api_required"] is False
    assert report["blockers"] == []


def test_agent_triggered_archive_schema_validates_without_llm_api(tmp_path: Path) -> None:
    init_project(tmp_path, "general", "harness-self-governance")
    summary = build_default_project_summary("general", "harness-self-governance")
    report = validate_agent_archive_contract(summary)

    assert report["status"] == "PASS"
    assert report["llm_hub_api_enabled"] is False
    assert report["agent_triggered_archive"] is True
    assert summary["privacy"] == "local_only"
    assert summary["decisions"]
    assert summary["requirements"]
    assert summary["constraints"]
