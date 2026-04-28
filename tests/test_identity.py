from __future__ import annotations

from pathlib import Path

from graph_harness_maintain.identity import (
    EXPECTED_IDENTITY,
    GITHUB_ACTIONS_BOT,
    collect_identity_data,
    evaluate_identity_report,
)


def _command_result(command: str, stdout: str = "", exit_code: int = 0, stderr: str = "") -> dict:
    return {"command": command, "exit_code": exit_code, "stdout": stdout, "stderr": stderr}


def _make_identity_data(
    author: str,
    committer: str,
    *,
    local_user_name: str = "VANILAAAAAAAA",
    local_user_email: str = "xchen247@uw.edu",
    reachable_refs: list[str] | None = None,
    command_overrides: dict[str, dict] | None = None,
) -> dict:
    command_results = {
        "author_ident": _command_result("git var GIT_AUTHOR_IDENT", author),
        "committer_ident": _command_result("git var GIT_COMMITTER_IDENT", committer),
        "local_user_name": _command_result("git config --local user.name", local_user_name),
        "local_user_email": _command_result("git config --local user.email", local_user_email),
        "reachable_refs": _command_result(
            "git log --all --format=...",
            "\n".join(
                reachable_refs
                if reachable_refs is not None
                else [
                    "abc123 | HEAD -> main | author: VANILAAAAAAAA <xchen247@uw.edu> | committer: VANILAAAAAAAA <xchen247@uw.edu> | init"
                ]
            ),
        ),
    }
    if command_overrides:
        command_results.update(command_overrides)
    return {
        "author_ident": command_results["author_ident"]["stdout"],
        "committer_ident": command_results["committer_ident"]["stdout"],
        "local_user_name": command_results["local_user_name"]["stdout"],
        "local_user_email": command_results["local_user_email"]["stdout"],
        "reachable_refs": [line for line in command_results["reachable_refs"]["stdout"].splitlines() if line.strip()],
        "command_results": command_results,
        "git_command_results": command_results,
        "failed_commands": [key for key, value in command_results.items() if value["exit_code"] != 0],
    }


def test_local_mode_passes_when_expected_identity_matches() -> None:
    report = evaluate_identity_report(_make_identity_data(EXPECTED_IDENTITY, EXPECTED_IDENTITY), ci_mode=False)
    assert report["status"] == "PASS"
    assert report["exit_code"] == 0
    assert report["author_matches_expected"] is True
    assert report["committer_matches_expected"] is True


def test_local_mode_fails_when_identity_mismatches() -> None:
    report = evaluate_identity_report(
        _make_identity_data("Someone Else <else@example.com>", EXPECTED_IDENTITY),
        ci_mode=False,
    )
    assert report["status"] == "FAIL"
    assert report["exit_code"] == 3
    assert any("author identity mismatch" in blocker for blocker in report["blockers"])


def test_local_mode_fails_when_author_identity_is_hermes_agent() -> None:
    report = evaluate_identity_report(
        _make_identity_data("Hermes Agent <hermes-agent@users.noreply.github.com>", EXPECTED_IDENTITY),
        ci_mode=False,
    )
    assert report["status"] == "FAIL"
    assert report["exit_code"] == 3
    assert any("Hermes Agent identity" in blocker for blocker in report["blockers"])


def test_local_mode_fails_when_committer_identity_is_hermes_agent() -> None:
    report = evaluate_identity_report(
        _make_identity_data(EXPECTED_IDENTITY, "Hermes Agent <hermes-agent@users.noreply.github.com>"),
        ci_mode=False,
    )
    assert report["status"] == "FAIL"
    assert report["exit_code"] == 3
    assert any("Hermes Agent identity" in blocker for blocker in report["blockers"])


def test_ci_mode_allows_github_actions_bot_identity_with_warnings() -> None:
    report = evaluate_identity_report(
        _make_identity_data(
            GITHUB_ACTIONS_BOT,
            GITHUB_ACTIONS_BOT,
            local_user_name="github-actions[bot]",
            local_user_email="41898282+github-actions[bot]@users.noreply.github.com",
        ),
        ci_mode=True,
    )
    assert report["status"] == "PASS_WITH_WARNINGS"
    assert report["exit_code"] == 0
    assert report["ci_mode"] is True
    assert report["author_matches_expected"] is False
    assert report["committer_matches_expected"] is False


def test_ci_mode_fails_for_hermes_agent_identity() -> None:
    report = evaluate_identity_report(
        _make_identity_data("Hermes Agent <hermes-agent@users.noreply.github.com>", GITHUB_ACTIONS_BOT),
        ci_mode=True,
    )
    assert report["status"] == "FAIL"
    assert report["exit_code"] == 3
    assert any("Hermes Agent identity" in blocker for blocker in report["blockers"])


def test_missing_local_git_config_in_ci_mode_is_warning_not_blocker() -> None:
    report = evaluate_identity_report(
        _make_identity_data(
            GITHUB_ACTIONS_BOT,
            GITHUB_ACTIONS_BOT,
            local_user_name="",
            local_user_email="",
            command_overrides={
                "local_user_name": _command_result("git config --local user.name", "", 1, "missing"),
                "local_user_email": _command_result("git config --local user.email", "", 1, "missing"),
            },
        ),
        ci_mode=True,
    )
    assert report["status"] == "PASS_WITH_WARNINGS"
    assert report["exit_code"] == 0
    assert any("user.name" in warning for warning in report["warnings"])
    assert any("user.email" in warning for warning in report["warnings"])
    assert not report["blockers"]


def test_ci_mode_fails_when_git_var_identity_is_unreadable() -> None:
    report = evaluate_identity_report(
        _make_identity_data(
            "",
            GITHUB_ACTIONS_BOT,
            command_overrides={"author_ident": _command_result("git var GIT_AUTHOR_IDENT", "", 1, "no identity")},
        ),
        ci_mode=True,
    )
    assert report["status"] == "FAIL"
    assert report["exit_code"] == 3
    assert any("CI author identity" in blocker for blocker in report["blockers"])


def test_collect_identity_data_handles_nonzero_local_config_without_throwing(tmp_path: Path) -> None:
    calls: list[str] = []

    def runner(command: list[str], repo_root: Path) -> dict:
        calls.append(" ".join(command))
        command_text = " ".join(command)
        if command == ["git", "config", "--local", "user.name"]:
            return _command_result(command_text, "", 1, "missing user.name")
        if command == ["git", "config", "--local", "user.email"]:
            return _command_result(command_text, "", 1, "missing user.email")
        if command == ["git", "var", "GIT_AUTHOR_IDENT"]:
            return _command_result(command_text, GITHUB_ACTIONS_BOT)
        if command == ["git", "var", "GIT_COMMITTER_IDENT"]:
            return _command_result(command_text, GITHUB_ACTIONS_BOT)
        return _command_result(command_text, "abc123 | HEAD -> main | author: Test <t@example.com> | committer: Test <t@example.com> | init")

    data = collect_identity_data(tmp_path, runner=runner)
    assert data["local_user_name"] == ""
    assert data["local_user_email"] == ""
    assert set(data["failed_commands"]) == {"local_user_name", "local_user_email"}
    assert len(calls) == 5
