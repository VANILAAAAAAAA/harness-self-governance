from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TEMPLATE_REQUIREMENTS = {
    "adapter-review.template.md": ["# Adapter Review Template", "## Adapter", "read-only behavior", "approval-gated proposals"],
    "audit-report.template.md": ["# Audit Report Template", "## Status", "## Blockers"],
    "governance-policy.template.md": ["# Governance Policy Template", "## Purpose"],
    "release-checklist.template.md": ["# Release Checklist Template", "verify identity", "obtain explicit human approval"],
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rel(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def validate_template_file(path: Path, required_fragments: list[str]) -> dict[str, Any]:
    findings: list[str] = []
    if not path.exists():
        return {"path": path.as_posix(), "status": "FAIL", "findings": ["missing template"]}
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        findings.append("template is empty")
    if not text.lstrip().startswith("# "):
        findings.append("template must start with H1")
    for fragment in required_fragments:
        if fragment not in text:
            findings.append(f"missing required fragment: {fragment}")
    return {"path": path.as_posix(), "status": "PASS" if not findings else "FAIL", "findings": findings}


def validate_templates(repo_root: Path, report_path: str | Path | None = None) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    report_target = Path(report_path) if report_path else repo_root / "artifacts" / "v1.1" / "template-validation.json"
    if not report_target.is_absolute():
        report_target = repo_root / report_target
    report_target = report_target.resolve()
    artifacts_root = (repo_root / "artifacts").resolve()
    if not (report_target == artifacts_root or str(report_target).startswith(str(artifacts_root) + "/")):
        raise ValueError(f"template validation report must stay under repo artifacts/: {report_target}")

    results = []
    for name, fragments in sorted(TEMPLATE_REQUIREMENTS.items()):
        path = repo_root / "templates" / name
        item = validate_template_file(path, fragments)
        item["path"] = _rel(repo_root, path)
        results.append(item)

    blockers = [f"{item['path']}: {finding}" for item in results for finding in item["findings"]]
    report = {
        "generated_at": _utc_now(),
        "status": "PASS" if not blockers else "FAIL",
        "template_count": len(results),
        "templates": results,
        "blockers": blockers,
        "warnings": [],
        "path": _rel(repo_root, report_target),
    }
    report_target.parent.mkdir(parents=True, exist_ok=True)
    report_target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
