from __future__ import annotations

from pathlib import Path


NOT_EXECUTED = [
    "git commit",
    "git push",
    "git tag",
    "GitHub Release",
    "PyPI publish",
    "raw archive apply",
    "delete",
    "move",
    "graph/events mutation",
    "quarantine",
    "rehydrate",
    "provenance upgrade",
    "sensitive export",
    "reviewed apply execution",
    "force push",
]


def _lines(items: list[str]) -> str:
    if not items:
        return "- none"
    return "\n".join(f"- {item}" for item in items)


def write_pipeline_report(
    repo_root: Path,
    artifact_path: Path,
    result: dict,
    git_state: dict,
    identity: dict,
    release_audit: dict,
    gates: dict,
    adapter: dict,
    evidence: dict,
    provenance: dict,
    tests: dict,
    smoke: dict,
    leak_scan: dict,
) -> None:
    content = f"""# v1.0 local release-candidate report

status
: {result['status']}

repo URL
: {git_state.get('remote_url') or 'none'}

current branch
: {git_state.get('branch')}

current HEAD
: {git_state.get('head')}

origin/main HEAD when available
: {git_state.get('origin_main_head') or 'unavailable'}

identity check
: {identity.get('status')}

worktree status
: {_lines(git_state.get('worktree_status', []))}

open-source surface status
: {release_audit.get('status')}

approval gates status
: {gates.get('status')}

adapter status
: {adapter.get('status')}

evidence index status
: {evidence.get('status')}

provenance status
: {provenance.get('status')}

tests status
: {tests.get('status')}

package smoke status
: {smoke.get('package_import')}

CLI smoke status
: {smoke.get('cli_smoke')}

leak scan status
: {leak_scan.get('status')}

blockers
: {_lines(result.get('blockers', []))}

warnings
: {_lines(result.get('warnings', []))}

human approval required actions
: {_lines(result.get('human_approval_required', []))}

not executed actions
: {_lines(NOT_EXECUTED)}

next recommended local step
: Review local artifacts and decide whether to approve commit.
"""
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(content, encoding="utf-8")


def write_v1_1_pipeline_report(
    repo_root: Path,
    artifact_path: Path,
    result: dict,
    git_state: dict,
    identity: dict,
    release_audit: dict,
    gates: dict,
    proposal: dict,
    proposal_validation: dict,
    templates: dict,
    adapter: dict,
    provenance_append: dict,
    provenance: dict,
    evidence: dict,
    tests: dict,
    smoke: dict,
    leak_scan: dict,
) -> None:
    content = f"""# v1.1 local release-candidate report

status
: {result['status']}

current branch
: {git_state.get('branch')}

current HEAD
: {git_state.get('head')}

origin/main HEAD when available
: {git_state.get('origin_main_head') or 'unavailable'}

identity check
: {identity.get('status')}

worktree status
: {_lines(git_state.get('worktree_status', []))}

open-source surface status
: {release_audit.get('status')}

approval gates status
: {gates.get('status')}

proposal create status
: {proposal.get('status')}

proposal validation status
: {proposal_validation.get('status')}

template validation status
: {templates.get('status')}

adapter report status
: {adapter.get('status')}

local provenance append status
: {provenance_append.get('status')}

provenance current state status
: {provenance.get('status')}

evidence index status
: {evidence.get('status')}

tests status
: {tests.get('status')}

package smoke status
: {smoke.get('package_import')}

CLI smoke status
: {smoke.get('cli_smoke')}

leak scan status
: {leak_scan.get('status')}

reviewed apply gated
: {result.get('reviewed_apply_gated')}

remote publication allowed
: {result.get('remote_publication_allowed')}

provenance upgrade allowed
: {result.get('provenance_upgrade_allowed')}

blockers
: {_lines(result.get('blockers', []))}

warnings
: {_lines(result.get('warnings', []))}

human approval required actions
: {_lines(result.get('human_approval_required', []))}

artifacts
: {_lines(result.get('artifacts', []))}

not executed actions
: {_lines(result.get('not_executed_actions', NOT_EXECUTED))}

next recommended local step
: Review local v1.1 artifacts and decide whether to approve a future commit. Do not push, tag, release, or publish from this report.
"""
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(content, encoding="utf-8")
