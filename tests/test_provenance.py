from __future__ import annotations

from graph_harness_maintain.provenance import build_current_state


def test_current_state_json_contains_repo_head_pipeline_and_status() -> None:
    state = build_current_state(
        repo_name="harness-self-governance",
        branch="main",
        head="abc123",
        identity={"author": "VANILAAAAAAAA <xchen247@uw.edu>", "committer": "VANILAAAAAAAA <xchen247@uw.edu>", "status": "PASS"},
        inputs=["README.md"],
        outputs=["artifacts/v1/evidence-index.json", "artifacts/v1/v1-local-rc-report.md"],
        approval_gates={"status": "PASS", "blocked_actions": ["git_commit"]},
        validation={"tests": "PASS", "package_import": "PASS", "cli_smoke": "PASS", "leak_scan": "PASS"},
    )
    assert state["pipeline"] == "local-rc"
    assert state["repo"]["head"] == "abc123"
    assert state["status"] == "PASS"


def test_output_references_evidence_and_report_artifacts() -> None:
    state = build_current_state(
        repo_name="harness-self-governance",
        branch="main",
        head="abc123",
        identity={"author": "a", "committer": "b", "status": "PASS"},
        inputs=["README.md"],
        outputs=["artifacts/v1/evidence-index.json", "artifacts/v1/v1-local-rc-report.md"],
        approval_gates={"status": "PASS", "blocked_actions": ["git_commit"]},
        validation={"tests": "PASS", "package_import": "PASS", "cli_smoke": "PASS", "leak_scan": "PASS"},
    )
    assert "artifacts/v1/evidence-index.json" in state["outputs"]
    assert "artifacts/v1/v1-local-rc-report.md" in state["outputs"]


def test_approval_gated_actions_are_listed() -> None:
    state = build_current_state(
        repo_name="harness-self-governance",
        branch="main",
        head="abc123",
        identity={"author": "a", "committer": "b", "status": "PASS"},
        inputs=["README.md"],
        outputs=["artifacts/v1/evidence-index.json", "artifacts/v1/v1-local-rc-report.md"],
        approval_gates={"status": "PASS", "blocked_actions": ["git_commit", "git_push", "pypi_publish"]},
        validation={"tests": "PASS", "package_import": "PASS", "cli_smoke": "PASS", "leak_scan": "PASS"},
    )
    assert "git_push" in state["approval_gates"]["blocked_actions"]
    assert "pypi_publish" in state["approval_gates"]["blocked_actions"]
