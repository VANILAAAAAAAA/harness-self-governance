from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .repo_adapter import read_repo_manifest
from .schemas import SCHEMA_VERSION, deterministic_write_json, read_json, resolve_memory_root, utc_now


def _candidate_id(update_id: str, text: str) -> str:
    digest = hashlib.sha256(f"{update_id}:{text}".encode("utf-8")).hexdigest()[:12]
    return f"compiled-candidate:{digest}"


def compile_pending_updates(repo_root: Path | str, memory_root: Path | str | None = None, profile: str | None = None, project: str | None = None) -> dict[str, Any]:
    """Convert pending updates into reviewed candidate records without archiving.

    This is intentionally non-destructive: it does not remove pending updates and it does
    not merge candidates into stable compiled memory. It only materializes an explicit
    `compiled_candidate` layer for the archive gate to inspect.
    """

    repo_root = Path(repo_root).resolve()
    memory_root_path = resolve_memory_root(memory_root)
    manifest = read_repo_manifest(repo_root)
    profile = profile or manifest.get("profile")
    project = project or manifest.get("project")
    pending_path = memory_root_path / "routing" / "pending-updates.json"
    candidate_path = memory_root_path / "routing" / "compiled-candidates.json"
    pending_payload = read_json(pending_path, default={"updates": []})
    existing_payload = read_json(
        candidate_path,
        default={
            "schema_version": SCHEMA_VERSION,
            "lifecycle_policy": "pending_update_to_compiled_candidate_requires_review",
            "candidates": [],
            "warnings": [],
            "blockers": [],
        },
    )
    candidates_by_id = {item.get("id"): item for item in existing_payload.get("candidates", []) if isinstance(item, dict)}
    compiled = []
    skipped = []
    for update in pending_payload.get("updates", []):
        if not isinstance(update, dict):
            continue
        if profile and update.get("profile") != profile:
            skipped.append({"id": update.get("id"), "reason": "profile_mismatch"})
            continue
        if project and update.get("project") != project:
            skipped.append({"id": update.get("id"), "reason": "project_mismatch"})
            continue
        text = str(update.get("text", "")).strip()
        if not text:
            skipped.append({"id": update.get("id"), "reason": "empty_text"})
            continue
        candidate = {
            "id": _candidate_id(str(update.get("id", "pending-update")), text),
            "source_update_id": update.get("id"),
            "profile": update.get("profile"),
            "project": update.get("project"),
            "text": text,
            "status": "requires_review",
            "lifecycle_state": "compiled_candidate",
            "source_lifecycle_state": update.get("lifecycle_state", "pending_update"),
            "candidate_type": update.get("update_type", "new_information"),
            "source": update.get("source", "current_turn"),
            "created_at": utc_now(),
            "archive_gate_required": True,
            "review_required": True,
            "auto_archive_allowed": False,
            "raw_sessions_allowed": False,
            "suggested_compiled_session_patch": {
                "summary_candidate": text[:240],
                "evidence_policy": "anchor_only_until_reviewed",
                "target_profile": update.get("profile"),
                "target_project": update.get("project"),
            },
        }
        candidates_by_id[candidate["id"]] = candidate
        compiled.append(candidate)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "lifecycle_policy": "pending_update_to_compiled_candidate_requires_review",
        "candidates": [candidates_by_id[key] for key in sorted(candidates_by_id)],
        "warnings": [],
        "blockers": [],
    }
    deterministic_write_json(candidate_path, payload)
    report = {
        "schema_version": SCHEMA_VERSION,
        "report_type": "pending_update_compilation_report",
        "status": "PASS",
        "repo_path": repo_root.as_posix(),
        "memory_root": memory_root_path.as_posix(),
        "pending_updates_path": pending_path.as_posix(),
        "compiled_candidates_path": candidate_path.as_posix(),
        "compiled_count": len(compiled),
        "total_candidate_count": len(payload["candidates"]),
        "skipped": skipped,
        "non_destructive": True,
        "archive_gate_required": True,
        "auto_archive_allowed": False,
        "warnings": [],
        "blockers": [],
    }
    deterministic_write_json(memory_root_path / "reports" / "pending-update-compilation-report.json", report)
    return report


def list_compiled_candidates(memory_root: Path | str | None = None) -> list[dict[str, Any]]:
    memory_root_path = resolve_memory_root(memory_root)
    payload = read_json(memory_root_path / "routing" / "compiled-candidates.json", default={"candidates": []})
    return [item for item in payload.get("candidates", []) if isinstance(item, dict)]
