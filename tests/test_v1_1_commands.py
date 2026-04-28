from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
PY = sys.executable


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([PY, "-m", "graph_harness_maintain", *args], cwd=ROOT, text=True, capture_output=True, env=ENV)


def _json(stdout: str) -> dict:
    return json.loads(stdout)


def test_proposal_create_and_validate_commands() -> None:
    manifest = ROOT / "artifacts" / "v1.1" / "test-proposal-manifest.json"
    report = ROOT / "artifacts" / "v1.1" / "test-proposal-validation.json"

    created = _run("proposal", "create", "--title", "v1.1 test proposal", "--out", str(manifest))
    assert created.returncode == 0, created.stderr
    created_data = _json(created.stdout)
    assert created_data["status"] == "PASS"
    assert created_data["path"] == "artifacts/v1.1/test-proposal-manifest.json"

    manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
    assert manifest_data["schema_version"] == "1.1"
    assert manifest_data["version"] == "1.1"
    assert manifest_data["scope"] == "v1.1 reviewed-action-layer local baseline"
    assert manifest_data["operation_type"] == "reviewed_apply_plan"
    assert manifest_data["evidence"]
    assert manifest_data["required_approvals"] == ["human_review"]
    assert manifest_data["destructive"] is False
    assert manifest_data["apply_allowed"] is False
    assert manifest_data["apply_plan"]["review_gated"] is True
    assert manifest_data["apply_plan"]["human_approval_required"] is True
    assert "git_push" in manifest_data["blocked_actions"]
    assert "graph_mutation" in manifest_data["blocked_actions"]
    assert manifest_data["actions"] == []

    validated = _run("proposal", "validate", "--manifest", str(manifest), "--report", str(report))
    assert validated.returncode == 0, validated.stderr
    validation_data = _json(validated.stdout)
    assert validation_data["status"] == "PASS"
    assert validation_data["manifest_path"] == "artifacts/v1.1/test-proposal-manifest.json"
    assert report.exists()


def test_proposal_validation_blocks_destructive_actions() -> None:
    from graph_harness_maintain.proposals import build_default_manifest, validate_manifest

    manifest = build_default_manifest(ROOT, "bad proposal")
    manifest["actions"].append({"id": "bad-delete", "type": "delete", "target": "README.md", "destructive": True})
    result = validate_manifest(manifest)
    assert result["status"] == "FAIL"
    assert any("destructive" in item or "blocked action" in item for item in result["blockers"])


def test_proposal_validation_requires_audit_evidence_and_blocks_apply() -> None:
    from graph_harness_maintain.proposals import build_default_manifest, validate_manifest

    manifest = build_default_manifest(ROOT, "bad apply proposal")
    manifest["evidence"] = []
    manifest["apply_allowed"] = True
    result = validate_manifest(manifest)
    assert result["status"] == "FAIL"
    assert any("evidence" in item for item in result["blockers"])
    assert any("apply_allowed" in item for item in result["blockers"])


def test_templates_validate_command() -> None:
    result = _run("templates", "validate")
    assert result.returncode == 0, result.stderr
    data = _json(result.stdout)
    assert data["status"] == "PASS"
    assert data["template_count"] >= 4
    assert data["path"] == "artifacts/v1.1/template-validation.json"


def test_adapter_report_command() -> None:
    result = _run("adapter-report")
    assert result.returncode == 0, result.stderr
    data = _json(result.stdout)
    assert data["status"] == "PASS"
    assert data["path"] == "artifacts/v1.1/adapter-report.json"
    names = {item["name"] for item in data["adapters"]}
    assert {"GitRepoAdapter", "FileTreeAdapter", "ArtifactStoreAdapter"}.issubset(names)
    assert all(item["mutation_behavior"] == "approval_required" for item in data["adapters"])
    assert all(item["apply_executed"] is False for item in data["adapters"])
    assert data["read_only_behavior"] is True
    assert data["no_execution_side_effects"] is True
    assert data["safety_boundary"]["proposal_only"] is True
    assert data["safety_boundary"]["graph_mutation_allowed"] is False
    assert all(item["capabilities"] for item in data["adapters"])
    assert all(item["limitations"] for item in data["adapters"])
    assert all(item["inputs"] for item in data["adapters"])
    assert all(item["outputs"] for item in data["adapters"])
    assert all(item["safety_boundary"]["read_only_behavior"] is True for item in data["adapters"])


def test_provenance_append_local_test_command() -> None:
    result = _run("provenance", "append", "--local-test", "--note", "pytest local append")
    assert result.returncode == 0, result.stderr
    data = _json(result.stdout)
    assert data["status"] == "PASS"
    assert data["local_test"] is True
    assert data["provenance_upgrade"] is False
    event_path = ROOT / data["path"]
    assert event_path.exists()
    last_event = json.loads(event_path.read_text(encoding="utf-8").splitlines()[-1])
    assert last_event["local_test"] is True
    assert last_event["mutation_scope"] == "artifacts_only"


def test_pipeline_v1_1_rc_command() -> None:
    result = _run("pipeline", "v1.1-rc")
    assert result.returncode == 0, result.stderr
    data = _json(result.stdout)
    assert data["status"] in {"PASS", "PASS_WITH_WARNINGS"}
    assert data["remote_publication_allowed"] is False
    assert data["destructive_operations_allowed"] is False
    assert data["reviewed_apply_gated"] is True
    assert "artifacts/v1.1/v1.1-rc-report.md" in data["artifacts"]
    assert "git_push" in data["human_approval_required"]
    assert "graph_mutation" in data["human_approval_required"]


def test_pipeline_v1_1_rc_strict_command() -> None:
    result = _run("pipeline", "v1.1-rc", "--strict")
    assert result.returncode == 0, result.stderr
    data = _json(result.stdout)
    assert data["strict"] is True
    assert data["status"] in {"PASS", "PASS_WITH_WARNINGS"}
