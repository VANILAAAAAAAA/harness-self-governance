from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


TOKEN_PATTERNS = [
    re.compile(r"(https?://)([^/@\s]+)@"),
    re.compile(r"(ssh://)([^/@\s]+)@"),
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run(command: list[str], repo_root: Path) -> str:
    proc = subprocess.run(command, cwd=repo_root, text=True, capture_output=True)
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def redact_remote_url(url: str) -> str:
    redacted = url.strip()
    for pattern in TOKEN_PATTERNS:
        redacted = pattern.sub(r"\1[REDACTED]@", redacted)
    return redacted


def collect_git_state(repo_root: Path) -> dict:
    status_lines = _run(["git", "status", "--short"], repo_root).splitlines()
    branch = _run(["git", "branch", "--show-current"], repo_root)
    head = _run(["git", "rev-parse", "HEAD"], repo_root)
    origin_main = _run(["git", "rev-parse", "origin/main"], repo_root)
    remote_url = redact_remote_url(_run(["git", "remote", "get-url", "origin"], repo_root))
    staged = _run(["git", "diff", "--cached", "--name-only"], repo_root).splitlines()
    latest_commits = _run(["git", "log", "--oneline", "-5"], repo_root).splitlines()
    untracked = [line[3:] for line in status_lines if line.startswith("?? ")]
    return {
        "generated_at": _utc_now(),
        "branch": branch,
        "head": head,
        "origin_main_head": origin_main or None,
        "worktree_status": status_lines,
        "staged_changes": [line for line in staged if line],
        "untracked_files": untracked,
        "latest_commits": [line for line in latest_commits if line],
        "remote_url": remote_url or None,
        "status": "PASS",
    }


def write_git_state(repo_root: Path, artifact_path: Path) -> dict:
    report = collect_git_state(repo_root)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report["path"] = artifact_path.relative_to(repo_root).as_posix()
    return report
