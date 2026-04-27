#!/usr/bin/env python3
"""Release leak scanner for the limited graph-harness adapter.

Scans repository text files for credentials, absolute/private paths, raw EHR
terms, and patient-level identifiers. It is intentionally conservative, but
allows occurrences inside tests, schemas, and this deny-rule implementation.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", "dist", "build", ".venv", "venv", "artifacts"}
SKIP_SUFFIXES = {".pyc", ".pyo", ".so", ".dll", ".dylib", ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".tar", ".gz"}
MAX_TEXT_BYTES = 2_000_000

SAFE_CONTEXT_PARTS = {
    "tests",
    "scripts/release_leak_scan.py",
    "tests/fixtures",
    "src/graph_harness_maintain/schema.py",
}

RULES: list[tuple[str, re.Pattern[str], str]] = [
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |)?PRIVATE KEY-----"), "critical"),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "critical"),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"), "critical"),
    ("bearer_token", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}\b", re.I), "critical"),
    ("secret_assignment", re.compile(r"(?i)\b(?:api[_-]?key|secret(?:[_-]?key)?|token|password|credential)\b\s*[:=]\s*['\"]?[^'\"\s]{8,}"), "high"),
    ("ehrlab_private_path", re.compile(r"/home/vanila/(?:\.hermes/profiles/ehrlab|code/ehrtopath(?:-rich-to-structured)?)\b[^\s\"']*"), "high"),
    ("absolute_path", re.compile(r"(?:file:///[^\s\"']+|(?<![A-Za-z0-9_.-])/(?:home|mnt|tmp|Users|opt|var|workspace)/[^\s\"']+|[A-Za-z]:[\\/]+[^\s\"']+|\\\\+(?:wsl\$|wsl\.localhost)[\\/]+[^\s\"']+)", re.I), "medium"),
    ("raw_ehr_term", re.compile(r"(?i)\b(?:raw\s+ehr|ehr\s+raw|mimic|subject_id|hadm_id|icustay|patient[-_ ]?level|phi)\b"), "medium"),
]

@dataclass
class Finding:
    rule: str
    severity: str
    path: str
    line: int
    excerpt: str
    allowed: bool
    reason: str = ""


def rel_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def iter_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        rel_parts = path.relative_to(root).parts
        if any(part in SKIP_DIRS for part in rel_parts):
            continue
        if path.is_dir() or path.suffix in SKIP_SUFFIXES:
            continue
        yield path


def is_text_file(path: Path) -> bool:
    try:
        data = path.read_bytes()[:4096]
    except OSError:
        return False
    return b"\0" not in data


def safe_context(rel: str, rule: str, line_text: str) -> tuple[bool, str]:
    if rel == "artifacts/release_leak_scan.json":
        return True, "generated scan output"
    if rel.startswith("tests/"):
        return True, "test fixture or regression test"
    if rel.endswith("synthetic_schema.yaml") or "/schema" in rel:
        return True, "schema/test vocabulary"
    if rel == "scripts/release_leak_scan.py":
        return True, "deny-rule implementation"
    if rel == "README.md" and rule == "absolute_path" and "External Raw Storage" in line_text:
        return True, "documented local archive root for storage guard"
    if rel in {"src/graph_harness_maintain/export.py", "src/graph_harness_maintain/policy.py"}:
        return True, "sanitizer deny-rule implementation"
    if rule == "raw_ehr_term" and re.search(r"(?i)(deny|block|forbid|never export|no raw|raw EHR|patient-level)", line_text):
        return True, "policy/deny-rule wording"
    if rule in {"absolute_path", "ehrlab_private_path", "raw_ehr_term"} and rel.startswith("artifacts/") and "review" in rel:
        return True, "review artifact path provenance"
    return False, ""


def scan(root: Path) -> dict:
    findings: list[Finding] = []
    scanned_files = 0
    skipped_large = 0
    for path in iter_files(root):
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size > MAX_TEXT_BYTES:
            skipped_large += 1
            continue
        if not is_text_file(path):
            continue
        scanned_files += 1
        rel = rel_posix(path, root)
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, 1):
            for rule, pattern, severity in RULES:
                if pattern.search(line):
                    allowed, reason = safe_context(rel, rule, line)
                    excerpt = pattern.sub("[MATCH]", line.strip())[:240]
                    findings.append(Finding(rule, severity, rel, lineno, excerpt, allowed, reason))
    blocking = [f for f in findings if not f.allowed and f.severity in {"critical", "high", "medium"}]
    return {
        "ok": not blocking,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "scanned_files": scanned_files,
        "skipped_large_files": skipped_large,
        "finding_count": len(findings),
        "blocking_count": len(blocking),
        "findings": [asdict(f) for f in findings],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan repository for release-blocking leaks")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    out = Path(args.out).resolve() if args.out else root / "artifacts" / "release_leak_scan.json"
    result = scan(root)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": result["ok"], "blocking_count": result["blocking_count"], "finding_count": result["finding_count"], "out": str(out)}, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
