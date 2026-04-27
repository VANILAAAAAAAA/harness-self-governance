from __future__ import annotations

import json
import tomllib
from datetime import datetime, timezone
from pathlib import Path


REQUIRED_TEMPLATE_FILES = [
    "templates/governance-policy.template.md",
    "templates/release-checklist.template.md",
    "templates/audit-report.template.md",
    "templates/adapter-review.template.md",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check(status: bool, detail: str) -> dict:
    return {"status": "PASS" if status else "FAIL", "detail": detail}


def audit_release_surface(repo_root: Path) -> dict:
    readme = repo_root / "README.md"
    readme_text = readme.read_text(encoding="utf-8") if readme.exists() else ""
    pyproject = repo_root / "pyproject.toml"
    pyproject_data = tomllib.loads(pyproject.read_text(encoding="utf-8")) if pyproject.exists() else {}
    scripts = pyproject_data.get("project", {}).get("scripts", {}) if pyproject_data else {}
    checks = {
        "readme_exists": _check(readme.exists(), "README.md exists"),
        "readme_purpose": _check("purpose" in readme_text.lower() or "project" in readme_text.lower(), "README has project purpose"),
        "readme_install": _check("install" in readme_text.lower(), "README has install instructions"),
        "readme_usage": _check("cli usage" in readme_text.lower() or "ghm " in readme_text.lower(), "README has CLI usage"),
        "readme_scope": _check("v1.0 scope" in readme_text.lower(), "README explains v1.0 scope"),
        "readme_approval_gates": _check("approval gate" in readme_text.lower(), "README explains approval gates"),
        "readme_architecture": _check("architecture" in readme_text.lower() or "mermaid" in readme_text.lower(), "README has architecture section or diagram"),
        "license_exists": _check((repo_root / "LICENSE").exists(), "LICENSE exists"),
        "pyproject_exists": _check(pyproject.exists(), "pyproject.toml exists"),
        "pyproject_metadata": _check(bool(pyproject_data.get("project")), "pyproject has package metadata"),
        "ghm_entrypoint": _check(scripts.get("ghm") == "graph_harness_maintain.cli:main", "pyproject has ghm entrypoint"),
        "templates_exist": _check(all((repo_root / path).exists() for path in REQUIRED_TEMPLATE_FILES), "required templates exist"),
        "tests_exist": _check((repo_root / "tests").exists(), "tests directory exists"),
        "ci_workflow_exists": _check((repo_root / ".github" / "workflows" / "ci.yml").exists(), "CI workflow exists"),
        "security_exists": _check((repo_root / "SECURITY.md").exists(), "SECURITY.md exists"),
        "contributing_exists": _check((repo_root / "CONTRIBUTING.md").exists(), "CONTRIBUTING.md exists"),
        "changelog_exists": _check((repo_root / "CHANGELOG.md").exists(), "CHANGELOG.md exists"),
        "code_of_conduct_exists": _check((repo_root / "CODE_OF_CONDUCT.md").exists(), "CODE_OF_CONDUCT.md exists"),
        "approval_policy_exists": _check((repo_root / "policies" / "approval-gates.yaml").exists(), "approval gates policy exists"),
        "package_imports_cleanly": _check((repo_root / "src" / "graph_harness_maintain" / "__init__.py").exists(), "source package import target exists"),
    }
    blockers = [name for name, result in checks.items() if result["status"] == "FAIL"]
    warnings: list[str] = []
    if "/home/" in readme_text or "C:\\Users\\" in readme_text:
        blockers.append("readme_private_details")
    status = "PASS" if not blockers else "FAIL"
    return {"generated_at": _utc_now(), "status": status, "checks": checks, "blockers": blockers, "warnings": warnings}


def write_release_audit(repo_root: Path, artifact_path: Path) -> dict:
    report = audit_release_surface(repo_root)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report["path"] = artifact_path.relative_to(repo_root).as_posix()
    return report
