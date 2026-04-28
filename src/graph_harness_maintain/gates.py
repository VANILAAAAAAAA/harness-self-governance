from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


CONFIG_FAIL_EXIT_CODE = 4
GATE_BLOCK_EXIT_CODE = 2

DEFAULT_POLICY_TEXT = """version: 1
policy_name: v1-approval-gates

allowed_without_human_approval:
  - read_only_audit
  - local_tests
  - local_leak_scan
  - local_report_generation
  - local_evidence_index_generation
  - local_provenance_state_generation
  - package_import_smoke_test
  - cli_smoke_test
  - local_docs_edit
  - local_policy_edit
  - local_template_edit
  - local_proposal_generation
  - local_proposal_validation
  - local_template_validation
  - local_adapter_report_generation
  - local_provenance_append_test
  - reviewed_apply_plan_generation

always_require_human_approval:
  - git_commit
  - git_push
  - git_tag
  - github_release
  - pypi_publish
  - raw_archive_apply
  - delete
  - move
  - graph_mutation
  - graph_events_mutation
  - quarantine
  - rehydrate
  - provenance_upgrade
  - sensitive_export
  - reviewed_apply
  - apply_plan_execute
  - force_push

blocked_in_v1:
  - destructive_file_operation
  - remote_publication_without_approval
  - credential_export
  - private_path_export
  - unreviewed_identity_change
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_policy_file(policy_path: Path) -> None:
    if not policy_path.exists():
        policy_path.parent.mkdir(parents=True, exist_ok=True)
        policy_path.write_text(DEFAULT_POLICY_TEXT, encoding="utf-8")


def _parse_simple_yaml(text: str) -> dict:
    data: dict[str, object] = {}
    current_key: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" ") and ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value:
                if value.isdigit():
                    data[key] = int(value)
                else:
                    data[key] = value
                current_key = None
            else:
                data[key] = []
                current_key = key
            continue
        if line.startswith("  - ") and current_key:
            assert isinstance(data[current_key], list)
            data[current_key].append(line[4:].strip())
    return data


def load_policy(policy_path: Path) -> dict:
    if not policy_path.exists():
        return {
            "generated_at": _utc_now(),
            "status": "FAIL",
            "message": f"Policy file missing: {policy_path}",
            "exit_code": CONFIG_FAIL_EXIT_CODE,
        }
    parsed = _parse_simple_yaml(policy_path.read_text(encoding="utf-8"))
    parsed["generated_at"] = _utc_now()
    parsed["status"] = "PASS"
    parsed["path"] = policy_path.as_posix()
    parsed["exit_code"] = 0
    return parsed


def check_action_allowed(policy: dict, action: str) -> dict:
    if policy.get("status") == "FAIL":
        return policy
    allowed = set(policy.get("allowed_without_human_approval", []))
    gated = set(policy.get("always_require_human_approval", []))
    blocked = set(policy.get("blocked_in_v1", []))
    if action in allowed:
        return {"action": action, "allowed": True, "status": "PASS", "reason": "allowed_without_human_approval", "exit_code": 0}
    if action in gated or action in blocked:
        return {"action": action, "allowed": False, "status": "BLOCKED", "reason": "human_approval_required", "exit_code": GATE_BLOCK_EXIT_CODE}
    return {"action": action, "allowed": False, "status": "FAIL", "reason": "unknown_action", "exit_code": CONFIG_FAIL_EXIT_CODE}


def write_gate_check(repo_root: Path, artifact_path: Path, policy_path: Path) -> dict:
    ensure_policy_file(policy_path)
    policy = load_policy(policy_path)
    if policy.get("status") == "FAIL":
        report = policy
    else:
        human_actions = list(policy.get("always_require_human_approval", []))
        blocked_actions = list(policy.get("blocked_in_v1", []))
        report = {
            "generated_at": _utc_now(),
            "status": "PASS",
            "policy_name": policy.get("policy_name"),
            "version": policy.get("version"),
            "allowed_without_human_approval": policy.get("allowed_without_human_approval", []),
            "always_require_human_approval": human_actions,
            "blocked_in_v1": blocked_actions,
            "human_approval_required": human_actions,
            "exit_code": 0,
        }
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report["path"] = artifact_path.relative_to(repo_root).as_posix()
    return report
