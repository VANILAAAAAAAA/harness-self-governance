from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


REQUIRED_CLAIMS = [
    ("EV-001", "Git identity is user-owned", "identity", "identity"),
    ("EV-002", "worktree status is known", "git_state", "git"),
    ("EV-003", "README exists", "release_audit", "docs"),
    ("EV-004", "README has v1.0 scope", "release_audit", "docs"),
    ("EV-005", "README has usage instructions", "release_audit", "docs"),
    ("EV-006", "README has architecture section", "release_audit", "docs"),
    ("EV-007", "LICENSE exists", "release_audit", "package"),
    ("EV-008", "pyproject exists", "release_audit", "package"),
    ("EV-009", "package imports", "smoke", "package"),
    ("EV-010", "CLI entrypoint exists", "release_audit", "package"),
    ("EV-011", "approval gates policy exists", "gates", "policy"),
    ("EV-012", "templates exist", "release_audit", "templates"),
    ("EV-013", "tests exist", "release_audit", "tests"),
    ("EV-014", "tests pass", "tests", "tests"),
    ("EV-015", "leak scan passes", "leak_scan", "security"),
    ("EV-016", "sensitive public docs review passes", "leak_scan", "security"),
    ("EV-017", "provenance state generated", "provenance", "provenance"),
    ("EV-018", "pipeline report generated", "report", "report"),
    ("EV-019", "human approval gates are enforced", "gates", "policy"),
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _status_from_stage(stage_name: str, stage_results: dict) -> tuple[str, list[dict], str | None]:
    stage = stage_results.get(stage_name, {})
    status = stage.get("status", "FAIL")
    path = stage.get("path")
    evidence = [{"path": path, "detail": f"{stage_name} status {status}", "line": None}] if path else []
    remediation = None if status.startswith("PASS") else f"Review stage: {stage_name}"
    return ("PASS" if status.startswith("PASS") else "FAIL", evidence, remediation)


def build_evidence_index(stage_results: dict) -> dict:
    claims = []
    for claim_id, claim_text, stage_name, category in REQUIRED_CLAIMS:
        status, evidence, remediation = _status_from_stage(stage_name, stage_results)
        claims.append(
            {
                "id": claim_id,
                "claim": claim_text,
                "status": status,
                "severity": "required",
                "category": category,
                "evidence": evidence,
                "checked_by": "graph_harness_maintain.evidence",
                "remediation": remediation,
            }
        )
    overall = "PASS" if all(item["status"] == "PASS" for item in claims) else "FAIL"
    return {"generated_at": _utc_now(), "status": overall, "claims": claims}


def write_evidence_index(repo_root: Path, artifact_path: Path, stage_results: dict) -> dict:
    report = build_evidence_index(stage_results)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report["path"] = artifact_path.relative_to(repo_root).as_posix()
    return report
