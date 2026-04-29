from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .archive_quality import compiled_session_example_dir, iter_compiled_session_examples
from .repo_adapter import read_repo_manifest
from .schemas import SCHEMA_VERSION, deterministic_write_json, read_json, resolve_memory_root, validate_compiled_session


RAW_SESSION_SUFFIXES = {".txt", ".jsonl", ".log", ".trace", ".md"}


def _base_gate() -> dict[str, Any]:
    return {
        "live_session_priority": True,
        "pending_update_supported": True,
        "compiled_candidate_requires_review": True,
        "forensic_raw_sessions_explicit_only": True,
        "raw_sessions_default_read": False,
        "raw_sessions_required": False,
        "review_required": False,
        "auto_archive_allowed": False,
        "archive_allowed": False,
    }


def _looks_like_pending_update(payload: dict[str, Any], path: Path) -> bool:
    if path.name == "pending-updates.json":
        return True
    if payload.get("routing_policy") == "new_information_becomes_pending_update":
        return True
    updates = payload.get("updates")
    if isinstance(updates, list):
        return True
    status = str(payload.get("status", "")).lower()
    return "pending" in status and "archive" in status


def _looks_like_forensic_only(payload: dict[str, Any], path: Path) -> bool:
    path_l = path.as_posix().lower()
    if "sessions/raw" in path_l or "raw-session" in path_l or path.suffix.lower() in RAW_SESSION_SUFFIXES:
        return True
    if any(key in payload for key in ("transcript", "messages", "chat", "speaker_turns", "raw_session")):
        return True
    text = json.dumps(payload, ensure_ascii=False).lower() if payload else ""
    return "user:" in text and "assistant:" in text


def classify_archive_input(input_path: Path | str, repo_root: Path | str, memory_root: Path | str | None = None) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    memory_root = resolve_memory_root(memory_root)
    input_path = Path(input_path).resolve()
    gate = _base_gate()
    payload: dict[str, Any] = {}
    if input_path.suffix.lower() == ".json" and input_path.exists():
        try:
            payload = read_json(input_path)
        except json.JSONDecodeError:
            payload = {}
    classification = "transient"
    rationale = "live session or scratch material remains transient until explicitly reviewed"
    if input_path.suffix.lower() == ".json" and payload and not validate_compiled_session(payload):
        classification = "compiled_candidate"
        rationale = "compiled-session shaped artifact is eligible only through explicit reviewed archive-session path"
        gate["review_required"] = True
        gate["archive_allowed"] = True
    elif _looks_like_pending_update(payload, input_path):
        classification = "pending_update"
        rationale = "new information is buffered as pending update and never auto-promoted to compiled memory"
    elif _looks_like_forensic_only(payload, input_path):
        classification = "forensic_only"
        rationale = "raw sessions stay last-resort forensic context and are not default-read memory"
    gate["classification"] = classification
    gate["rationale"] = rationale
    return {
        "status": "PASS",
        "input_path": input_path.as_posix(),
        "repo_path": repo_root.as_posix(),
        "memory_root": memory_root.as_posix(),
        "archive_gate": gate,
        "warnings": [],
        "blockers": [],
    }


def _pending_update_items(memory_root: Path) -> list[dict[str, Any]]:
    payload = read_json(
        memory_root / "routing" / "pending-updates.json",
        default={"updates": []},
    )
    items = []
    for item in payload.get("updates", []):
        if not isinstance(item, dict):
            continue
        items.append(
            {
                "id": item.get("id"),
                "classification": "pending_update",
                "path": "<memory-root>/routing/pending-updates.json",
                "archive_allowed": False,
                "review_required": False,
                "summary": item.get("text", "")[:160],
            }
        )
    return items


def _compiled_candidate_items(repo_root: Path, memory_root: Path, profile_id: str, project_id: str) -> list[dict[str, Any]]:
    items = []
    for path in iter_compiled_session_examples(compiled_session_example_dir(repo_root)):
        payload = read_json(path)
        items.append(
            {
                "id": payload.get("session_id") or path.stem,
                "classification": "compiled_candidate",
                "path": path.relative_to(repo_root).as_posix(),
                "archive_allowed": True,
                "review_required": True,
                "summary": payload.get("summary", "")[:160],
            }
        )
    if items:
        return items
    session_index = read_json(
        memory_root / "projects" / profile_id / project_id / "session-index.json",
        default={"sessions": []},
    )
    for session in session_index.get("sessions", []):
        items.append(
            {
                "id": session.get("session_id"),
                "classification": "compiled_candidate",
                "path": "<memory-root>/projects/{}/{}/session-index.json".format(profile_id, project_id),
                "archive_allowed": True,
                "review_required": True,
                "summary": str(session.get("summary", ""))[:160],
            }
        )
    return items


def _forensic_only_items(repo_root: Path) -> list[dict[str, Any]]:
    items = []
    raw_root = repo_root / "sessions" / "raw"
    if raw_root.exists():
        for path in sorted(item for item in raw_root.rglob("*") if item.is_file()):
            items.append(
                {
                    "id": path.stem,
                    "classification": "forensic_only",
                    "path": path.relative_to(repo_root).as_posix(),
                    "archive_allowed": False,
                    "review_required": False,
                    "summary": "raw session source material",
                }
            )
    return items


def write_archive_gate_report(repo_root: Path | str, memory_root: Path | str | None = None) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    memory_root = resolve_memory_root(memory_root)
    manifest = read_repo_manifest(repo_root)
    profile_id = manifest.get("profile")
    project_id = manifest.get("project")
    items = _compiled_candidate_items(repo_root, memory_root, profile_id, project_id) + _pending_update_items(memory_root) + _forensic_only_items(repo_root)
    counts = {name: 0 for name in ("transient", "pending_update", "compiled_candidate", "forensic_only")}
    for item in items:
        counts[item["classification"]] = counts.get(item["classification"], 0) + 1
    payload = {
        "schema_version": SCHEMA_VERSION,
        "report_type": "archive_gate_report",
        "profile": manifest.get("profile"),
        "project": manifest.get("project"),
        "live_session_priority": True,
        "pending_update_supported": True,
        "compiled_candidate_requires_review": True,
        "forensic_raw_sessions_explicit_only": True,
        "raw_sessions_default_read": False,
        "raw_sessions_required": False,
        "counts": counts,
        "items": items,
        "warnings": [],
        "blockers": [],
    }
    report_path = memory_root / "reports" / "archive-gate-report.json"
    deterministic_write_json(report_path, payload)
    return {
        "status": "PASS",
        "report_path": report_path.as_posix(),
        "counts": counts,
        "warnings": [],
        "blockers": [],
    }
