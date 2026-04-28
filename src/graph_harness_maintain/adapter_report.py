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


def build_adapter_report(repo_root: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    adapters = [GitRepoAdapter(repo_root), FileTreeAdapter(repo_root), ArtifactStoreAdapter(repo_root)]
    report = {
        "generated_at": _utc_now(),
        "schema_version": "1.1",
        "status": "PASS",
        "reviewed_action_layer": "proposal_only",
        "apply_executed": False,
        "blocked_actions": BLOCKED_ACTIONS,
        "adapters": [],
        "warnings": [],
        "blockers": [],
    }
    for adapter in adapters:
        evidence = adapter.locate_evidence()
        proposals = adapter.propose_actions()
        report["adapters"].append(
            {
                "name": adapter.__class__.__name__,
                "inspect": adapter.inspect(),
                "evidence_count": len(evidence),
                "proposal_count": len(proposals),
                "proposals": proposals,
                "reviewed_action_support": "manifest_validation_only",
                "mutation_behavior": "approval_required",
                "apply_executed": False,
                "destructive_operations_allowed": False,
                "remote_publication_allowed": False,
                "provenance_upgrade_allowed": False,
                "maintenance_note": "adapter reports proposed actions only; mutation remains review-gated",
            }
        )
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
