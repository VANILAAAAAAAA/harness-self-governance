from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

EXPECTED_NAME = "VANILAAAAAAAA"
EXPECTED_EMAIL = "xchen247@uw.edu"
EXPECTED_IDENTITY = f"{EXPECTED_NAME} <{EXPECTED_EMAIL}>"
IDENTITY_FAIL_EXIT_CODE = 3

CommandRunner = Callable[[list[str], Path], str]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run(command: list[str], repo_root: Path) -> str:
    proc = subprocess.run(command, cwd=repo_root, text=True, capture_output=True, check=True)
    return proc.stdout.strip()


def collect_identity_data(repo_root: Path, runner: CommandRunner | None = None) -> dict:
    runner = runner or _run
    return {
        "author_ident": runner(["git", "var", "GIT_AUTHOR_IDENT"], repo_root),
        "committer_ident": runner(["git", "var", "GIT_COMMITTER_IDENT"], repo_root),
        "local_user_name": runner(["git", "config", "--local", "user.name"], repo_root),
        "local_user_email": runner(["git", "config", "--local", "user.email"], repo_root),
        "reachable_refs": [
            line
            for line in runner(
                [
                    "git",
                    "log",
                    "--all",
                    "--format=%h | %D | author: %an <%ae> | committer: %cn <%ce> | %s",
                ],
                repo_root,
            ).splitlines()
            if line.strip()
        ],
    }


def evaluate_identity_report(identity_data: dict, ci_mode: bool = False) -> dict:
    author = identity_data.get("author_ident", "")
    committer = identity_data.get("committer_ident", "")
    blockers: list[str] = []
    warnings: list[str] = []
    author_matches = EXPECTED_IDENTITY in author
    committer_matches = EXPECTED_IDENTITY in committer
    reachable_refs = identity_data.get("reachable_refs", [])
    public_identity_hits = [
        line for line in reachable_refs if "Hermes Agent" in line or "hermes-agent@users.noreply.github.com" in line
    ]

    if ci_mode:
        if not author.strip() or not committer.strip():
            blockers.append("CI identity is missing")
        if not author_matches:
            warnings.append("CI author identity does not match local user-owned identity")
        if not committer_matches:
            warnings.append("CI committer identity does not match local user-owned identity")
    else:
        if not author_matches:
            blockers.append("author identity mismatch: expected user-owned identity")
        if not committer_matches:
            blockers.append("committer identity mismatch: expected user-owned identity")

    if public_identity_hits:
        blockers.append("reachable git history still contains Hermes Agent identity")

    if blockers:
        status = "FAIL"
        exit_code = IDENTITY_FAIL_EXIT_CODE
    elif warnings:
        status = "PASS_WITH_WARNINGS"
        exit_code = 0
    else:
        status = "PASS"
        exit_code = 0

    return {
        "generated_at": _utc_now(),
        "ci_mode": ci_mode,
        "expected_identity": EXPECTED_IDENTITY,
        "author": author,
        "committer": committer,
        "local_user_name": identity_data.get("local_user_name"),
        "local_user_email": identity_data.get("local_user_email"),
        "author_matches_expected": author_matches,
        "committer_matches_expected": committer_matches,
        "hermes_agent_refs": public_identity_hits,
        "status": status,
        "warnings": warnings,
        "blockers": blockers,
        "exit_code": exit_code,
    }


def run_identity_check(repo_root: Path, artifact_path: Path, ci_mode: bool = False) -> dict:
    report = evaluate_identity_report(collect_identity_data(repo_root), ci_mode=ci_mode)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report["path"] = artifact_path.relative_to(repo_root).as_posix()
    return report
