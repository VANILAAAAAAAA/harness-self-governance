from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping, Any

EXPECTED_NAME = "VANILAAAAAAAA"
EXPECTED_EMAIL = "xchen247@uw.edu"
EXPECTED_IDENTITY = f"{EXPECTED_NAME} <{EXPECTED_EMAIL}>"
IDENTITY_FAIL_EXIT_CODE = 3

GITHUB_ACTIONS_BOT = "github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>"
HERMES_AGENT_MARKERS = ("Hermes Agent", "hermes-agent@users.noreply.github.com")

CommandResult = dict[str, Any]
CommandRunner = Callable[[list[str], Path], CommandResult]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _command_to_string(command: list[str]) -> str:
    return " ".join(command)


def _run(command: list[str], repo_root: Path) -> CommandResult:
    proc = subprocess.run(command, cwd=repo_root, text=True, capture_output=True)
    return {
        "command": _command_to_string(command),
        "exit_code": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def _coerce_result(command: list[str], result: CommandResult | str) -> CommandResult:
    """Accept old string-based test runners while normalizing to structured results."""
    if isinstance(result, Mapping):
        return {
            "command": str(result.get("command") or _command_to_string(command)),
            "exit_code": int(result.get("exit_code", 0)),
            "stdout": str(result.get("stdout", "")).strip(),
            "stderr": str(result.get("stderr", "")).strip(),
        }
    return {"command": _command_to_string(command), "exit_code": 0, "stdout": str(result).strip(), "stderr": ""}


def collect_identity_data(repo_root: Path, runner: CommandRunner | None = None) -> dict:
    runner = runner or _run
    commands = {
        "author_ident": ["git", "var", "GIT_AUTHOR_IDENT"],
        "committer_ident": ["git", "var", "GIT_COMMITTER_IDENT"],
        "local_user_name": ["git", "config", "--local", "user.name"],
        "local_user_email": ["git", "config", "--local", "user.email"],
        "reachable_refs": [
            "git",
            "log",
            "--all",
            "--format=%h | %D | author: %an <%ae> | committer: %cn <%ce> | %s",
        ],
    }
    command_results: dict[str, CommandResult] = {}
    for key, command in commands.items():
        try:
            command_results[key] = _coerce_result(command, runner(command, repo_root))
        except Exception as exc:  # defensive: identity reporting must not crash on git failures
            command_results[key] = {
                "command": _command_to_string(command),
                "exit_code": 255,
                "stdout": "",
                "stderr": f"{type(exc).__name__}: {exc}",
            }

    failed_commands = [key for key, result in command_results.items() if result["exit_code"] != 0]
    reachable_stdout = command_results["reachable_refs"]["stdout"]
    return {
        "author_ident": command_results["author_ident"]["stdout"],
        "committer_ident": command_results["committer_ident"]["stdout"],
        "local_user_name": command_results["local_user_name"]["stdout"],
        "local_user_email": command_results["local_user_email"]["stdout"],
        "reachable_refs": [line for line in reachable_stdout.splitlines() if line.strip()],
        "command_results": command_results,
        "git_command_results": command_results,
        "failed_commands": failed_commands,
    }


def _contains_hermes_agent(value: object) -> bool:
    text = "\n".join(value) if isinstance(value, list) else str(value or "")
    return any(marker in text for marker in HERMES_AGENT_MARKERS)


def _command_failed(identity_data: dict, key: str) -> bool:
    result = (identity_data.get("command_results") or {}).get(key, {})
    return result.get("exit_code", 0) != 0


def evaluate_identity_report(identity_data: dict, ci_mode: bool = False) -> dict:
    author = identity_data.get("author_ident", "") or ""
    committer = identity_data.get("committer_ident", "") or ""
    local_user_name = identity_data.get("local_user_name", "") or ""
    local_user_email = identity_data.get("local_user_email", "") or ""
    reachable_refs = identity_data.get("reachable_refs", []) or []
    command_results = identity_data.get("command_results") or identity_data.get("git_command_results") or {}
    failed_commands = list(identity_data.get("failed_commands") or [key for key, value in command_results.items() if value.get("exit_code", 0) != 0])

    blockers: list[str] = []
    warnings: list[str] = []
    author_matches = EXPECTED_IDENTITY in author
    committer_matches = EXPECTED_IDENTITY in committer

    hermes_agent_refs = [line for line in reachable_refs if _contains_hermes_agent(line)]
    hermes_agent_fields = [
        field
        for field, value in {
            "author": author,
            "committer": committer,
            "local_user_name": local_user_name,
            "local_user_email": local_user_email,
        }.items()
        if _contains_hermes_agent(value)
    ]

    if ci_mode:
        if _command_failed(identity_data, "author_ident") or not author.strip():
            blockers.append("CI author identity is missing or unreadable")
        if _command_failed(identity_data, "committer_ident") or not committer.strip():
            blockers.append("CI committer identity is missing or unreadable")
        if _command_failed(identity_data, "local_user_name") or not local_user_name.strip():
            warnings.append("CI local git config user.name is missing or unreadable")
        if _command_failed(identity_data, "local_user_email") or not local_user_email.strip():
            warnings.append("CI local git config user.email is missing or unreadable")
        if not author_matches:
            warnings.append("CI author identity does not match local user-owned identity")
        if not committer_matches:
            warnings.append("CI committer identity does not match local user-owned identity")
    else:
        if _command_failed(identity_data, "author_ident") or not author.strip():
            blockers.append("author identity missing or unreadable")
        elif not author_matches:
            blockers.append("author identity mismatch: expected user-owned identity")
        if _command_failed(identity_data, "committer_ident") or not committer.strip():
            blockers.append("committer identity missing or unreadable")
        elif not committer_matches:
            blockers.append("committer identity mismatch: expected user-owned identity")
        if _command_failed(identity_data, "local_user_name") or not local_user_name.strip():
            warnings.append("local git config user.name is missing or unreadable")
        if _command_failed(identity_data, "local_user_email") or not local_user_email.strip():
            warnings.append("local git config user.email is missing or unreadable")

    if hermes_agent_fields:
        blockers.append("Hermes Agent identity appears in current identity or local git config")
    if hermes_agent_refs:
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
        "local_user_name": local_user_name,
        "local_user_email": local_user_email,
        "reachable_refs": reachable_refs,
        "author_matches_expected": author_matches,
        "committer_matches_expected": committer_matches,
        "hermes_agent_refs": hermes_agent_refs,
        "command_results": command_results,
        "git_command_results": command_results,
        "failed_commands": failed_commands,
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
