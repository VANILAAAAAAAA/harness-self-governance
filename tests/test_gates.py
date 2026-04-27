from __future__ import annotations

from pathlib import Path

from graph_harness_maintain.gates import GATE_BLOCK_EXIT_CODE, check_action_allowed, load_policy


POLICY_TEXT = """version: 1
policy_name: v1-approval-gates
allowed_without_human_approval:
  - read_only_audit
  - local_tests
always_require_human_approval:
  - git_commit
  - git_push
blocked_in_v1:
  - destructive_file_operation
"""


def test_allowed_action_passes(tmp_path: Path) -> None:
    policy_path = tmp_path / "approval-gates.yaml"
    policy_path.write_text(POLICY_TEXT, encoding="utf-8")
    policy = load_policy(policy_path)
    decision = check_action_allowed(policy, "read_only_audit")
    assert decision["status"] == "PASS"
    assert decision["allowed"] is True


def test_gated_action_blocks(tmp_path: Path) -> None:
    policy_path = tmp_path / "approval-gates.yaml"
    policy_path.write_text(POLICY_TEXT, encoding="utf-8")
    policy = load_policy(policy_path)
    decision = check_action_allowed(policy, "git_commit")
    assert decision["status"] == "BLOCKED"
    assert decision["allowed"] is False
    assert decision["exit_code"] == GATE_BLOCK_EXIT_CODE


def test_policy_file_loads(tmp_path: Path) -> None:
    policy_path = tmp_path / "approval-gates.yaml"
    policy_path.write_text(POLICY_TEXT, encoding="utf-8")
    policy = load_policy(policy_path)
    assert policy["policy_name"] == "v1-approval-gates"
    assert "git_push" in policy["always_require_human_approval"]


def test_missing_policy_fails_cleanly(tmp_path: Path) -> None:
    missing = tmp_path / "missing.yaml"
    decision = load_policy(missing)
    assert decision["status"] == "FAIL"
    assert decision["exit_code"] == 4
    assert "missing" in decision["message"].lower()
