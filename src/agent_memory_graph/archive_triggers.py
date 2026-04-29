from __future__ import annotations

from pathlib import Path
from typing import Any

from .repo_adapter import read_repo_manifest
from .schemas import SCHEMA_VERSION, deterministic_write_json, read_json, resolve_memory_root, utc_now


TRIGGER_TYPES = {
    "milestone_completed",
    "pr_merged",
    "release_tagged",
    "architecture_decision",
    "new_long_term_requirement",
    "new_constraint",
    "context_gap_detected",
    "pending_update_accumulated",
    "stale_summary_detected",
    "user_requested_archive",
}

ACTIONS = {
    "no_action",
    "capture_pending_update",
    "create_compiled_candidate",
    "create_maintenance_proposal",
    "recommend_manual_archive",
}


def _events_path(memory_root: Path) -> Path:
    return memory_root / "reports" / "archive-trigger-events.json"


def _load_events(memory_root: Path) -> dict[str, Any]:
    return read_json(
        _events_path(memory_root),
        default={
            "schema_version": SCHEMA_VERSION,
            "report_type": "archive_trigger_events",
            "trigger_policy_active": True,
            "archive_auto_apply_enabled": False,
            "manual_archive_required": True,
            "events": [],
            "warnings": [],
            "blockers": [],
        },
    )


def _recommendation(trigger_type: str) -> tuple[str, str]:
    mapping = {
        "milestone_completed": (
            "recommend_manual_archive",
            "Milestone completion indicates stable project knowledge worth manual archive review.",
        ),
        "pr_merged": (
            "recommend_manual_archive",
            "Merged PR suggests project state changed enough to review curated archive updates.",
        ),
        "release_tagged": (
            "recommend_manual_archive",
            "Release tagging marks a durable milestone and should prompt manual archive review.",
        ),
        "architecture_decision": (
            "create_compiled_candidate",
            "Architecture decisions should be distilled into a curated compiled-session candidate.",
        ),
        "new_long_term_requirement": (
            "create_compiled_candidate",
            "New durable requirements belong in curated compiled-session memory, not raw session replay.",
        ),
        "new_constraint": (
            "create_compiled_candidate",
            "New durable constraints should be captured in curated compiled-session memory.",
        ),
        "context_gap_detected": (
            "create_maintenance_proposal",
            "Context gaps require reviewed maintenance work before archive quality degrades.",
        ),
        "pending_update_accumulated": (
            "capture_pending_update",
            "Accumulated updates should stay buffered as pending updates until reviewed.",
        ),
        "stale_summary_detected": (
            "create_maintenance_proposal",
            "Stale summaries require reviewed maintenance, not automatic archival.",
        ),
        "user_requested_archive": (
            "recommend_manual_archive",
            "Explicit operator intent should recommend the reviewed manual archive path.",
        ),
    }
    return mapping.get(
        trigger_type,
        ("no_action", "Transient or unknown event does not justify archive work."),
    )


def evaluate_archive_trigger(input_path: Path | str, repo_root: Path | str, memory_root: Path | str | None = None) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    memory_root = resolve_memory_root(memory_root)
    input_path = Path(input_path).resolve()
    payload = read_json(input_path)
    manifest = read_repo_manifest(repo_root)
    trigger_type = str(payload.get("event_type", "")).strip() or "transient_event"
    recommended_action, rationale = _recommendation(trigger_type)
    event = {
        "event_id": payload.get("event_id") or f"archive-trigger:{trigger_type}:{utc_now()}",
        "evaluated_at": utc_now(),
        "schema_version": SCHEMA_VERSION,
        "trigger_type": trigger_type,
        "recognized_trigger": trigger_type in TRIGGER_TYPES,
        "recommended_action": recommended_action,
        "archive_auto_apply_enabled": False,
        "manual_archive_required": True,
        "profile_id": payload.get("profile_id") or manifest.get("profile"),
        "project_id": payload.get("project_id") or manifest.get("project"),
        "summary": str(payload.get("summary", "")).strip(),
        "source": payload.get("source", "unknown"),
        "input_path": input_path.as_posix(),
        "rationale": rationale,
    }
    stored = _load_events(memory_root)
    events = [item for item in stored.get("events", []) if isinstance(item, dict)]
    events.append(event)
    stored["events"] = sorted(events, key=lambda item: (str(item.get("evaluated_at", "")), str(item.get("event_id", ""))))
    deterministic_write_json(_events_path(memory_root), stored)
    return {
        "status": "PASS",
        "repo_path": repo_root.as_posix(),
        "memory_root": memory_root.as_posix(),
        "input_path": input_path.as_posix(),
        "trigger_type": trigger_type,
        "recommended_action": recommended_action,
        "archive_auto_apply_enabled": False,
        "manual_archive_required": True,
        "rationale": rationale,
        "event": event,
        "warnings": [],
        "blockers": [],
    }


def write_archive_trigger_report(repo_root: Path | str, memory_root: Path | str | None = None) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    memory_root = resolve_memory_root(memory_root)
    manifest = read_repo_manifest(repo_root)
    stored = _load_events(memory_root)
    events = [item for item in stored.get("events", []) if isinstance(item, dict)]
    counts_by_action = {action: 0 for action in sorted(ACTIONS)}
    counts_by_trigger = {trigger: 0 for trigger in sorted(TRIGGER_TYPES)}
    recommendation_count = 0
    for event in events:
        action = str(event.get("recommended_action", "no_action"))
        trigger = str(event.get("trigger_type", ""))
        if action in counts_by_action:
            counts_by_action[action] += 1
        if trigger in counts_by_trigger:
            counts_by_trigger[trigger] += 1
        if action != "no_action":
            recommendation_count += 1
    latest_recommendations = [
        {
            "event_id": event.get("event_id"),
            "trigger_type": event.get("trigger_type"),
            "recommended_action": event.get("recommended_action"),
            "summary": event.get("summary", ""),
            "rationale": event.get("rationale", ""),
            "evaluated_at": event.get("evaluated_at"),
        }
        for event in sorted(events, key=lambda item: (str(item.get("evaluated_at", "")), str(item.get("event_id", ""))), reverse=True)
        if event.get("recommended_action") != "no_action"
    ]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "report_type": "archive_trigger_report",
        "profile": manifest.get("profile"),
        "project": manifest.get("project"),
        "trigger_policy_active": True,
        "archive_auto_apply_enabled": False,
        "manual_archive_required": True,
        "user_requested_archive_supported": True,
        "milestone_archive_recommendation_supported": True,
        "raw_sessions_default_read": False,
        "counts_by_action": counts_by_action,
        "counts_by_trigger": counts_by_trigger,
        "recommendation_count": recommendation_count,
        "latest_recommendation_count": recommendation_count,
        "latest_recommendations": latest_recommendations,
        "events": events,
        "warnings": [],
        "blockers": [],
    }
    report_path = memory_root / "reports" / "archive-trigger-report.json"
    deterministic_write_json(report_path, payload)
    return {
        "status": "PASS",
        "report_path": report_path.as_posix(),
        "recommendation_count": recommendation_count,
        "archive_auto_apply_enabled": False,
        "manual_archive_required": True,
        "warnings": [],
        "blockers": [],
    }
