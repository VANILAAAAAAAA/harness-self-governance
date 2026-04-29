from __future__ import annotations

from pathlib import Path
from typing import Any

from .archive_gate import write_archive_gate_report
from .archive_quality import compiled_session_example_dir, validate_compiled_session_examples
from .context_gaps import list_context_gaps
from .repo_adapter import read_repo_manifest
from .schemas import SCHEMA_VERSION, deterministic_write_json, read_json, resolve_memory_root


def _stale_summaries_count(memory_root: Path, profile_id: str, project_id: str) -> int:
    session_index = read_json(
        memory_root / "projects" / profile_id / project_id / "session-index.json",
        default={"sessions": []},
    )
    stale = 0
    for session in session_index.get("sessions", []):
        summary = str(session.get("summary", "")).strip()
        if len(summary) < 24:
            stale += 1
    return stale


def _pending_updates_count(memory_root: Path) -> int:
    pending = read_json(memory_root / "routing" / "pending-updates.json", default={"updates": []})
    return len(pending.get("updates", []))


def build_archive_maintenance_report(repo_root: Path | str, memory_root: Path | str | None = None) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    memory_root = resolve_memory_root(memory_root)
    manifest = read_repo_manifest(repo_root)
    profile_id = manifest.get("profile")
    project_id = manifest.get("project")

    gate = read_json(memory_root / "reports" / "archive-gate-report.json")
    if not gate:
        gate = read_json(Path(write_archive_gate_report(repo_root, memory_root)["report_path"]))
    quality = validate_compiled_session_examples(compiled_session_example_dir(repo_root))
    gaps = list_context_gaps(repo_root, memory_root)
    stale_summaries_count = _stale_summaries_count(memory_root, profile_id, project_id)
    pending_updates_count = _pending_updates_count(memory_root)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "report_type": "archive_maintenance_report",
        "profile": profile_id,
        "project": project_id,
        "proposal_only": True,
        "archive_quality_status": quality["archive_quality_status"],
        "pending_updates_count": pending_updates_count,
        "context_gaps_count": len(gaps.get("gaps", [])),
        "stale_summaries_count": stale_summaries_count,
        "compiled_candidates_count": gate.get("counts", {}).get("compiled_candidate", 0),
        "forensic_only_count": gate.get("counts", {}).get("forensic_only", 0),
        "live_session_priority": True,
        "pending_update_supported": True,
        "compiled_candidate_requires_review": True,
        "forensic_raw_sessions_explicit_only": True,
        "raw_sessions_default_read": False,
        "raw_sessions_required": False,
        "quality": quality,
        "archive_gate": gate,
        "context_gaps": gaps.get("gaps", []),
        "warnings": [],
        "blockers": quality.get("blockers", []),
    }
    return payload


def write_archive_maintenance_report(repo_root: Path | str, memory_root: Path | str | None = None) -> dict[str, Any]:
    memory_root = resolve_memory_root(memory_root)
    payload = build_archive_maintenance_report(repo_root, memory_root)
    report_path = memory_root / "reports" / "archive-maintenance-report.json"
    deterministic_write_json(report_path, payload)
    status = "PASS" if not payload.get("blockers") else "PASS_WITH_WARNINGS"
    return {
        "status": status,
        "report_path": report_path.as_posix(),
        "archive_quality_status": payload["archive_quality_status"],
        "warnings": payload.get("warnings", []),
        "blockers": payload.get("blockers", []),
    }


def validate_archive_maintenance(repo_root: Path | str, memory_root: Path | str | None = None) -> dict[str, Any]:
    payload = build_archive_maintenance_report(repo_root, memory_root)
    blockers = []
    if payload["archive_quality_status"] != "PASS":
        blockers.append("compiled-session examples failed archive quality validation")
    status = "PASS" if not blockers else "PASS_WITH_WARNINGS"
    return {
        "status": status,
        "proposal_only": True,
        "archive_quality_status": payload["archive_quality_status"],
        "pending_updates_count": payload["pending_updates_count"],
        "context_gaps_count": payload["context_gaps_count"],
        "stale_summaries_count": payload["stale_summaries_count"],
        "compiled_candidates_count": payload["compiled_candidates_count"],
        "forensic_only_count": payload["forensic_only_count"],
        "warnings": payload.get("warnings", []),
        "blockers": blockers,
    }


def generate_archive_maintenance_proposal(repo_root: Path | str, memory_root: Path | str | None = None) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    memory_root = resolve_memory_root(memory_root)
    report = build_archive_maintenance_report(repo_root, memory_root)
    actions: list[dict[str, Any]] = []
    if report["pending_updates_count"]:
        actions.append({
            "id": "review-pending-updates",
            "title": "Review pending updates before any compilation",
            "reason": f"{report['pending_updates_count']} pending update(s) require explicit review.",
            "mutation_allowed": False,
        })
    if report["compiled_candidates_count"]:
        actions.append({
            "id": "review-compiled-candidates",
            "title": "Review curated compiled-session candidates",
            "reason": f"{report['compiled_candidates_count']} compiled candidate fixture(s) exist and require explicit archive-session command path.",
            "mutation_allowed": False,
        })
    if report["context_gaps_count"]:
        actions.append({
            "id": "repair-context-gaps",
            "title": "Repair context gaps",
            "reason": f"{report['context_gaps_count']} context gap(s) remain open.",
            "mutation_allowed": False,
        })
    if report["stale_summaries_count"]:
        actions.append({
            "id": "refresh-stale-summaries",
            "title": "Refresh stale summaries",
            "reason": f"{report['stale_summaries_count']} stale summary item(s) need curated revision.",
            "mutation_allowed": False,
        })
    if not actions:
        actions.append({
            "id": "no-op-observe",
            "title": "No archive mutation proposed",
            "reason": "Archive lifecycle is healthy; keep reviewed archive workflow manual.",
            "mutation_allowed": False,
        })
    payload = {
        "schema_version": SCHEMA_VERSION,
        "report_type": "archive_maintenance_proposal",
        "profile": report["profile"],
        "project": report["project"],
        "proposal_only": True,
        "live_session_priority": True,
        "pending_update_supported": True,
        "compiled_candidate_requires_review": True,
        "forensic_raw_sessions_explicit_only": True,
        "raw_sessions_default_read": False,
        "recommended_actions": actions,
        "report_snapshot": {
            "archive_quality_status": report["archive_quality_status"],
            "pending_updates_count": report["pending_updates_count"],
            "context_gaps_count": report["context_gaps_count"],
            "stale_summaries_count": report["stale_summaries_count"],
            "compiled_candidates_count": report["compiled_candidates_count"],
            "forensic_only_count": report["forensic_only_count"],
        },
        "warnings": [],
        "blockers": [],
    }
    proposal_path = memory_root / "reports" / "archive-maintenance-proposal.json"
    deterministic_write_json(proposal_path, payload)
    return {
        "status": "PASS",
        "proposal_only": True,
        "proposal_path": proposal_path.as_posix(),
        "recommended_actions": actions,
        "warnings": [],
        "blockers": [],
    }
