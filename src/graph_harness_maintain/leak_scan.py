from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path


PUBLIC_SCAN_PATHS = [
    "README.md",
    "LICENSE",
    "pyproject.toml",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    ".gitignore",
    "policies",
    "templates",
    "src/graph_harness_maintain",
    "tests",
    ".github/workflows/ci.yml",
]

RULES = [
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"), "blocking"),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |)?PRIVATE KEY-----"), "blocking"),
    ("absolute_path", re.compile(r"(?:^|[\s\"'=:\[,])/(?:home|mnt|tmp|Users|opt|var)/[^\s\"'\],}]+"), "blocking"),
    ("windows_path", re.compile(r"(?:^|[\s\"'=:\[,])[A-Za-z]:[\\/]+[^\s\"'\],}]+"), "blocking"),
    ("wsl_path", re.compile(r"(?:wsl\$|wsl\.localhost)[\\/]+[^\s\"'\],}]+", re.I), "blocking"),
    ("token_assignment", re.compile(r"(?i)\b(?:token|password|secret|api[_-]?key)\b\s*[:=]\s*['\"]?[^'\"\s]{8,}"), "blocking"),
    ("local_identity_email", re.compile(r"\bxchen247@uw\.edu\b", re.I), "blocking"),
    ("local_username", re.compile(r"\bvanila\b", re.I), "warning"),
]

ALLOWED_CONTEXTS = {
    "src/graph_harness_maintain/identity.py",
    "src/graph_harness_maintain/policy.py",
    "src/graph_harness_maintain/leak_scan.py",
    "src/graph_harness_maintain/release_audit.py",
    "scripts/release_leak_scan.py",
}

LEAK_SCAN_FAIL_EXIT_CODE = 5


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iter_public_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for rel in PUBLIC_SCAN_PATHS:
        path = repo_root / rel
        if path.is_file() and path.suffix != ".pyc":
            files.append(path)
        elif path.is_dir():
            for item in path.rglob("*"):
                if not item.is_file() or item.suffix == ".pyc" or "__pycache__" in item.parts:
                    continue
                files.append(item)
    return sorted(set(files))


def scan_public_surface(repo_root: Path) -> dict:
    findings: list[dict] = []
    for path in _iter_public_files(repo_root):
        rel = path.relative_to(repo_root).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            for rule_name, pattern, classification in RULES:
                if pattern.search(line):
                    allowed = rel in ALLOWED_CONTEXTS or rel.startswith("tests/")
                    findings.append(
                        {
                            "rule": rule_name,
                            "classification": "informational" if allowed else classification,
                            "path": rel,
                            "line": lineno,
                            "excerpt": line.strip()[:240],
                            "allowed_context": allowed,
                        }
                    )
    blocking_count = sum(1 for item in findings if item["classification"] == "blocking")
    warning_count = sum(1 for item in findings if item["classification"] == "warning")
    status = "PASS" if blocking_count == 0 else "FAIL"
    return {
        "generated_at": _utc_now(),
        "status": status,
        "blocking_count": blocking_count,
        "warning_count": warning_count,
        "informational_count": sum(1 for item in findings if item["classification"] == "informational"),
        "findings": findings,
        "exit_code": 0 if blocking_count == 0 else LEAK_SCAN_FAIL_EXIT_CODE,
    }


def write_leak_scan(repo_root: Path, artifact_path: Path) -> dict:
    report = scan_public_surface(repo_root)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report["path"] = artifact_path.relative_to(repo_root).as_posix()
    return report
