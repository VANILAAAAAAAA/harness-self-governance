from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "2.0"
DEFAULT_MEMORY_ROOT = Path("~/.agent-memory-graph").expanduser()
DEFAULT_PROFILE_ID = "general"
DEFAULT_PROJECT_ID = "harness-self-governance"
PROFILE_IDS = ("general", "ehrlab")
VALID_ID_RE = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")
RECOMMENDED_READ_ORDER = [
    "global_graph",
    "active_profile",
    "active_project",
    "project_summary",
    "decision_ledger",
    "requirements",
    "constraints",
    "lineage_index",
    "mapped_logs_and_artifacts",
    "raw_sessions",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def resolve_memory_root(memory_root: str | Path | None) -> Path:
    if memory_root is None:
        return DEFAULT_MEMORY_ROOT
    return Path(memory_root).expanduser().resolve()


def deterministic_write_json(path: str | Path, payload: dict[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def read_json(path: str | Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        return dict(default or {})
    return json.loads(target.read_text(encoding="utf-8"))


def relpath(path: Path, base: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def validate_id(value: str, label: str) -> list[str]:
    blockers: list[str] = []
    if not value:
        blockers.append(f"{label} is required")
    elif not VALID_ID_RE.match(value):
        blockers.append(f"{label} must match {VALID_ID_RE.pattern}")
    return blockers


def ensure_memory_layout(memory_root: Path) -> None:
    for rel in ("profiles", "projects", "graph", "reports"):
        (memory_root / rel).mkdir(parents=True, exist_ok=True)


def default_config() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "context_protocol": "graph_governed",
        "default_context_order": RECOMMENDED_READ_ORDER,
        "raw_sessions_policy": "last_resort",
        "graph_mutation_enabled": False,
        "destructive_operations_enabled": False,
        "hub_llm_api_enabled": False,
    }


def default_profile(profile_id: str) -> dict[str, Any]:
    if profile_id == "ehrlab":
        label = "EHR Lab"
        role = "domain_knowledge_profile"
        description = "Domain knowledge profile for EHR research and healthcare modeling."
        projects: list[str] = []
    else:
        label = "General Governance"
        role = "governance_hub"
        description = "Global governance hub for the reusable Agent Memory Graph protocol."
        projects = [DEFAULT_PROJECT_ID]
    return {
        "schema_version": SCHEMA_VERSION,
        "profile_id": profile_id,
        "label": label,
        "role": role,
        "description": description,
        "projects": projects,
        "context_protocol": "graph_governed",
        "recommended_read_order": RECOMMENDED_READ_ORDER,
        "raw_sessions_policy": "last_resort",
        "graph_mutation_enabled": False,
        "destructive_operations_enabled": False,
    }


def default_project_manifest(profile_id: str, project_id: str) -> dict[str, Any]:
    title = "Harness Self Governance" if project_id == DEFAULT_PROJECT_ID else project_id.replace("-", " ").title()
    return {
        "schema_version": SCHEMA_VERSION,
        "profile_id": profile_id,
        "project_id": project_id,
        "title": title,
        "role": "governance_project" if profile_id == "general" else "knowledge_project",
        "privacy": "local_only",
        "context_protocol": "graph_governed",
        "raw_sessions_default_read": False,
        "raw_sessions_policy": "last_resort",
        "artifacts": {
            "project_summary": "project-summary.json",
            "decision_ledger": "decision-ledger.json",
            "requirements": "requirements.json",
            "constraints": "constraints.json",
            "session_index": "session-index.json",
            "graph_fragment": "graph-fragment.json",
            "lineage_index": "lineage-index.json",
        },
        "warnings": [],
        "blockers": [],
    }


def default_project_summary(profile_id: str, project_id: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "profile_id": profile_id,
        "project_id": project_id,
        "privacy": "local_only",
        "summary_contract": "agent_readable_project_context_v1",
        "summary": "",
        "project_identity": {
            "profile": profile_id,
            "project": project_id,
            "one_line": f"{profile_id}/{project_id} compiled project memory",
        },
        "routing_hints": {
            "aliases": [profile_id, project_id, project_id.replace("-", " ")],
            "negative_aliases": [],
            "default_entry_nodes": [f"project_summary:{profile_id}:{project_id}", f"plan:{profile_id}:{project_id}"],
        },
        "agent_priority_order": ["hard_constraints", "current_state", "active_phase", "plan.todo", "key_decisions", "evidence_paths"],
        "project_goal": "",
        "current_state": [],
        "open_problems": [],
        "phase_boundaries": [],
        "key_decisions": [],
        "hard_constraints": [],
        "evidence_paths": [],
        "read_order": ["project_summary", "project_plan", "constraints", "requirements", "decisions", "evidence_paths"],
        "memory_lifecycle": {
            "live_session_ram": "current turn only",
            "pending_update": "new facts wait here",
            "compiled_candidate": "candidate after session compilation",
            "archive_gate": "quality/scope gate before stable memory",
            "compiled_memory": "summary/plan/graph artifacts used by retriever",
        },
        "miss_policy": {
            "if_no_project_match": "return_zero_hit_packet_then_offer_create_pending_project_or_run_explicit_discovery",
            "if_project_match_but_no_claim_match": "return_low_confidence_packet_with_summary_and_plan_only_then_require_user_or_single_deepening_decision",
            "if_claim_not_in_summary": "traverse_evidence_once_before_answering; if still absent record_context_gap",
            "if_new_user_decision": "capture_pending_update_not_compiled_memory",
            "if_user_supplies_new_knowledge": "create_pending_update_with_source=this_turn_then_wait_for_archive_gate",
            "fallback_budget_rule": "at_most_one_automatic_deepening_step; never_scan_all_docs_or_raw_sessions_by_default",
        },
        "project_plan": {"completed": [], "todo": [], "update_mode": "agent_plan_command_compatible"},
        "session_summaries": [],
        "decisions": [],
        "requirements": [],
        "constraints": [],
        "graph_links": [],
        "warnings": [],
        "blockers": [],
    }


def collection_document(profile_id: str, project_id: str, key: str) -> dict[str, Any]:
    plural_key = {
        "decision-ledger": "decisions",
        "requirements": "requirements",
        "constraints": "constraints",
        "session-index": "sessions",
    }[key]
    return {
        "schema_version": SCHEMA_VERSION,
        "profile_id": profile_id,
        "project_id": project_id,
        "privacy": "local_only",
        plural_key: [],
        "warnings": [],
        "blockers": [],
    }


def default_graph_fragment(profile_id: str, project_id: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "profile_id": profile_id,
        "project_id": project_id,
        "privacy": "local_only",
        "nodes": [],
        "edges": [],
        "warnings": [],
        "blockers": [],
    }


def default_global_graph() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "context_protocol": "graph_governed",
        "raw_sessions_default_read": False,
        "recommended_read_order": RECOMMENDED_READ_ORDER,
        "nodes": [],
        "edges": [],
        "warnings": [],
        "blockers": [],
    }


def default_global_lineage() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "view_in_logs_requires_mapping": True,
        "nodes": {},
        "edges": {},
        "warnings": [],
        "blockers": [],
    }


def validate_compiled_session(payload: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        blockers.append("compiled session schema_version must be 2.0")
    blockers.extend(validate_id(str(payload.get("profile_id", "")), "profile_id"))
    blockers.extend(validate_id(str(payload.get("project_id", "")), "project_id"))
    if not payload.get("session_id"):
        blockers.append("session_id is required")
    if payload.get("privacy") not in {"local_only", "internal"}:
        blockers.append("privacy must be local_only or internal")
    if not isinstance(payload.get("summary"), str):
        blockers.append("summary must be a string")
    for section in ("decisions", "requirements", "constraints", "graph_links"):
        if not isinstance(payload.get(section), list):
            blockers.append(f"{section} must be a list")
    return blockers


def stable_items_by_id(items: list[dict[str, Any]], id_key: str = "id") -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    extras: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        ident = item.get(id_key)
        normalized = json.loads(json.dumps(item, sort_keys=True))
        if ident:
            merged[str(ident)] = normalized
        else:
            extras.append(normalized)
    ordered = [merged[key] for key in sorted(merged)]
    ordered.extend(sorted(extras, key=lambda item: json.dumps(item, sort_keys=True)))
    return ordered


def stable_links(links: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[tuple[str, str, str], dict[str, Any]] = {}
    extras: list[dict[str, Any]] = []
    for link in links:
        if not isinstance(link, dict):
            continue
        source = str(link.get("source", ""))
        target = str(link.get("target", ""))
        link_type = str(link.get("type", ""))
        normalized = json.loads(json.dumps(link, sort_keys=True))
        if source and target and link_type:
            unique[(source, link_type, target)] = normalized
        else:
            extras.append(normalized)
    ordered = [unique[key] for key in sorted(unique)]
    ordered.extend(sorted(extras, key=lambda item: json.dumps(item, sort_keys=True)))
    return ordered
