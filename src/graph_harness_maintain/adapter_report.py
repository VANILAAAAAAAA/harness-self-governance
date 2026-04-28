from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .adapters import ArtifactStoreAdapter, FileTreeAdapter, GitRepoAdapter
from .proposals import BLOCKED_ACTIONS


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rel(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _sanitize_inspect(repo_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    root_text = repo_root.as_posix()
    for key, value in payload.items():
        if isinstance(value, str) and value.startswith(root_text):
            try:
                sanitized[key] = Path(value).resolve().relative_to(repo_root).as_posix() or "."
            except ValueError:
                sanitized[key] = "<outside-repo>"
        else:
            sanitized[key] = value
    return sanitized


def _adapter_metadata(name: str) -> dict[str, Any]:
    common_boundary = {
        "read_only_behavior": True,
        "no_execution_side_effects": True,
        "mutation_behavior": "approval_required",
        "apply_executed": False,
        "destructive_operations_allowed": False,
        "remote_publication_allowed": False,
        "provenance_upgrade_allowed": False,
    }
    metadata = {
        "GitRepoAdapter": {
            "capabilities": ["inspect branch/head/status", "list tracked paths", "locate tracked source/test evidence"],
            "limitations": ["does not push, tag, release, or rewrite history", "does not mutate git state"],
            "inputs": ["repository git metadata", "tracked file list"],
            "outputs": ["read-only git inspection summary", "review-gated proposal hints"],
        },
        "FileTreeAdapter": {
            "capabilities": ["list repository files", "locate source/test/policy/template evidence"],
            "limitations": ["does not delete, move, quarantine, or rehydrate files", "does not write graph/event stores"],
            "inputs": ["repository file tree"],
            "outputs": ["read-only file evidence summary", "review-gated proposal hints"],
        },
        "ArtifactStoreAdapter": {
            "capabilities": ["list local artifacts", "locate JSON/Markdown artifact evidence"],
            "limitations": ["does not publish artifacts remotely", "does not export sensitive data", "does not apply raw archives"],
            "inputs": ["repository artifacts directory"],
            "outputs": ["read-only artifact evidence summary", "review-gated proposal hints"],
        },
    }
    return {**metadata.get(name, {}), "safety_boundary": common_boundary}


def build_adapter_report(repo_root: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    adapters = [GitRepoAdapter(repo_root), FileTreeAdapter(repo_root), ArtifactStoreAdapter(repo_root)]
    report = {
        "generated_at": _utc_now(),
        "schema_version": "1.1",
        "status": "PASS",
        "reviewed_action_layer": "proposal_only",
        "read_only_behavior": True,
        "no_execution_side_effects": True,
        "apply_executed": False,
        "blocked_actions": BLOCKED_ACTIONS,
        "safety_boundary": {
            "proposal_only": True,
            "reviewed_apply_gated": True,
            "destructive_operations_allowed": False,
            "remote_publication_allowed": False,
            "raw_archive_apply_allowed": False,
            "graph_mutation_allowed": False,
            "sensitive_export_allowed": False,
        },
        "adapters": [],
        "warnings": [],
        "blockers": [],
    }
    for adapter in adapters:
        evidence = adapter.locate_evidence()
        proposals = adapter.propose_actions()
        adapter_name = adapter.__class__.__name__
        metadata = _adapter_metadata(adapter_name)
        item = {
            "name": adapter_name,
            "inspect": _sanitize_inspect(repo_root, adapter.inspect()),
            "evidence_count": len(evidence),
            "proposal_count": len(proposals),
            "proposals": proposals,
            "reviewed_action_support": "manifest_validation_only",
            "mutation_behavior": "approval_required",
            "apply_executed": False,
            "destructive_operations_allowed": False,
            "remote_publication_allowed": False,
            "provenance_upgrade_allowed": False,
            "failure_modes": [],
            "maintenance_note": "adapter reports proposed actions only; mutation remains review-gated",
            **metadata,
        }
        for proposal in proposals:
            if proposal.get("requires_human_approval") is True:
                item["failure_modes"].append(f"proposal remains gated: {proposal.get('action')}")
        report["adapters"].append(item)
    return report


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# v1.1 adapter maintenance report",
        "",
        f"status: {report['status']}",
        f"reviewed_action_layer: {report['reviewed_action_layer']}",
        f"apply_executed: {report['apply_executed']}",
        "",
        "## Adapters",
        "",
    ]
    for item in report["adapters"]:
        lines.extend(
            [
                f"### {item['name']}",
                "",
                f"- evidence_count: {item['evidence_count']}",
                f"- proposal_count: {item['proposal_count']}",
                f"- mutation_behavior: {item['mutation_behavior']}",
                f"- apply_executed: {item['apply_executed']}",
                f"- read_only_behavior: {item['safety_boundary']['read_only_behavior']}",
                f"- no_execution_side_effects: {item['safety_boundary']['no_execution_side_effects']}",
                f"- capabilities: {', '.join(item['capabilities'])}",
                f"- limitations: {', '.join(item['limitations'])}",
                f"- inputs: {', '.join(item['inputs'])}",
                f"- outputs: {', '.join(item['outputs'])}",
                f"- failure_modes: {', '.join(item['failure_modes']) if item['failure_modes'] else 'none'}",
                f"- maintenance_note: {item['maintenance_note']}",
                "",
            ]
        )
    lines.extend(["## Blocked actions", ""])
    lines.extend(f"- {action}" for action in report["blocked_actions"])
    lines.append("")
    return "\n".join(lines)


def write_adapter_report(repo_root: Path, report_path: str | Path | None = None, markdown_path: str | Path | None = None) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    report_target = Path(report_path) if report_path else repo_root / "artifacts" / "v1.1" / "adapter-report.json"
    markdown_target = Path(markdown_path) if markdown_path else repo_root / "artifacts" / "v1.1" / "adapter-report.md"
    if not report_target.is_absolute():
        report_target = repo_root / report_target
    if not markdown_target.is_absolute():
        markdown_target = repo_root / markdown_target
    report_target = report_target.resolve()
    markdown_target = markdown_target.resolve()
    artifacts_root = (repo_root / "artifacts").resolve()
    for path in (report_target, markdown_target):
        if not (path == artifacts_root or str(path).startswith(str(artifacts_root) + "/")):
            raise ValueError(f"adapter report output must stay under repo artifacts/: {path}")

    report = build_adapter_report(repo_root)
    report["path"] = _rel(repo_root, report_target)
    report["markdown_path"] = _rel(repo_root, markdown_target)
    report_target.parent.mkdir(parents=True, exist_ok=True)
    markdown_target.parent.mkdir(parents=True, exist_ok=True)
    report_target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_target.write_text(_render_markdown(report), encoding="utf-8")
    return report
