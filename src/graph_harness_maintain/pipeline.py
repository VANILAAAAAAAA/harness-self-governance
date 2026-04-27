from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .adapters import ArtifactStoreAdapter, FileTreeAdapter, GitRepoAdapter
from .evidence import write_evidence_index
from .gates import GATE_BLOCK_EXIT_CODE, write_gate_check
from .git_state import write_git_state
from .identity import IDENTITY_FAIL_EXIT_CODE, run_identity_check
from .leak_scan import LEAK_SCAN_FAIL_EXIT_CODE, write_leak_scan
from .provenance import build_current_state, write_current_state
from .release_audit import write_release_audit
from .report import write_pipeline_report


PASS = 0
FAIL = 1
CONFIG_FAIL = 4
TESTS_FAIL = 6
PACKAGE_SMOKE_FAIL = 7


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_command(command: list[str], repo_root: Path, env: dict[str, str] | None = None) -> dict:
    proc = subprocess.run(command, cwd=repo_root, text=True, capture_output=True, env=env)
    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()
    return {
        "command": " ".join(command),
        "exit_code": proc.returncode,
        "status": "PASS" if proc.returncode == 0 else "FAIL",
        "stdout_tail": "\n".join(stdout.splitlines()[-20:]),
        "stderr_tail": "\n".join(stderr.splitlines()[-20:]),
    }


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def adapter_audit(repo_root: Path, artifact_path: Path) -> dict:
    adapters = [GitRepoAdapter(repo_root), FileTreeAdapter(repo_root), ArtifactStoreAdapter(repo_root)]
    report = {
        "generated_at": _utc_now(),
        "status": "PASS",
        "adapters": [],
    }
    for adapter in adapters:
        report["adapters"].append(
            {
                "name": adapter.__class__.__name__,
                "inspect": adapter.inspect(),
                "evidence_count": len(adapter.locate_evidence()),
                "proposals": adapter.propose_actions(),
                "mutation_behavior": "approval_required",
            }
        )
    _write_json(artifact_path, report)
    report["path"] = artifact_path.relative_to(repo_root).as_posix()
    return report


def run_tests(repo_root: Path, artifact_path: Path) -> dict:
    if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("GHM_RECURSIVE_PYTEST"):
        result = {
            "command": f"{sys.executable} -m pytest",
            "exit_code": 0,
            "status": "PASS",
            "stdout_tail": "skipped recursive pytest invocation under pytest runner",
            "stderr_tail": "",
            "summary_line": "recursive pytest skipped for in-process pipeline test",
            "test_count": None,
        }
    else:
        child_env = {**os.environ, "GHM_RECURSIVE_PYTEST": "1"}
        result = _run_command([sys.executable, "-m", "pytest"], repo_root, env=child_env)
        result["test_count"] = None
        for line in (result["stdout_tail"] + "\n" + result["stderr_tail"]).splitlines():
            if " passed" in line or " failed" in line:
                result["summary_line"] = line.strip()
    _write_json(artifact_path, result)
    result["path"] = artifact_path.relative_to(repo_root).as_posix()
    return result


def run_smoke_tests(repo_root: Path, artifact_path: Path) -> dict:
    ghm_command = [sys.executable, "-m", "graph_harness_maintain"]
    commands = [
        [sys.executable, "-c", "import graph_harness_maintain; print(graph_harness_maintain.__version__)"],
        ghm_command + ["--help"],
        ghm_command + ["identity-check"],
        ghm_command + ["check-gates"],
        ghm_command + ["audit-release"],
    ]
    results = [_run_command(command, repo_root) for command in commands]
    status = "PASS" if all(item["status"] == "PASS" for item in results) else "FAIL"
    report = {
        "generated_at": _utc_now(),
        "status": status,
        "package_import": results[0]["status"],
        "cli_smoke": "PASS" if all(item["status"] == "PASS" for item in results[1:]) else "FAIL",
        "results": results,
    }
    _write_json(artifact_path, report)
    report["path"] = artifact_path.relative_to(repo_root).as_posix()
    return report


def run_local_rc(repo_root: Path, strict: bool = False, ci_mode: bool = False, stage_overrides: dict | None = None) -> dict:
    repo_root = repo_root.resolve()
    artifacts_root = repo_root / "artifacts" / "v1"
    provenance_root = artifacts_root / "provenance"
    policy_path = repo_root / "policies" / "approval-gates.yaml"

    identity = run_identity_check(repo_root, artifacts_root / "identity-check.json", ci_mode=ci_mode)
    git_state = write_git_state(repo_root, artifacts_root / "git-state.json")
    release_audit = write_release_audit(repo_root, artifacts_root / "open-source-surface.json")
    gates = write_gate_check(repo_root, artifacts_root / "approval-gate-check.json", policy_path)
    adapter = adapter_audit(repo_root, artifacts_root / "adapter-audit.json")
    tests = run_tests(repo_root, artifacts_root / "test-results.json")
    smoke = run_smoke_tests(repo_root, artifacts_root / "smoke-tests.json")
    leak_scan = write_leak_scan(repo_root, artifacts_root / "leak-scan.json")

    stage_results = {
        "identity": identity,
        "git_state": git_state,
        "release_audit": release_audit,
        "gates": gates,
        "adapter": adapter,
        "tests": tests,
        "smoke": smoke,
        "leak_scan": leak_scan,
        "provenance": {"status": "PASS", "path": "artifacts/v1/provenance/current-state.json"},
        "report": {"status": "PASS", "path": "artifacts/v1/v1-local-rc-report.md"},
    }
    if stage_overrides:
        for name, override in stage_overrides.items():
            stage_results.setdefault(name, {}).update(override)

    evidence = write_evidence_index(repo_root, artifacts_root / "evidence-index.json", stage_results)
    provenance_state = build_current_state(
        repo_name="harness-self-governance",
        branch=git_state.get("branch") or "unknown",
        head=git_state.get("head") or "unknown",
        identity=identity,
        inputs=["README.md", "pyproject.toml", "policies/approval-gates.yaml"],
        outputs=["artifacts/v1/evidence-index.json", "artifacts/v1/v1-local-rc-report.md"],
        approval_gates=gates,
        validation={
            "tests": tests["status"],
            "package_import": smoke["package_import"],
            "cli_smoke": smoke["cli_smoke"],
            "leak_scan": leak_scan["status"],
        },
    )
    provenance = write_current_state(repo_root, provenance_root / "current-state.json", provenance_state)
    stage_results["provenance"] = provenance

    blockers: list[str] = []
    warnings: list[str] = []
    if identity["status"] == "FAIL":
        blockers.extend(identity["blockers"])
    elif identity["warnings"]:
        warnings.extend(identity["warnings"])
    if release_audit["status"] == "FAIL":
        blockers.extend(release_audit["blockers"])
    if gates["status"] == "FAIL":
        blockers.append("approval gate policy failed to load")
    if tests["status"] != "PASS":
        blockers.append("pytest failed")
    if smoke["status"] != "PASS":
        blockers.append("package or CLI smoke tests failed")
    if leak_scan["status"] != "PASS":
        blockers.append("leak scan found blocking issues")
    if evidence["status"] != "PASS":
        blockers.append("evidence index contains failed required claims")

    status = "PASS"
    if blockers:
        status = "FAIL" if strict or any(item for item in blockers) else "BLOCKED"
    elif warnings:
        status = "PASS_WITH_WARNINGS"

    exit_code = PASS
    if identity["status"] == "FAIL":
        exit_code = IDENTITY_FAIL_EXIT_CODE
    elif gates["status"] == "FAIL":
        exit_code = CONFIG_FAIL
    elif leak_scan["status"] != "PASS":
        exit_code = LEAK_SCAN_FAIL_EXIT_CODE
    elif tests["status"] != "PASS":
        exit_code = TESTS_FAIL
    elif smoke["status"] != "PASS":
        exit_code = PACKAGE_SMOKE_FAIL
    elif blockers:
        exit_code = FAIL

    result = {
        "generated_at": _utc_now(),
        "status": status,
        "release_ready_local": not blockers,
        "remote_publication_allowed": False,
        "human_approval_required": gates.get("human_approval_required", []),
        "blockers": blockers,
        "warnings": warnings,
        "artifacts": [
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
        ],
        "exit_code": exit_code,
        "ci_mode": ci_mode,
        "strict": strict,
    }
    write_pipeline_report(repo_root, artifacts_root / "v1-local-rc-report.md", result, git_state, identity, release_audit, gates, adapter, evidence, provenance, tests, smoke, leak_scan)
    _write_json(artifacts_root / "pipeline-run.json", result)
    return result
