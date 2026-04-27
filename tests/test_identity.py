from __future__ import annotations

from graph_harness_maintain.identity import EXPECTED_IDENTITY, evaluate_identity_report


def _make_identity_data(author: str, committer: str) -> dict:
    return {
        "author_ident": author,
        "committer_ident": committer,
        "local_user_name": "VANILAAAAAAAA",
        "local_user_email": "xchen247@uw.edu",
        "reachable_refs": [
            "abc123 | HEAD -> main | author: VANILAAAAAAAA <xchen247@uw.edu> | committer: VANILAAAAAAAA <xchen247@uw.edu> | init"
        ],
    }


def test_identity_passes_when_expected_identity_matches() -> None:
    report = evaluate_identity_report(_make_identity_data(EXPECTED_IDENTITY, EXPECTED_IDENTITY), ci_mode=False)
    assert report["status"] == "PASS"
    assert report["exit_code"] == 0
    assert report["author_matches_expected"] is True
    assert report["committer_matches_expected"] is True


def test_identity_fails_when_author_identity_is_hermes_agent() -> None:
    report = evaluate_identity_report(
        _make_identity_data("Hermes Agent <hermes-agent@users.noreply.github.com>", EXPECTED_IDENTITY),
        ci_mode=False,
    )
    assert report["status"] == "FAIL"
    assert report["exit_code"] == 3
    assert any("author identity mismatch" in blocker for blocker in report["blockers"])


def test_identity_fails_when_committer_identity_is_hermes_agent() -> None:
    report = evaluate_identity_report(
        _make_identity_data(EXPECTED_IDENTITY, "Hermes Agent <hermes-agent@users.noreply.github.com>"),
        ci_mode=False,
    )
    assert report["status"] == "FAIL"
    assert report["exit_code"] == 3
    assert any("committer identity mismatch" in blocker for blocker in report["blockers"])


def test_identity_ci_mode_reports_identity_without_local_email_block() -> None:
    report = evaluate_identity_report(
        _make_identity_data("CI Bot <ci@example.invalid>", "CI Bot <ci@example.invalid>"),
        ci_mode=True,
    )
    assert report["status"] == "PASS_WITH_WARNINGS"
    assert report["exit_code"] == 0
    assert report["ci_mode"] is True
    assert report["author_matches_expected"] is False
    assert report["committer_matches_expected"] is False
    assert report["warnings"]
