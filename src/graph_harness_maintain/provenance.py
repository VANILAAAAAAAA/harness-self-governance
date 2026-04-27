from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


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
) -> dict:
    status = "PASS" if all(value == "PASS" for value in validation.values()) and identity.get("status", "") in {"PASS", "PASS_WITH_WARNINGS"} else "FAIL"
    return {
        "generated_at": _utc_now(),
        "schema_version": "1.0",
        "pipeline": "local-rc",
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


def write_current_state(repo_root: Path, artifact_path: Path, state: dict) -> dict:
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    state["path"] = artifact_path.relative_to(repo_root).as_posix()
    return state
