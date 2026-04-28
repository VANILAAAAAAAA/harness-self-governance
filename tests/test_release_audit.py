from __future__ import annotations

from pathlib import Path

from graph_harness_maintain.release_audit import audit_release_surface


REQUIRED_FILES = {
    "README.md": "# graph-harness-maintain\n\nInstall\n",
    "LICENSE": "MIT License\n",
    "pyproject.toml": "[project]\nname='graph-harness-maintain'\n[project.scripts]\nghm='graph_harness_maintain.cli:main'\n",
    "CHANGELOG.md": "# Changelog\n\n## Unreleased\n\n- Added v1.0 local governance pipeline.\n",
    "CONTRIBUTING.md": "# Contributing\n",
    "SECURITY.md": "# Security\n\nReport vulnerabilities privately.\n",
    "CODE_OF_CONDUCT.md": "# Code of Conduct\n",
    ".gitignore": "__pycache__/\n",
    ".github/workflows/ci.yml": "name: CI\n",
    "policies/approval-gates.yaml": "version: 1\n",
    "templates/governance-policy.template.md": "# Governance Policy\n",
    "templates/release-checklist.template.md": "# Release Checklist\n",
    "templates/audit-report.template.md": "# Audit Report\n",
    "templates/adapter-review.template.md": "# Adapter Review\n",
    "src/graph_harness_maintain/__init__.py": "__version__='1.0.0'\n",
    "tests/test_cli.py": "def test_placeholder():\n    assert True\n",
}


def _write_repo_layout(root: Path) -> None:
    for rel, content in REQUIRED_FILES.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    (root / "README.md").write_text(
        "# graph-harness-maintain\n\nPurpose\n\n## Install\n\npip install -e .\n\n## CLI usage\n\nghm pipeline local-rc\nghm pipeline v1.1-rc\n\n## v1.0 scope\n\nread-only\n\n## v1.1 scope\n\nproposal-only\n\n## Artifact layout\n\nartifacts/v1/ and artifacts/v1.1/\n\n## Safety boundary\n\ndestructive operations blocked\n\n## approval gates\n\ncommit requires approval\n\n## architecture\n\ndiagram\n",
        encoding="utf-8",
    )


def test_readme_check(tmp_path: Path) -> None:
    _write_repo_layout(tmp_path)
    audit = audit_release_surface(tmp_path)
    assert audit["checks"]["readme_exists"]["status"] == "PASS"
    assert audit["checks"]["readme_usage"]["status"] == "PASS"
    assert audit["checks"]["readme_artifact_paths"]["status"] == "PASS"
    assert audit["checks"]["readme_safety_boundary"]["status"] == "PASS"


def test_license_check(tmp_path: Path) -> None:
    _write_repo_layout(tmp_path)
    audit = audit_release_surface(tmp_path)
    assert audit["checks"]["license_exists"]["status"] == "PASS"


def test_pyproject_check(tmp_path: Path) -> None:
    _write_repo_layout(tmp_path)
    audit = audit_release_surface(tmp_path)
    assert audit["checks"]["pyproject_exists"]["status"] == "PASS"
    assert audit["checks"]["ghm_entrypoint"]["status"] == "PASS"


def test_templates_check(tmp_path: Path) -> None:
    _write_repo_layout(tmp_path)
    audit = audit_release_surface(tmp_path)
    assert audit["checks"]["templates_exist"]["status"] == "PASS"


def test_tests_directory_check(tmp_path: Path) -> None:
    _write_repo_layout(tmp_path)
    audit = audit_release_surface(tmp_path)
    assert audit["checks"]["tests_exist"]["status"] == "PASS"


def test_ci_workflow_check(tmp_path: Path) -> None:
    _write_repo_layout(tmp_path)
    audit = audit_release_surface(tmp_path)
    assert audit["checks"]["ci_workflow_exists"]["status"] == "PASS"
