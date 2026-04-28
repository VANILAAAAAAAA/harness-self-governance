from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_BLOCKED_ACTIONS = [
    "git_commit",
    "git_push",
    "git_tag",
    "github_release",
    "pypi_publish",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_current_state(
    *,
    repo_name: str,
    branch: str,
    head: str,
    identity: dict,
    inputs: list[str],
    outputs: list[str],
    approval_gates: dict,
    validation: dict,
    pipeline: str = "local-rc",
    schema_version: str = "1.0",
) -> dict:
    status = "PASS" if all(value == "PASS" for value in validation.values()) and identity.get("status", "") in {"PASS", "PASS_WITH_WARNINGS"} else "FAIL"
    return {
        "generated_at": _utc_now(),
        "schema_version": schema_version,
        "pipeline": pipeline,
        "repo": {"name": repo_name, "branch": branch, "head": head},
        "identity": {
            "author": identity.get("author"),
            "committer": identity.get("committer"),
            "status": identity.get("status"),
        },
        "inputs": inputs,
        "outputs": outputs,
        "approval_gates": {
            "status": approval_gates.get("status", "PASS"),
            "blocked_actions": approval_gates.get("human_approval_required", DEFAULT_BLOCKED_ACTIONS),
        },
        "validation": validation,
        "status": status,
    }


def _rel(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def write_current_state(repo_root: Path, artifact_path: Path, state: dict) -> dict:
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    state["path"] = artifact_path.relative_to(repo_root).as_posix()
    return state


def build_local_test_event(repo_root: Path, note: str = "") -> dict[str, Any]:
    timestamp = _utc_now()
    return {
        "id": f"event:{timestamp}:local-provenance-append-test",
        "schema_version": "1.1",
        "type": "local_provenance_append_test",
        "profile": "local",
        "task": "v1.1 local provenance append test",
        "repo": {"root_name": repo_root.resolve().name},
        "timestamp": timestamp,
        "notes": note,
        "local_test": True,
        "mutation_scope": "artifacts_only",
        "provenance_upgrade": False,
        "apply_executed": False,
        "remote_publication_allowed": False,
        "destructive_operations_allowed": False,
    }


def append_local_test_event(
    repo_root: Path,
    events_path: str | Path | None = None,
    report_path: str | Path | None = None,
    note: str = "",
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    event_target = Path(events_path) if events_path else repo_root / "artifacts" / "v1.1" / "provenance" / "local-test-events.jsonl"
    report_target = Path(report_path) if report_path else repo_root / "artifacts" / "v1.1" / "provenance" / "local-append-report.json"
    if not event_target.is_absolute():
        event_target = repo_root / event_target
    if not report_target.is_absolute():
        report_target = repo_root / report_target
    event_target = event_target.resolve()
    report_target = report_target.resolve()
    artifacts_root = (repo_root / "artifacts").resolve()
    for path in (event_target, report_target):
        if not (path == artifacts_root or str(path).startswith(str(artifacts_root) + "/")):
            raise ValueError(f"local provenance append output must stay under repo artifacts/: {path}")

    event = build_local_test_event(repo_root, note)
    event_target.parent.mkdir(parents=True, exist_ok=True)
    with event_target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
    event_count = sum(1 for line in event_target.read_text(encoding="utf-8").splitlines() if line.strip())
    report = {
        "generated_at": _utc_now(),
        "status": "PASS",
        "path": _rel(repo_root, event_target),
        "report_path": _rel(repo_root, report_target),
        "event_id": event["id"],
        "event_count": event_count,
        "local_test": True,
        "mutation_scope": "artifacts_only",
        "provenance_upgrade": False,
        "apply_executed": False,
        "remote_publication_allowed": False,
        "destructive_operations_allowed": False,
    }
    report_target.parent.mkdir(parents=True, exist_ok=True)
    report_target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
