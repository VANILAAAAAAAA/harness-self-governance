from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .identity import EXPECTED_IDENTITY

SCHEMA_VERSION = "1.1"
MANIFEST_KIND = "reviewed_apply_proposal"

REMOTE_PUBLICATION_ACTIONS = {
    "git_push",
    "git_tag",
    "github_release",
    "pypi_publish",
    "force_push",
    "remote_publication_without_approval",
}
DESTRUCTIVE_ACTIONS = {
    "delete",
    "move",
    "destructive_file_operation",
    "raw_archive_apply",
    "quarantine",
    "rehydrate",
}
GATED_ACTIONS = {
    "git_commit",
    "reviewed_apply",
    "apply_plan_execute",
    "graph_mutation",
    "graph_events_mutation",
    "provenance_upgrade",
    "sensitive_export",
}
BLOCKED_ACTIONS = sorted(REMOTE_PUBLICATION_ACTIONS | DESTRUCTIVE_ACTIONS | GATED_ACTIONS)
ALLOWED_LOCAL_ACTIONS = {
    "read_only_audit",
    "local_tests",
    "local_leak_scan",
    "local_report_generation",
    "local_evidence_index_generation",
    "local_provenance_state_generation",
    "local_provenance_append_test",
    "local_docs_edit",
    "local_policy_edit",
    "local_template_edit",
    "local_proposal_generation",
    "local_proposal_validation",
    "local_template_validation",
    "local_adapter_report_generation",
}
REQUIRED_FIELDS = [
    "schema_version",
    "version",
    "manifest_kind",
    "proposal_id",
    "title",
    "status",
    "created_at",
    "scope",
    "operation_type",
    "target",
    "reason",
    "evidence",
    "risk_level",
    "required_approvals",
    "destructive",
    "apply_allowed",
    "expected_identity",
    "repo",
    "apply_plan",
    "blocked_actions",
    "actions",
    "blockers",
    "warnings",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return slug or "proposal"


def _git(repo_root: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=repo_root, text=True, capture_output=True)
    return proc.stdout.strip() if proc.returncode == 0 else "unknown"


def _rel(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _resolve_artifact_path(repo_root: Path, path: str | Path | None, default_rel: str) -> Path:
    candidate = Path(path) if path else repo_root / default_rel
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    candidate = candidate.resolve()
    artifacts_root = (repo_root / "artifacts").resolve()
    if not (candidate == artifacts_root or str(candidate).startswith(str(artifacts_root) + "/")):
        raise ValueError(f"v1.1 proposal output must stay under repo artifacts/: {candidate}")
    return candidate


def proposal_schema() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "version": SCHEMA_VERSION,
        "manifest_kind": MANIFEST_KIND,
        "required_fields": REQUIRED_FIELDS,
        "audit_fields": {
            "scope": "Bounded implementation/review scope for the proposal.",
            "operation_type": "Proposal operation class; never an apply command.",
            "target": "Repo-relative or logical target under review.",
            "reason": "Human-auditable reason for generating the proposal.",
            "evidence": "Explicit local evidence paths or claims supporting review.",
            "risk_level": "Expected risk before review; destructive proposals are blocked.",
            "required_approvals": "Approvals required before any future apply implementation.",
            "destructive": "Must be false for v1.1 proposal manifests.",
            "apply_allowed": "Must be false without reviewed approval.",
            "blockers": "Structured blockers found while building or validating the proposal.",
            "warnings": "Structured warnings found while building or validating the proposal.",
        },
        "apply_plan": {
            "review_gated": True,
            "human_approval_required": True,
            "apply_executed": False,
            "destructive_operations_allowed": False,
            "remote_publication_allowed": False,
            "provenance_upgrade_allowed": False,
        },
        "allowed_local_action_types": sorted(ALLOWED_LOCAL_ACTIONS),
        "blocked_action_types": BLOCKED_ACTIONS,
    }


def build_default_manifest(repo_root: Path, title: str = "v1.1 reviewed apply plan") -> dict[str, Any]:
    repo_root = repo_root.resolve()
    now = _utc_now()
    return {
        "schema_version": SCHEMA_VERSION,
        "version": SCHEMA_VERSION,
        "manifest_kind": MANIFEST_KIND,
        "proposal_id": f"proposal:{now}:{_slug(title)}",
        "title": title,
        "status": "draft",
        "created_at": now,
        "scope": "v1.1 reviewed-action-layer local baseline",
        "operation_type": "reviewed_apply_plan",
        "target": "repository-local governance pipeline",
        "reason": "Generate a deterministic, reviewable proposal artifact without executing apply behavior.",
        "evidence": [
            "docs/plans/v1.1-reviewed-action-layer.md",
            "policies/approval-gates.yaml",
            "src/graph_harness_maintain/proposals.py",
            "src/graph_harness_maintain/pipeline.py",
        ],
        "risk_level": "low",
        "required_approvals": ["human_review"],
        "destructive": False,
        "apply_allowed": False,
        "expected_identity": EXPECTED_IDENTITY,
        "repo": {
            "branch": _git(repo_root, "branch", "--show-current"),
            "head": _git(repo_root, "rev-parse", "HEAD"),
            "origin_main": _git(repo_root, "rev-parse", "origin/main"),
        },
        "apply_plan": {
            "framework": "reviewed_apply_plan",
            "review_gated": True,
            "human_approval_required": True,
            "apply_executed": False,
            "destructive_operations_allowed": False,
            "remote_publication_allowed": False,
            "provenance_upgrade_allowed": False,
            "local_provenance_append_test_allowed": True,
            "required_reviews": ["human_review"],
        },
        "blocked_actions": BLOCKED_ACTIONS,
        "allowed_local_actions": sorted(ALLOWED_LOCAL_ACTIONS),
        "actions": [],
        "blockers": [],
        "warnings": [],
        "notes": [
            "Proposal creation and validation are local artifact operations only.",
            "No apply execution command is provided in v1.1.",
        ],
    }


def validate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []

    for field in REQUIRED_FIELDS:
        if field not in manifest:
            blockers.append(f"missing required field: {field}")

    if manifest.get("schema_version") != SCHEMA_VERSION:
        blockers.append("schema_version must be 1.1")
    if manifest.get("manifest_kind") != MANIFEST_KIND:
        blockers.append(f"manifest_kind must be {MANIFEST_KIND}")
    if manifest.get("version") not in {SCHEMA_VERSION, None}:
        blockers.append("version must be 1.1 when provided")

    if manifest.get("destructive") is not False:
        blockers.append("destructive must be false for v1.1 proposals")
    if manifest.get("apply_allowed") is not False:
        blockers.append("apply_allowed must be false without reviewed approval")

    evidence = manifest.get("evidence")
    if not isinstance(evidence, list) or not evidence or not all(isinstance(item, str) and item.strip() for item in evidence):
        blockers.append("evidence must be a non-empty list of explicit audit strings")
    required_approvals = manifest.get("required_approvals")
    if not isinstance(required_approvals, list) or "human_review" not in required_approvals:
        blockers.append("required_approvals must include human_review")
    if not isinstance(manifest.get("blockers"), list):
        blockers.append("blockers must be a list")
    if not isinstance(manifest.get("warnings"), list):
        blockers.append("warnings must be a list")

    apply_plan = manifest.get("apply_plan")
    if not isinstance(apply_plan, dict):
        blockers.append("apply_plan must be an object")
        apply_plan = {}
    if apply_plan.get("review_gated") is not True:
        blockers.append("apply_plan.review_gated must be true")
    if apply_plan.get("human_approval_required") is not True:
        blockers.append("apply_plan.human_approval_required must be true")
    if apply_plan.get("apply_executed") is not False:
        blockers.append("apply_plan.apply_executed must be false for proposal validation")
    if apply_plan.get("destructive_operations_allowed") is not False:
        blockers.append("destructive operations must remain blocked")
    if apply_plan.get("remote_publication_allowed") is not False:
        blockers.append("remote publication must remain blocked")
    if apply_plan.get("provenance_upgrade_allowed") is not False:
        blockers.append("provenance upgrade must remain gated")

    blocked_actions = set(manifest.get("blocked_actions") or [])
    for required in sorted(REMOTE_PUBLICATION_ACTIONS | DESTRUCTIVE_ACTIONS | {"graph_mutation", "provenance_upgrade", "sensitive_export"}):
        if required not in blocked_actions:
            blockers.append(f"blocked_actions missing required gate: {required}")

    actions = manifest.get("actions")
    if not isinstance(actions, list):
        blockers.append("actions must be a list")
        actions = []
    for index, action in enumerate(actions):
        if not isinstance(action, dict):
            blockers.append(f"action {index} must be an object")
            continue
        action_id = action.get("id", f"index:{index}")
        action_type = str(action.get("type", ""))
        if not action_type:
            blockers.append(f"action {action_id} missing type")
        if action.get("destructive") is True:
            blockers.append(f"action {action_id} is destructive")
        if action.get("remote_publication") is True:
            blockers.append(f"action {action_id} attempts remote publication")
        if action_type in blocked_actions or action_type in REMOTE_PUBLICATION_ACTIONS or action_type in DESTRUCTIVE_ACTIONS:
            blockers.append(f"action {action_id} uses blocked action type: {action_type}")
        if action_type and action_type not in ALLOWED_LOCAL_ACTIONS and action_type not in GATED_ACTIONS and action_type not in blocked_actions:
            warnings.append(f"action {action_id} uses unknown action type: {action_type}")
        target = action.get("target")
        if isinstance(target, str) and (Path(target).is_absolute() or ".." in Path(target).parts):
            blockers.append(f"action {action_id} target must be repo-relative and non-parent-traversing")

    status = "PASS" if not blockers else "FAIL"
    return {
        "generated_at": _utc_now(),
        "status": status,
        "schema_version": SCHEMA_VERSION,
        "version": manifest.get("version"),
        "manifest_kind": manifest.get("manifest_kind"),
        "proposal_id": manifest.get("proposal_id"),
        "apply_allowed": manifest.get("apply_allowed") is True,
        "destructive": manifest.get("destructive") is True,
        "review_gated": apply_plan.get("review_gated") is True,
        "human_approval_required": apply_plan.get("human_approval_required") is True,
        "apply_executed": apply_plan.get("apply_executed") is True,
        "remote_publication_allowed": apply_plan.get("remote_publication_allowed") is True,
        "destructive_operations_allowed": apply_plan.get("destructive_operations_allowed") is True,
        "provenance_upgrade_allowed": apply_plan.get("provenance_upgrade_allowed") is True,
        "action_count": len(actions),
        "blockers": blockers,
        "warnings": warnings,
    }


def write_default_proposal(repo_root: Path, out_path: str | Path | None = None, title: str = "v1.1 reviewed apply plan") -> dict[str, Any]:
    repo_root = repo_root.resolve()
    manifest_path = _resolve_artifact_path(repo_root, out_path, "artifacts/v1.1/proposals/reviewed-apply-plan.json")
    schema_path = repo_root / "artifacts" / "v1.1" / "proposal-manifest.schema.json"
    manifest = build_default_manifest(repo_root, title)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    schema_path.write_text(json.dumps(proposal_schema(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    validation = validate_manifest(manifest)
    return {
        "generated_at": _utc_now(),
        "status": validation["status"],
        "path": _rel(repo_root, manifest_path),
        "schema_path": _rel(repo_root, schema_path),
        "proposal_id": manifest["proposal_id"],
        "review_gated": True,
        "human_approval_required": True,
        "apply_executed": False,
        "blockers": validation["blockers"],
        "warnings": validation["warnings"],
    }


def validate_proposal_file(repo_root: Path, manifest_path: str | Path | None = None, report_path: str | Path | None = None) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    path = _resolve_artifact_path(repo_root, manifest_path, "artifacts/v1.1/proposals/reviewed-apply-plan.json")
    report_target = _resolve_artifact_path(repo_root, report_path, "artifacts/v1.1/proposal-validation.json")
    if not path.exists():
        result = {
            "generated_at": _utc_now(),
            "status": "FAIL",
            "manifest_path": _rel(repo_root, path),
            "blockers": [f"proposal manifest missing: {_rel(repo_root, path)}"],
            "warnings": [],
        }
    else:
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
            result = validate_manifest(manifest)
            result["manifest_path"] = _rel(repo_root, path)
        except json.JSONDecodeError as exc:
            result = {
                "generated_at": _utc_now(),
                "status": "FAIL",
                "manifest_path": _rel(repo_root, path),
                "blockers": [f"invalid JSON: {exc}"],
                "warnings": [],
            }
    report_target.parent.mkdir(parents=True, exist_ok=True)
    result["path"] = _rel(repo_root, report_target)
    report_target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result
