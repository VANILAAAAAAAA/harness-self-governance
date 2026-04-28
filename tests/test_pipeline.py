from __future__ import annotations

from pathlib import Path

from graph_harness_maintain.pipeline import run_local_rc, run_tests


ROOT = Path(__file__).parents[1]


REQUIRED_ARTIFACTS = [
    "artifacts/v1/identity-check.json",
    "artifacts/v1/git-state.json",
    "artifacts/v1/open-source-surface.json",
    "artifacts/v1/approval-gate-check.json",
    "artifacts/v1/adapter-audit.json",
    "artifacts/v1/evidence-index.json",
    "artifacts/v1/provenance/current-state.json",
    "artifacts/v1/test-results.json",
    "artifacts/v1/smoke-tests.json",
    "artifacts/v1/leak-scan.json",
    "artifacts/v1/v1-local-rc-report.md",
    "artifacts/v1/pipeline-run.json",
]


def test_local_rc_produces_all_required_artifact_files() -> None:
    result = run_local_rc(ROOT, strict=False, ci_mode=True)
    for rel in REQUIRED_ARTIFACTS:
        assert (ROOT / rel).exists(), rel
    assert result["artifacts"]


def test_run_tests_skips_recursive_pytest_when_guard_env_is_set(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("GHM_RECURSIVE_PYTEST", "1")
    artifact_path = tmp_path / "artifacts" / "v1" / "test-results.json"
    result = run_tests(tmp_path, artifact_path)
    assert result["status"] == "PASS"
    assert "recursive pytest skipped" in result["summary_line"]
    assert artifact_path.exists()


def test_strict_mode_returns_failure_on_blockers() -> None:
    result = run_local_rc(ROOT, strict=True, ci_mode=True, stage_overrides={"leak_scan": {"status": "FAIL", "blocking_count": 1}})
    assert result["exit_code"] == 5
    assert result["status"] == "FAIL"


def test_pipeline_ci_mode_passes_identity_semantics() -> None:
    result = run_local_rc(ROOT, strict=False, ci_mode=True)
    assert result["status"] in {"PASS", "PASS_WITH_WARNINGS"}
    assert "human_approval_required" in result
    assert not any("identity" in blocker.lower() for blocker in result["blockers"])


def test_pipeline_is_idempotent() -> None:
    first = run_local_rc(ROOT, strict=False, ci_mode=True)
    second = run_local_rc(ROOT, strict=False, ci_mode=True)
    assert first["artifacts"] == second["artifacts"]
    assert second["status"] in {"PASS", "PASS_WITH_WARNINGS"}
